import unittest

from backend.agent.tools.instagram import InstagramFindings
from backend.agent.tools.instagram_comments import (
    MIN_COMMENTS,
    CommentFindings,
    InstagramComment,
    analyze_comments,
    is_complaint,
    parse_comments,
)
from backend.scoring.sources.instagram import score_instagram_comments
from backend.scoring.types import ScoreStatus


def comment(owner: str, text: str) -> InstagramComment:
    return InstagramComment(owner=owner, text=text, post_url="https://www.instagram.com/p/x/")


def filler(count: int) -> list[InstagramComment]:
    """Neutral comments from distinct accounts, none repeating another."""
    return [comment(f"fan{i}", f"lovely piece number {i}") for i in range(count)]


class IsComplaintTests(unittest.TestCase):
    def test_flags_complaints_and_warnings(self) -> None:
        for text in (
            "Liars and thieves!! Don't know how to measure",
            "Don’t waste your time or money",  # curly apostrophe
            "Never received my order",
            "Terrible!!! I bought a dress and it was way too big",
            "This is a SCAM",
            "Nothing like the pictures",
            "Very disappointed, fabric is very poor quality",
            # Phrasings from a real store's comments that the first lexicon missed
            "Nope!! This dress is a lie!!",
            "BEWARE!! CROOKS!!",
            "Pieces of shit.",
            "They rip you off.",
            "Photos are not correct, fabric is not correct",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_complaint(text))

    def test_ignores_praise_and_questions(self) -> None:
        for text in (
            "Love this dress! 😍",
            "Fast shipping and great quality",
            "Where can I get this in blue?",
            "This is not a scam, I got mine in a week",
            "definitely isn't fake, looks just like the photos",
            "Ripped jeans off the rack look great",
            "Soooo happy with my order! 👌🏼",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_complaint(text))


class AnalyzeCommentsTests(unittest.TestCase):
    def test_too_few_comments_is_not_scored(self) -> None:
        result = analyze_comments(filler(MIN_COMMENTS - 1))

        self.assertIsNone(result.risk_score)
        self.assertEqual(result.analyzed, MIN_COMMENTS - 1)
        self.assertIn("need 10", result.skip_reason or "")

    def test_one_complaint_is_not_a_pattern(self) -> None:
        result = analyze_comments(filler(9) + [comment("angry", "Terrible service")])

        self.assertEqual(len(result.complaints), 1)
        self.assertEqual(result.complaint_risk, 0)
        self.assertEqual(result.risk_score, 0)

    def test_complaint_risk_scales_with_share_and_caps(self) -> None:
        two_in_twenty = analyze_comments(
            filler(18)
            + [comment("a", "Liars and thieves"), comment("b", "Never received it")]
        )
        three_in_twelve = analyze_comments(
            filler(9)
            + [comment(n, "Total scam, stay away") for n in ("a", "b", "c")]
        )

        self.assertEqual(two_in_twenty.complaint_risk, 38)  # 10% of the 25% needed
        self.assertEqual(three_in_twelve.complaint_risk, 95)  # 25% hits the cap
        self.assertEqual(three_in_twelve.risk_score, 95)

    def test_identical_text_from_many_accounts_is_flagged(self) -> None:
        bots = [comment(f"bot{i}", "Great product, fast shipping!!") for i in range(3)]
        result = analyze_comments(filler(9) + bots)

        self.assertEqual(result.duplicate_comments, 3)
        self.assertEqual(result.duplicate_risk, 70)  # 25% >= the 20% cap point
        self.assertEqual(result.complaint_risk, 0)
        self.assertEqual(result.risk_score, 70)

    def test_one_account_repeating_itself_is_not_a_bot_ring(self) -> None:
        spam = [comment("chatty", "Great product, fast shipping!!") for _ in range(3)]
        result = analyze_comments(filler(9) + spam)

        self.assertEqual(result.duplicate_comments, 0)

    def test_short_and_emoji_only_repeats_are_normal(self) -> None:
        crowd = [comment(f"a{i}", "🔥🔥🔥") for i in range(4)] + [
            comment(f"b{i}", "love it") for i in range(4)
        ]
        result = analyze_comments(filler(4) + crowd)

        self.assertEqual(result.duplicate_comments, 0)
        self.assertEqual(result.risk_score, 0)

    def test_risk_is_the_worse_of_the_two_signals(self) -> None:
        bots = [comment(f"bot{i}", "Great product, fast shipping!!") for i in range(3)]
        angry = [comment("a", "Total scam"), comment("b", "Stay away")]
        result = analyze_comments(filler(15) + bots + angry)

        self.assertEqual(
            result.risk_score, max(result.complaint_risk, result.duplicate_risk)
        )


class ParseCommentsTests(unittest.TestCase):
    def test_flattens_posts_and_skips_the_stores_own_replies(self) -> None:
        posts = [
            {
                "url": "https://www.instagram.com/p/one/",
                "latestComments": [
                    {"ownerUsername": "alice", "text": " Love it "},
                    {"ownerUsername": "Shop", "text": "Thanks for the kind words!"},
                    {"ownerUsername": "bob", "text": ""},
                ],
            },
            {"url": "https://www.instagram.com/p/two/", "latestComments": None},
            {
                "url": "https://www.instagram.com/p/three/",
                "latestComments": [{"ownerUsername": "carol", "text": "Nice"}],
            },
        ]
        comments = parse_comments(posts, "shop")

        self.assertEqual([c.owner for c in comments], ["alice", "carol"])
        self.assertEqual(comments[0].text, "Love it")
        self.assertEqual(comments[0].post_url, "https://www.instagram.com/p/one/")


class ScoreInstagramCommentsTests(unittest.TestCase):
    def findings(self, comments: list[InstagramComment]) -> InstagramFindings:
        return InstagramFindings(handle="shop", comments=analyze_comments(comments))

    def test_complaints_are_quoted_in_the_finding(self) -> None:
        score = score_instagram_comments(
            self.findings(
                filler(9) + [comment(n, "Liars and thieves, total scam") for n in "abc"]
            )
        )

        self.assertEqual(score.status, ScoreStatus.AVAILABLE)
        self.assertEqual(score.risk_score, 95)
        finding = score.findings[0]
        self.assertEqual(finding.rule_id, "INSTAGRAM_COMPLAINT_COMMENTS")
        self.assertEqual(finding.impact, 95)
        self.assertIn("3 of 12", finding.explanation)
        self.assertIn("Liars and thieves, total scam", finding.explanation)
        self.assertEqual(len(finding.metadata["samples"]), 3)
        self.assertEqual(finding.metadata["url"], "https://www.instagram.com/shop/")

    def test_duplicates_get_their_own_finding(self) -> None:
        bots = [comment(f"bot{i}", "Great product, fast shipping!!") for i in range(3)]
        score = score_instagram_comments(self.findings(filler(9) + bots))

        self.assertEqual(
            [f.rule_id for f in score.findings], ["INSTAGRAM_DUPLICATE_COMMENTS"]
        )
        self.assertEqual(score.risk_score, 70)

    def test_both_signals_produce_both_findings(self) -> None:
        bots = [comment(f"bot{i}", "Great product, fast shipping!!") for i in range(3)]
        angry = [comment("a", "Total scam"), comment("b", "Stay away")]
        score = score_instagram_comments(self.findings(filler(15) + bots + angry))

        self.assertEqual(
            {f.rule_id for f in score.findings},
            {"INSTAGRAM_COMPLAINT_COMMENTS", "INSTAGRAM_DUPLICATE_COMMENTS"},
        )

    def test_clean_comments_are_a_positive_finding(self) -> None:
        score = score_instagram_comments(self.findings(filler(12)))

        self.assertEqual(score.risk_score, 0)
        self.assertEqual(score.findings[0].rule_id, "INSTAGRAM_CLEAN_COMMENTS")
        self.assertEqual(score.findings[0].impact, 0)

    def test_too_few_comments_is_insufficient_data_not_safe(self) -> None:
        score = score_instagram_comments(self.findings(filler(3)))

        self.assertEqual(score.status, ScoreStatus.INSUFFICIENT_DATA)
        self.assertIsNone(score.risk_score)
        self.assertIn("only 3", score.metadata["reason"])

    def test_errors_from_either_level_are_reported(self) -> None:
        run_failed = InstagramFindings(
            handle="shop", comments=CommentFindings(error="posts run failed: boom")
        )
        whole_check_failed = InstagramFindings(error="research timed out after 80s")

        for findings, expected in (
            (run_failed, "posts run failed: boom"),
            (whole_check_failed, "research timed out after 80s"),
        ):
            with self.subTest(expected=expected):
                score = score_instagram_comments(findings)
                self.assertEqual(score.status, ScoreStatus.ERROR)
                self.assertEqual(score.metadata["error"], expected)


if __name__ == "__main__":
    unittest.main()
