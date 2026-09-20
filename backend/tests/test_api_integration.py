import unittest
from unittest.mock import AsyncMock, patch

import httpx

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
        ) as research:
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/analyze",
                    json=body,
                    headers={"Origin": "chrome-extension://integration-test"},
                )
        research.assert_awaited_once_with("https://store.example/item")
        return response

    async def test_real_reddit_score_is_aggregated_with_other_sources(self) -> None:
        response = await self.post_analyze(
            RedditFindings(found_any=True, posts=[critical_post()], risk_score=40)
        )
        payload = response.json()
        scoring = payload["scoring"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")
        self.assertEqual(payload["store"]["domain"], "store.example")
        # No reviews in the request, so gptzero - the only source in
        # site-analysis - never reports and the whole category is uncovered.
        self.assertEqual(scoring["coverage"], 50)
        self.assertEqual(scoring["overallRisk"], 40)  # Reddit alone

        third_party, site_analysis = scoring["categories"]
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

    async def test_no_posts_is_insufficient_data_not_safe(self) -> None:
        response = await self.post_analyze(RedditFindings(found_any=False))
        scoring = response.json()["scoring"]

        reddit = scoring["categories"][0]["sources"][0]
        self.assertEqual(reddit["status"], "insufficient-data")
        self.assertIsNone(reddit["riskScore"])
        self.assertIsNone(scoring["categories"][0]["riskScore"])
        # Neither source reported, so there is no score at all - which is the
        # point: an unexamined store is unknown, not safe.
        self.assertIsNone(scoring["overallRisk"])
        self.assertEqual(scoring["coverage"], 0)

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

        self.assertEqual(wrong_type.status_code, 422)
        self.assertEqual(missing.status_code, 422)


if __name__ == "__main__":
    unittest.main()
