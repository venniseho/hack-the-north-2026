import unittest
from unittest.mock import AsyncMock, patch

import httpx

from backend.agent.tools.instagram import InstagramFindings
from backend.agent.tools.instagram_comments import (
    CommentFindings,
    InstagramComment,
)
from backend.agent.tools.product_reviews import PreparedReviews
from backend.agent.tools.reddit import RedditFindings, RedditPost
from backend.api.app import app
from backend.services.gptzero import ReviewScore, summarize


def critical_post() -> RedditPost:
    return RedditPost(
        url="https://www.reddit.com/r/Scams/comments/abc123/never_arrived/",
        title="Order never arrived",
        quote="Paid three weeks ago, nothing shipped.",
        severity="critical",
        subreddit="Scams",
        verified=True,
    )


def unscored_instagram() -> InstagramFindings:
    return InstagramFindings(
        comments=CommentFindings(skip_reason="no Instagram link found")
    )


def scam_comments() -> CommentFindings:
    """3 of 12 comments complaining: risk 95."""
    angry = [
        InstagramComment(n, "Total scam, never received it", category="scam_accusation")
        for n in "abc"
    ]
    return CommentFindings(
        analyzed=12,
        complaints=angry,
        complaint_summary="3 of 12 comments say the store is a scam.",
        complaint_quotes=angry[:2],
        complaint_risk=95,
        risk_score=95,
    )


def scam_instagram() -> InstagramFindings:
    return InstagramFindings(handle="store", followers=5000, comments=scam_comments())


def ai_review(index: int) -> str:
    return f"This product has transformed my daily routine in every way. {index}"


def scored_corpus() -> tuple:
    """A verdict standing in for a real GPTZero run: 2 of 4 reviews flagged."""
    scores = [
        ReviewScore("a" * 300, 1.0, "ai", "high"),
        ReviewScore("b" * 300, 0.98, "ai", "high"),
        ReviewScore("c" * 300, 0.002, "human", "high"),
        ReviewScore("d" * 300, 0.0, "human", "high"),
    ]
    return summarize(scores), PreparedReviews(texts=["x"] * 4, received=4)


class ApiIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def post_analyze(
        
        self,
       
        findings: RedditFindings,
        instagram: InstagramFindings | None = None,
        instagram_links: list[str] | None = None,
    ,
        *,
        reviews: list[str] | None = None,
        via: str | None = None,
    ) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        body: dict = {"currentUrl": "https://store.example/item"}
        if reviews is not None:
            body["reviews"] = reviews
        if via is not None:
            body["via"] = via

        with patch(
            "backend.api.app.research_store", AsyncMock(return_value=findings)
        ) as research, patch(
            "backend.api.app.research_store_instagram",
            AsyncMock(return_value=instagram or unscored_instagram()),
        ) as research_instagram:
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "currentUrl": "https://store.example/item",
                        **(
                            {"instagramLinks": instagram_links}
                            if instagram_links is not None
                            else {}
                        ),
                    },
                    headers={"Origin": "chrome-extension://integration-test"},
                )
        research.assert_awaited_once_with("https://store.example/item")
        research_instagram.assert_awaited_once_with(
            "https://store.example/item", instagram_links or []
        )
        return response

    async def test_instagram_links_from_the_page_reach_the_research(self) -> None:
        links = ["https://www.instagram.com/store/", "https://instagram.com/p/x/"]
        response = await self.post_analyze(
            RedditFindings(found_any=False), instagram_links=links
        )

        self.assertEqual(response.status_code, 200)  # the assertions are in post_analyze

    async def test_real_reddit_score_is_aggregated_with_other_sources(self) -> None:
        response = await self.post_analyze(
            RedditFindings(found_any=True, posts=[critical_post()], risk_score=40)
        )
        payload = response.json()
        scoring = payload["scoring"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")
        self.assertEqual(payload["store"]["domain"], "store.example")
        self.assertEqual(scoring["coverage"], 70)  # social proof is unscored
        # (40 * 0.4 + 58 * 0.3) / 0.7
        self.assertAlmostEqual(scoring["overallRisk"], 47.714, places=3)

        third_party, site_analysis, social_proof = scoring["categories"]
        self.assertEqual(third_party["riskScore"], 40)
        reddit = third_party["sources"][0]
        self.assertEqual(reddit["id"], "reddit")
        self.assertEqual(reddit["status"], "available")
        self.assertEqual(reddit["findings"][0]["ruleId"], "REDDIT_CRITICAL")
        self.assertEqual(
            reddit["findings"][0]["metadata"]["url"], critical_post().url
        )
        self.assertIsNone(site_analysis["riskScore"])

    async def test_no_reviews_is_insufficient_data_not_low_risk(self) -> None:
        response = await self.post_analyze(
            RedditFindings(found_any=True, posts=[critical_post()], risk_score=40)
        )
        scoring = response.json()["scoring"]

        gptzero = scoring["categories"][1]["sources"][0]
        self.assertEqual(gptzero["id"], "gptzero")
        self.assertEqual(gptzero["status"], "insufficient-data")
        self.assertIsNone(gptzero["riskScore"])

    async def test_extracted_reviews_produce_a_real_gptzero_score(self) -> None:
        verdict, prepared = scored_corpus()
        with patch.dict("os.environ", {"GPTZERO_API_KEY": "test-key"}):
            with patch(
                "backend.api.analysis.score_reviews",
                AsyncMock(return_value=(verdict, prepared)),
            ) as scorer:
                response = await self.post_analyze(
                    RedditFindings(found_any=True, posts=[critical_post()], risk_score=40),
                    reviews=[ai_review(i) for i in range(4)],
                    via="widget:judgeme",
                )

        scorer.assert_awaited_once()
        self.assertEqual(scorer.await_args.kwargs["via"], "widget:judgeme")

        scoring = response.json()["scoring"]
        gptzero = scoring["categories"][1]["sources"][0]
        self.assertEqual(gptzero["status"], "available")
        # Mean of 1.0, 0.98, 0.002 and 0.0 is 0.4955, rescaled to 0-100.
        self.assertEqual(gptzero["riskScore"], 49.5)
        self.assertEqual(gptzero["metadata"]["flagged"], 2)
        self.assertEqual(len(gptzero["findings"]), 2)
        # Every source now reports, so nothing is uncovered.
        self.assertEqual(scoring["coverage"], 100)

    async def test_missing_api_key_does_not_fail_the_request(self) -> None:
        with patch.dict("os.environ", {"GPTZERO_API_KEY": ""}):
            response = await self.post_analyze(
                RedditFindings(found_any=True, posts=[critical_post()], risk_score=40),
                reviews=[ai_review(i) for i in range(4)],
            )

        self.assertEqual(response.status_code, 200)
        gptzero = response.json()["scoring"]["categories"][1]["sources"][0]
        self.assertEqual(gptzero["status"], "unavailable")
        self.assertIsNone(gptzero["riskScore"])
        self.assertIsNone(social_proof["riskScore"])

    async def test_real_instagram_score_is_aggregated(self) -> None:
        response = await self.post_analyze(
            RedditFindings(found_any=True, posts=[critical_post()], risk_score=40),
            scam_instagram(),
        )
        scoring = response.json()["scoring"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(scoring["coverage"], 100)
        # social proof = 95, then 40 * 0.4 + 58 * 0.3 + 95 * 0.3
        self.assertAlmostEqual(scoring["overallRisk"], 61.9, places=3)

        social_proof = scoring["categories"][2]
        self.assertEqual(social_proof["id"], "social-proof")
        self.assertAlmostEqual(social_proof["riskScore"], 95, places=3)
        (comments,) = social_proof["sources"]
        self.assertEqual(comments["id"], "instagram-comments")
        self.assertEqual(comments["status"], "available")
        self.assertEqual(comments["riskScore"], 95)
        self.assertEqual(
            comments["findings"][0]["ruleId"], "INSTAGRAM_COMPLAINT_COMMENTS"
        )
        self.assertIn("Total scam", comments["findings"][0]["explanation"])

    async def test_instagram_failure_degrades_only_the_instagram_source(self) -> None:
        response = await self.post_analyze(
            RedditFindings(found_any=True, posts=[critical_post()], risk_score=40),
            InstagramFindings(error="research timed out after 80s"),
        )
        scoring = response.json()["scoring"]

        self.assertEqual(response.status_code, 200)
        (instagram,) = scoring["categories"][2]["sources"]
        self.assertEqual(instagram["status"], "error")
        self.assertEqual(
            instagram["metadata"]["error"], "research timed out after 80s"
        )
        self.assertEqual(scoring["categories"][0]["riskScore"], 40)

    async def test_no_posts_is_insufficient_data_not_safe(self) -> None:
        response = await self.post_analyze(RedditFindings(found_any=False))
        scoring = response.json()["scoring"]

        reddit = scoring["categories"][0]["sources"][0]
        self.assertEqual(reddit["status"], "insufficient-data")
        self.assertIsNone(reddit["riskScore"])
        self.assertIsNone(scoring["categories"][0]["riskScore"])
        self.assertEqual(scoring["overallRisk"], 58)  # site analysis only
        self.assertEqual(scoring["coverage"], 30)

    async def test_research_failure_degrades_only_the_reddit_source(self) -> None:
        response = await self.post_analyze(
            RedditFindings(found_any=False, error="research timed out after 45s")
        )
        scoring = response.json()["scoring"]

        self.assertEqual(response.status_code, 200)
        reddit = scoring["categories"][0]["sources"][0]
        self.assertEqual(reddit["status"], "error")
        self.assertEqual(reddit["metadata"]["error"], "research timed out after 45s")
        self.assertIsNone(scoring["overallRisk"])

    async def test_analyze_endpoint_validates_requests(self) -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            wrong_type = await client.post("/analyze", json={"currentUrl": 123})
            missing = await client.post("/analyze", json={})
            url = "https://store.example/"
            too_many_links = await client.post(
                "/analyze",
                json={"currentUrl": url, "instagramLinks": ["https://a.example"] * 51},
            )
            link_too_long = await client.post(
                "/analyze",
                json={"currentUrl": url, "instagramLinks": ["x" * 501]},
            )
            links_wrong_type = await client.post(
                "/analyze", json={"currentUrl": url, "instagramLinks": [123]}
            )

        self.assertEqual(wrong_type.status_code, 422)
        self.assertEqual(missing.status_code, 422)
        self.assertEqual(too_many_links.status_code, 422)
        self.assertEqual(link_too_long.status_code, 422)
        self.assertEqual(links_wrong_type.status_code, 422)


if __name__ == "__main__":
    unittest.main()
