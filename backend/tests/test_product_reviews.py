import unittest

from backend.agent.tools.product_reviews import (
    DEFAULT_CAP,
    MAX_CHARS,
    MIN_CHARS,
    cap_confidence,
    dedupe_key,
    normalise,
    prepare,
)
from backend.services.gptzero import CorpusVerdict, ReviewScore, summarize


def review(n: int = 1, *, filler: str = "x") -> str:
    """A string comfortably over MIN_CHARS, distinct per n."""
    return f"Review number {n} about the product. " + filler * 40


class NormaliseTest(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(normalise("  it   arrived\n\n late  "), "it arrived late")

    def test_strips_leading_chrome(self):
        self.assertEqual(
            normalise("Verified Purchase: the strap broke in a week"),
            "the strap broke in a week",
        )

    def test_strips_trailing_chrome(self):
        self.assertEqual(
            normalise("the strap broke in a week Was this helpful?"),
            "the strap broke in a week",
        )
        self.assertEqual(normalise("great mug Helpful (32)"), "great mug")

    def test_strips_stars_and_rating(self):
        self.assertEqual(
            normalise("★★★★★ 5 out of 5 stars Lovely mug"),
            "Lovely mug",
        )

    def test_strips_wrapping_quotes(self):
        self.assertEqual(normalise('"“Lovely mug”"'), "Lovely mug")

    def test_preserves_typos_and_punctuation(self):
        # The typos ARE the human signal - see the module docstring.
        raw = "recieved it broken!! didnt even work,, would NOT recomend"
        self.assertEqual(normalise(raw), raw)

    def test_handles_empty_and_none_like(self):
        self.assertEqual(normalise(""), "")
        self.assertEqual(normalise("   "), "")


class DedupeKeyTest(unittest.TestCase):
    def test_ignores_case_punctuation_and_spacing(self):
        self.assertEqual(
            dedupe_key("Lovely mug, arrived fast!"),
            dedupe_key("lovely   mug arrived fast"),
        )

    def test_different_reviews_differ(self):
        self.assertNotEqual(dedupe_key("lovely mug"), dedupe_key("awful mug"))


class PrepareTest(unittest.TestCase):
    def test_drops_short_reviews(self):
        result = prepare(["Great!", "A+++", review(1)])
        self.assertEqual(result.texts, [review(1)])
        self.assertEqual(result.dropped_short, 2)
        self.assertEqual(result.received, 3)

    def test_keeps_text_at_the_length_boundary(self):
        exactly_min = "a" * MIN_CHARS
        self.assertEqual(prepare([exactly_min]).texts, [exactly_min])
        self.assertEqual(prepare(["a" * (MIN_CHARS - 1)]).texts, [])

    def test_drops_oversized_blobs_rather_than_truncating(self):
        blob = "a" * (MAX_CHARS + 1)
        result = prepare([blob, review(1)])
        self.assertEqual(result.texts, [review(1)])
        self.assertEqual(result.dropped_long, 1)

    def test_dedupes_the_qenova_case(self):
        """Four JSON-LD entries that are the same review four times."""
        result = prepare([review(1)] * 4)
        self.assertEqual(result.texts, [review(1)])
        self.assertEqual(result.dropped_duplicate, 3)

    def test_dedupes_across_differing_chrome(self):
        # Same review reached us via two widgets, one of which wrapped it in
        # quotes and appended a vote counter.
        a = "The mug arrived chipped and support never replied to me."
        b = f'"{a}" Helpful (12)'
        result = prepare([a, b])
        self.assertEqual(result.usable, 1)
        self.assertEqual(result.dropped_duplicate, 1)

    def test_dedupe_runs_before_cap(self):
        # 30 copies of one review plus 3 real ones. Capping first would spend
        # the whole budget on repeats and then report confidence in them.
        raw = [review(1)] * 30 + [review(2), review(3), review(4)]
        result = prepare(raw, cap=5)
        self.assertEqual(result.usable, 4)
        self.assertEqual(result.dropped_duplicate, 29)
        self.assertEqual(result.dropped_to_cap, 0)

    def test_caps_and_reports_the_overflow(self):
        result = prepare([review(i) for i in range(40)], cap=10)
        self.assertEqual(result.usable, 10)
        self.assertEqual(result.dropped_to_cap, 30)
        # Order is preserved: the cap takes the first N, not a random N.
        self.assertEqual(result.texts[0], review(0))

    def test_default_cap_is_applied(self):
        result = prepare([review(i) for i in range(100)])
        self.assertEqual(result.usable, DEFAULT_CAP)

    def test_empty_input(self):
        result = prepare([])
        self.assertEqual(result.texts, [])
        self.assertEqual(result.received, 0)


def verdict_with(confidence: str) -> CorpusVerdict:
    return CorpusVerdict(
        total=20,
        scored=20,
        flagged=10,
        ai_share=0.5,
        mean_prob=0.5,
        short_flagged=0,
        verdict="likely_ai_reviews",
        confidence=confidence,
    )


class CapConfidenceTest(unittest.TestCase):
    def test_widget_extraction_is_left_alone(self):
        v = verdict_with("high")
        self.assertEqual(cap_confidence(v, "widget:judge.me").confidence, "high")

    def test_heuristic_is_capped_at_low(self):
        self.assertEqual(cap_confidence(verdict_with("high"), "heuristic").confidence, "low")

    def test_json_ld_only_is_capped_at_low(self):
        """SEO markup is a sample the store chose, so it can't read as 'high'."""
        self.assertEqual(cap_confidence(verdict_with("medium"), "json-ld").confidence, "low")

    def test_mixed_thin_is_capped_at_low(self):
        self.assertEqual(cap_confidence(verdict_with("high"), "mixed-thin").confidence, "low")

    def test_insufficient_is_not_raised_to_low(self):
        self.assertEqual(
            cap_confidence(verdict_with("insufficient"), "heuristic").confidence,
            "insufficient",
        )

    def test_missing_via_is_left_alone(self):
        self.assertEqual(cap_confidence(verdict_with("high"), None).confidence, "high")

    def test_does_not_mutate_the_original(self):
        v = verdict_with("high")
        cap_confidence(v, "heuristic")
        self.assertEqual(v.confidence, "high")


class PrepareThenSummarizeTest(unittest.TestCase):
    """The two halves meet: what prepare() keeps is what summarize() counts."""

    def test_dedupe_changes_the_verdict(self):
        ai = review(1)
        human = [review(i) for i in range(2, 5)]

        def score(text: str, prob: float) -> ReviewScore:
            return ReviewScore(text=text, ai_prob=prob, predicted_class="ai", confidence="high")

        # Un-deduped: one AI review repeated reads as a review farm.
        naive = [score(ai, 1.0)] * 3 + [score(t, 0.0) for t in human]
        self.assertEqual(summarize(naive).ai_share, 0.5)

        # Deduped: the same corpus is one flagged review out of four.
        prepared = prepare([ai] * 3 + human)
        deduped = [
            score(t, 1.0 if t == ai else 0.0) for t in prepared.texts
        ]
        self.assertEqual(summarize(deduped).ai_share, 0.25)


if __name__ == "__main__":
    unittest.main()
