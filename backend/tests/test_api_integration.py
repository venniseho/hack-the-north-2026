import unittest
from unittest.mock import AsyncMock, patch

import httpx

from backend.agent.tools.reddit import RedditFindings, RedditPost
from backend.api.app import app


def critical_post() -> RedditPost:
    return RedditPost(
        url="https://www.reddit.com/r/Scams/comments/abc123/never_arrived/",
        title="Order never arrived",
        quote="Paid three weeks ago, nothing shipped.",
        severity="critical",
        subreddit="Scams",
        verified=True,
    )


class ApiIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def post_analyze(self, findings: RedditFindings) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        with patch(
            "backend.api.app.research_store", AsyncMock(return_value=findings)
        ) as research:
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/analyze",
                    json={"currentUrl": "https://store.example/item"},
                    headers={"Origin": "chrome-extension://integration-test"},
                )
        research.assert_awaited_once_with("https://store.example/item")
        return response

    async def test_real_reddit_score_is_aggregated_with_mock_sources(self) -> None:
        response = await self.post_analyze(
            RedditFindings(found_any=True, posts=[critical_post()], risk_score=40)
        )
        payload = response.json()
        scoring = payload["scoring"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")
        self.assertEqual(payload["store"]["domain"], "store.example")
        self.assertEqual(scoring["coverage"], 100)
        self.assertEqual(scoring["overallRisk"], 49)  # mean of 40 and 58

        third_party, site_analysis = scoring["categories"]
        self.assertEqual(third_party["riskScore"], 40)
        reddit = third_party["sources"][0]
        self.assertEqual(reddit["id"], "reddit")
        self.assertEqual(reddit["status"], "available")
        self.assertEqual(reddit["findings"][0]["ruleId"], "REDDIT_CRITICAL")
        self.assertEqual(
            reddit["findings"][0]["metadata"]["url"], critical_post().url
        )
        self.assertEqual(site_analysis["riskScore"], 58)

    async def test_no_posts_is_insufficient_data_not_safe(self) -> None:
        response = await self.post_analyze(RedditFindings(found_any=False))
        scoring = response.json()["scoring"]

        reddit = scoring["categories"][0]["sources"][0]
        self.assertEqual(reddit["status"], "insufficient-data")
        self.assertIsNone(reddit["riskScore"])
        self.assertIsNone(scoring["categories"][0]["riskScore"])
        self.assertEqual(scoring["overallRisk"], 58)  # site analysis only
        self.assertEqual(scoring["coverage"], 50)

    async def test_research_failure_degrades_only_the_reddit_source(self) -> None:
        response = await self.post_analyze(
            RedditFindings(found_any=False, error="research timed out after 45s")
        )
        scoring = response.json()["scoring"]

        self.assertEqual(response.status_code, 200)
        reddit = scoring["categories"][0]["sources"][0]
        self.assertEqual(reddit["status"], "error")
        self.assertEqual(reddit["metadata"]["error"], "research timed out after 45s")
        self.assertEqual(scoring["overallRisk"], 58)

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
