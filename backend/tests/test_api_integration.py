import unittest
from unittest.mock import AsyncMock, patch

import httpx

from backend.agent.tools.instagram import InstagramFindings
from backend.agent.tools.instagram_comments import (
    CommentFindings,
    InstagramComment,
)
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


class ApiIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def post_analyze(
        self,
        findings: RedditFindings,
        instagram: InstagramFindings | None = None,
        instagram_links: list[str] | None = None,
    ) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
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

    async def test_real_reddit_score_is_aggregated_with_mock_sources(self) -> None:
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
        self.assertEqual(site_analysis["riskScore"], 58)
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
        self.assertEqual(scoring["overallRisk"], 58)

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
