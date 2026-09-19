import unittest

import httpx

from backend.api.analysis import create_mock_analysis
from backend.api.app import app


class ApiIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def test_mock_scores_are_aggregated_through_the_complete_tree(self) -> None:
        response = create_mock_analysis("https://shop.example/products/widget")
        scoring = response.scoring

        self.assertEqual(response.store.domain, "shop.example")
        self.assertEqual(scoring.overall_risk, 69)
        self.assertEqual(scoring.coverage, 100)

        third_party, site_analysis = scoring.categories
        self.assertEqual(third_party.weight, 0.5)
        self.assertEqual(third_party.risk_score, 80)
        self.assertEqual(third_party.sources[0].id, "reddit")
        self.assertEqual(third_party.sources[0].weight, 1.0)

        self.assertEqual(site_analysis.weight, 0.5)
        self.assertEqual(site_analysis.risk_score, 58)
        self.assertEqual(
            [
                (source.id, source.weight, source.risk_score)
                for source in site_analysis.sources
            ],
            [("domain-age", 0.6, 50), ("gptzero", 0.4, 70)],
        )

    async def test_analyze_endpoint_returns_the_frontend_contract(self) -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/analyze",
                json={"currentUrl": "https://store.example/item"},
                headers={"Origin": "chrome-extension://integration-test"},
            )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")
        self.assertEqual(payload["store"]["domain"], "store.example")
        self.assertEqual(payload["scoring"]["overallRisk"], 69)
        self.assertEqual(len(payload["scoring"]["categories"]), 2)
        self.assertEqual(
            sum(
                len(category["sources"])
                for category in payload["scoring"]["categories"]
            ),
            3,
        )

    async def test_analyze_endpoint_validates_requests(self) -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post("/analyze", json={"currentUrl": 123})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
