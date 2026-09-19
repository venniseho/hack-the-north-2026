import unittest
from unittest.mock import AsyncMock, patch

from backend.agent import agent
from backend.agent.tools.reddit import RedditFindings, RedditPost, score_reddit


def post(severity: str) -> RedditPost:
    return RedditPost(
        url="https://www.reddit.com/r/x/comments/abc123/t/",
        title="t",
        quote="q",
        severity=severity,  # type: ignore[arg-type]
    )


class RedditRiskScoreTests(unittest.TestCase):
    def test_score_is_risk_not_trust(self) -> None:
        self.assertEqual(score_reddit([]), 0)
        self.assertEqual(score_reddit([post("critical")]), 40)
        self.assertEqual(score_reddit([post("minor")]), 3)

    def test_positive_posts_lower_risk(self) -> None:
        self.assertEqual(score_reddit([post("critical"), post("positive")]), 36)

    def test_post_order_does_not_matter(self) -> None:
        posts = [post("major"), post("positive"), post("moderate")]
        self.assertEqual(score_reddit(posts), score_reddit(posts[::-1]))


class HostnameTests(unittest.TestCase):
    def test_domain_drops_www_path_and_tracking_params(self) -> None:
        self.assertEqual(
            agent.domain_from_url("https://www.azazie.ca/p/dress?srsltid=abc"),
            "azazie.ca",
        )

    def test_brand_from_domain(self) -> None:
        self.assertEqual(agent.brand_from_domain("azazie.ca"), "Azazie")
        self.assertEqual(agent.brand_from_domain("shop.example.com"), "Example")
        self.assertEqual(agent.brand_from_domain("cool-gadgets.co.uk"), "Cool Gadgets")


class ResearchStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        agent._cache.clear()

    async def test_failures_come_back_as_error_findings(self) -> None:
        with patch.object(agent, "get_client", side_effect=RuntimeError("no key")):
            findings = await agent.research_store("https://store.example")

        self.assertIn("no key", findings.error or "")
        self.assertFalse(findings.found_any)

    async def test_successful_results_are_cached_by_domain(self) -> None:
        result = RedditFindings(found_any=True, posts=[post("minor")], risk_score=3)
        research = AsyncMock(return_value=result)
        with patch.object(agent, "get_client"), patch.object(
            agent, "research_reddit", research
        ):
            first = await agent.research_store("https://www.store.example/a")
            second = await agent.research_store("https://store.example/b?x=1")

        self.assertIs(first, second)
        research.assert_awaited_once()

    async def test_errors_are_not_cached(self) -> None:
        research = AsyncMock(
            return_value=RedditFindings(found_any=False, error="empty research response")
        )
        with patch.object(agent, "get_client"), patch.object(
            agent, "research_reddit", research
        ):
            await agent.research_store("https://store.example")
            await agent.research_store("https://store.example")

        self.assertEqual(research.await_count, 2)


if __name__ == "__main__":
    unittest.main()
