import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from backend.agent import agent
from backend.agent.tools import instagram
from backend.agent.tools.instagram import InstagramFindings, extract_handle
from backend.agent.tools.instagram_comments import CommentFindings


class ExtractHandleTests(unittest.TestCase):
    def test_finds_footer_link(self) -> None:
        html = '<a href="https://www.instagram.com/azazie/">Follow us</a>'
        self.assertEqual(extract_handle(html), "azazie")

    def test_finds_link_in_escaped_json(self) -> None:
        html = r'{"sameAs":["https:\/\/www.instagram.com\/Cool.Shop_1\/"]}'
        self.assertEqual(extract_handle(html), "cool.shop_1")

    def test_ignores_non_profile_paths(self) -> None:
        html = (
            '<a href="https://instagram.com/p/AbC123/">post</a>'
            '<a href="https://instagram.com/explore/tags/x/">tag</a>'
            '<a href="https://www.instagram.com/shop">us</a>'
        )
        self.assertEqual(extract_handle(html), "shop")

    def test_most_linked_handle_wins(self) -> None:
        html = (
            '<a href="instagram.com/other">a</a>'
            '<a href="instagram.com/shop">b</a>'
            '<a href="instagram.com/shop/">c</a>'
        )
        self.assertEqual(extract_handle(html), "shop")

    def test_no_link_returns_none(self) -> None:
        self.assertIsNone(extract_handle("<html>facebook.com/shop</html>"))


class FakeApify:
    """Stands in for ApifyClientAsync; each resultsType gets its own dataset."""

    def __init__(
        self,
        details: list[dict],
        posts: list[dict] | None = None,
        search: list[dict] | None = None,
        statuses: dict[str, str] | None = None,
    ) -> None:
        self._datasets = {
            "details": details,
            "posts": posts or [],
            "search": search or [],
        }
        self._statuses = statuses or {}  # per dataset; default SUCCEEDED
        self.inputs: list[dict] = []

    def actor(self, actor_id: str) -> SimpleNamespace:
        async def call(*, run_input: dict, **_: object) -> SimpleNamespace:
            self.inputs.append(run_input)
            # A search run also sets resultsType="details", so check it first.
            dataset = "search" if "search" in run_input else run_input["resultsType"]
            return SimpleNamespace(
                status=self._statuses.get(dataset, "SUCCEEDED"),
                default_dataset_id=dataset,
            )

        return SimpleNamespace(call=call)

    def dataset(self, dataset_id: str) -> SimpleNamespace:
        async def list_items(*, limit: int) -> SimpleNamespace:
            return SimpleNamespace(items=self._datasets[dataset_id][:limit])

        return SimpleNamespace(list_items=list_items)


def profile(followers: int, **extra: object) -> list[dict]:
    return [{"username": "shop", "followersCount": followers, **extra}]


def post_with_comments(url: str, comments: list[tuple[str, str]]) -> dict:
    return {
        "url": url,
        "latestComments": [{"ownerUsername": o, "text": t} for o, t in comments],
    }


def twelve_comments_three_angry() -> list[dict]:
    calm = [(f"fan{i}", f"lovely piece number {i}") for i in range(9)]
    angry = [(n, "Total scam, never received it") for n in ("a", "b", "c")]
    return [post_with_comments("https://www.instagram.com/p/one/", calm + angry)]


class ResearchInstagramTests(unittest.IsolatedAsyncioTestCase):
    async def research(self, fake: FakeApify) -> InstagramFindings:
        with patch.object(
            instagram, "find_instagram_handle", AsyncMock(return_value="shop")
        ):
            return await instagram.research_instagram(
                fake, "https://shop.example"  # type: ignore[arg-type]
            )

    async def test_comments_on_posts_are_analyzed(self) -> None:
        fake = FakeApify(profile(5_000, verified=True), twelve_comments_three_angry())
        findings = await self.research(fake)

        self.assertEqual(findings.handle, "shop")
        self.assertEqual(findings.followers, 5_000)
        self.assertTrue(findings.verified)
        self.assertEqual(findings.comments.analyzed, 12)
        self.assertEqual(len(findings.comments.complaints), 3)
        self.assertEqual(findings.comments.risk_score, 95)
        self.assertEqual({i["resultsType"] for i in fake.inputs}, {"details", "posts"})
        self.assertTrue(
            all(i["directUrls"] == ["https://www.instagram.com/shop/"] for i in fake.inputs)
        )
        posts_run = next(i for i in fake.inputs if i["resultsType"] == "posts")
        self.assertEqual(posts_run["resultsLimit"], instagram.POSTS_LIMIT)

    async def test_a_failed_posts_run_only_errors_the_comments(self) -> None:
        class PostsFail(FakeApify):
            def actor(self, actor_id: str) -> SimpleNamespace:
                inner = super().actor(actor_id)

                async def call(*, run_input: dict, **kwargs: object) -> SimpleNamespace:
                    if run_input["resultsType"] == "posts":
                        raise RuntimeError("posts blew up")
                    return await inner.call(run_input=run_input, **kwargs)

                return SimpleNamespace(call=call)

        findings = await self.research(PostsFail(profile(5_000)))

        self.assertIsNone(findings.error)
        self.assertEqual(findings.handle, "shop")
        self.assertIn("posts blew up", findings.comments.error or "")

    async def test_a_timed_out_posts_run_still_scores_its_partial_comments(self) -> None:
        # The run stalls on its last posts after saving most of them.
        fake = FakeApify(
            profile(5_000),
            twelve_comments_three_angry(),
            statuses={"posts": "TIMED-OUT"},
        )
        findings = await self.research(fake)

        self.assertIsNone(findings.comments.error)
        self.assertEqual(findings.comments.analyzed, 12)
        self.assertEqual(findings.comments.risk_score, 95)

    async def test_a_timed_out_posts_run_with_nothing_saved_errors_the_comments(self) -> None:
        fake = FakeApify(profile(5_000), statuses={"posts": "TIMED-OUT"})
        findings = await self.research(fake)

        self.assertIn("timed out before returning", findings.comments.error or "")

    async def test_a_tiny_account_still_gets_its_comments_scored(self) -> None:
        fake = FakeApify(profile(12), twelve_comments_three_angry())
        findings = await self.research(fake)

        self.assertEqual(findings.followers, 12)
        self.assertEqual(findings.comments.risk_score, 95)

    async def test_private_and_missing_accounts_skip_comments_too(self) -> None:
        private = await self.research(
            FakeApify(profile(5_000, private=True), twelve_comments_three_angry())
        )
        missing = await self.research(FakeApify([{"error": "not_found"}]))

        self.assertIn("private", private.comments.skip_reason or "")
        self.assertIsNone(private.comments.risk_score)
        self.assertIn("not found", missing.comments.skip_reason or "")

    async def test_no_link_skips_comments_too(self) -> None:
        with patch.object(
            instagram, "find_instagram_handle", AsyncMock(return_value=None)
        ):
            findings = await instagram.research_instagram(
                FakeApify([]), "https://shop.example"  # type: ignore[arg-type]
            )

        self.assertIsNone(findings.error)
        self.assertIn("no Instagram link", findings.comments.skip_reason or "")

    async def test_failed_actor_run_raises(self) -> None:
        class FailingApify(FakeApify):
            def actor(self, actor_id: str) -> SimpleNamespace:
                async def call(**_: object) -> SimpleNamespace:
                    return SimpleNamespace(status="FAILED", default_dataset_id="x")

                return SimpleNamespace(call=call)

        with self.assertRaises(RuntimeError):
            await self.research(FailingApify([]))


def candidate(username: str, followers: int, website: str | None = None) -> dict:
    item: dict = {"username": username, "followersCount": followers}
    if website:
        item["externalUrl"] = website
        item["externalUrls"] = [{"url": website}]
    return item


def blocked() -> AsyncMock:
    """A homepage fetch that gets 403 Forbidden, as bot-protected stores do."""
    request = httpx.Request("GET", "https://shop.example/")
    error = httpx.HTTPStatusError(
        "403 Forbidden", request=request, response=httpx.Response(403, request=request)
    )
    return AsyncMock(side_effect=error)


class SiteMatchingTests(unittest.TestCase):
    def test_site_key_ignores_www_and_subdomains(self) -> None:
        self.assertEqual(instagram._site_key("www.brand.com"), "brand.com")
        self.assertEqual(instagram._site_key("shop.brand.com"), "brand.com")
        self.assertEqual(instagram._site_key("www.shop.brand.co.uk"), "brand.co.uk")

    def test_links_to_site_reads_both_link_fields_and_bare_hosts(self) -> None:
        self.assertTrue(
            instagram._links_to_site(candidate("x", 1, "http://www.brand.com"), "brand.com")
        )
        self.assertTrue(
            instagram._links_to_site(
                {"externalUrls": [{"url": "https://linktr.ee/x"}, {"url": "brand.com/shop"}]},
                "brand.com",
            )
        )

    def test_website_match_tells_store_other_site_and_no_evidence_apart(self) -> None:
        match = instagram._website_match
        self.assertIs(match(candidate("x", 1, "https://shop.brand.com"), "brand.com"), True)
        self.assertIs(match(candidate("x", 1, "https://nike.com"), "brand.com"), False)
        # A store link among others still counts as a match
        both = {"externalUrls": [{"url": "https://nike.com"}, {"url": "brand.com"}]}
        self.assertIs(match(both, "brand.com"), True)
        # No website, link-in-bio pages and social links prove nothing either way
        self.assertIsNone(match(candidate("x", 1), "brand.com"))
        self.assertIsNone(match(candidate("x", 1, "https://linktr.ee/brand"), "brand.com"))
        self.assertIsNone(match(candidate("x", 1, "https://wa.me/123456"), "brand.com"))

    def test_lookalike_and_third_party_links_do_not_match(self) -> None:
        for website in ("https://notbrand.com", "https://linktr.ee/brand", None):
            with self.subTest(website=website):
                self.assertFalse(
                    instagram._links_to_site(candidate("x", 1, website), "brand.com")
                )


class ResearchInstagramFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def research(
        self, fake: FakeApify, homepage: AsyncMock, brand: str | None = "Shop"
    ) -> InstagramFindings:
        with patch.object(instagram, "find_instagram_handle", homepage):
            return await instagram.research_instagram(
                fake, "https://shop.example/item", brand=brand  # type: ignore[arg-type]
            )

    async def test_blocked_homepage_falls_back_to_a_verified_search_hit(self) -> None:
        fake = FakeApify(
            [],
            twelve_comments_three_angry(),
            search=[
                candidate("shopfashion", 900),  # lookalike, no website
                candidate("shop", 50_000, "https://www.shop.example"),
            ],
        )
        findings = await self.research(fake, blocked())

        self.assertIsNone(findings.error)
        self.assertEqual(findings.handle, "shop")
        self.assertEqual(findings.followers, 50_000)  # from the search hit
        self.assertEqual(findings.comments.risk_score, 95)
        search = next(i for i in fake.inputs if "search" in i)
        self.assertEqual(search["search"], "Shop")
        self.assertEqual(search["searchType"], "user")
        # The search already returned the profile, so there's no details run.
        other = sorted(i["resultsType"] for i in fake.inputs if "search" not in i)
        self.assertEqual(other, ["posts"])

    async def test_lookalike_accounts_are_never_scored(self) -> None:
        fake = FakeApify(
            [],
            search=[
                candidate("shopfashion", 900),
                candidate("shop_fans", 4_000, "https://notshop.example"),
            ],
        )
        findings = await self.research(fake, blocked())

        self.assertIsNone(findings.error)
        self.assertIsNone(findings.handle)
        skip_reason = findings.comments.skip_reason or ""
        self.assertIn("couldn't read the store's homepage", skip_reason)
        self.assertIn("no Instagram profile", skip_reason)
        self.assertEqual(len(fake.inputs), 1)  # only the search ran

    async def test_a_timed_out_search_still_uses_its_partial_results(self) -> None:
        # The run stalls on its last profile after the useful ones are saved.
        fake = FakeApify(
            [],
            twelve_comments_three_angry(),
            search=[
                candidate("shopfashion", 900),
                candidate("shop", 50_000, "https://shop.example"),
            ],
            statuses={"search": "TIMED-OUT"},
        )
        findings = await self.research(fake, blocked())

        self.assertIsNone(findings.error)
        self.assertEqual(findings.handle, "shop")

    async def test_a_timed_out_search_with_nothing_saved_is_a_failure(self) -> None:
        fake = FakeApify([], statuses={"search": "TIMED-OUT"})

        with self.assertRaises(RuntimeError):
            await self.research(fake, blocked())

    async def test_the_biggest_matching_profile_wins(self) -> None:
        fake = FakeApify(
            [],
            search=[
                candidate("shop_old", 300, "https://shop.example"),
                candidate("shop", 8_000, "https://shop.example"),
            ],
        )
        findings = await self.research(fake, blocked())

        self.assertEqual(findings.handle, "shop")

    async def test_a_homepage_without_a_link_also_tries_search(self) -> None:
        fake = FakeApify(
            [], search=[candidate("shop", 8_000, "https://shop.example")]
        )
        findings = await self.research(fake, AsyncMock(return_value=None))

        self.assertEqual(findings.handle, "shop")

    async def test_failed_search_after_a_readable_homepage_is_just_no_link(self) -> None:
        class SearchFails(FakeApify):
            def actor(self, actor_id: str) -> SimpleNamespace:
                async def call(*, run_input: dict, **_: object) -> SimpleNamespace:
                    raise RuntimeError("search timed out")

                return SimpleNamespace(call=call)

        findings = await self.research(
            SearchFails([]), AsyncMock(return_value=None)
        )

        self.assertIsNone(findings.error)
        self.assertIn("no Instagram link", findings.comments.skip_reason or "")

    async def test_blocked_homepage_and_failed_search_is_a_real_failure(self) -> None:
        class SearchFails(FakeApify):
            def actor(self, actor_id: str) -> SimpleNamespace:
                async def call(*, run_input: dict, **_: object) -> SimpleNamespace:
                    raise RuntimeError("search timed out")

                return SimpleNamespace(call=call)

        with self.assertRaises(RuntimeError):
            await self.research(SearchFails([]), blocked())

    async def test_without_a_brand_a_blocked_homepage_is_just_skipped(self) -> None:
        fake = FakeApify([])
        findings = await self.research(fake, blocked(), brand=None)

        self.assertEqual(
            findings.comments.skip_reason, "couldn't read the store's homepage"
        )
        self.assertEqual(fake.inputs, [])  # nothing was searched


class ResearchInstagramPageLinksTests(unittest.IsolatedAsyncioTestCase):
    async def research(
        self,
        fake: FakeApify,
        homepage: AsyncMock,
        page_links: list[str],
        brand: str | None = "Shop",
    ) -> InstagramFindings:
        with patch.object(instagram, "find_instagram_handle", homepage):
            return await instagram.research_instagram(
                fake,  # type: ignore[arg-type]
                "https://shop.example/item",
                brand=brand,
                page_links=page_links,
            )

    async def test_links_from_the_page_skip_the_homepage_and_search(self) -> None:
        homepage = AsyncMock(return_value="wrong")
        fake = FakeApify(profile(5_000), twelve_comments_three_angry())
        findings = await self.research(
            fake, homepage, ["https://www.instagram.com/shop/?hl=en"]
        )

        self.assertEqual(findings.handle, "shop")
        self.assertEqual(findings.comments.risk_score, 95)
        homepage.assert_not_awaited()
        self.assertFalse(any("search" in i for i in fake.inputs))

    async def test_links_that_are_not_profiles_fall_back_to_the_homepage(self) -> None:
        homepage = AsyncMock(return_value="shop")
        fake = FakeApify(profile(5_000))
        findings = await self.research(
            fake,
            homepage,
            ["https://www.instagram.com/p/AbC123/", "https://www.instagram.com/explore/"],
        )

        self.assertEqual(findings.handle, "shop")
        homepage.assert_awaited_once()

    async def test_a_blocked_homepage_is_not_needed_when_the_page_gave_a_link(self) -> None:
        # This is the lightinthebox case: the server gets a 403, the browser doesn't.
        fake = FakeApify(profile(5_000), twelve_comments_three_angry())
        findings = await self.research(
            fake, blocked(), ["https://www.instagram.com/shop/"]
        )

        self.assertIsNone(findings.error)
        self.assertEqual(findings.handle, "shop")


class WebsiteLinkBackTests(unittest.IsolatedAsyncioTestCase):
    async def research(self, fake: FakeApify) -> InstagramFindings:
        with patch.object(
            instagram, "find_instagram_handle", AsyncMock(return_value="shop")
        ):
            return await instagram.research_instagram(
                fake, "https://www.shop.example/item"  # type: ignore[arg-type]
            )

    async def test_a_profile_linking_to_the_store_is_verified(self) -> None:
        fake = FakeApify(
            profile(5_000, externalUrl="http://shop.example/"),
            twelve_comments_three_angry(),
        )
        findings = await self.research(fake)

        self.assertIs(findings.website_match, True)
        self.assertEqual(findings.comments.risk_score, 95)  # scored normally

    async def test_a_profile_linking_elsewhere_is_not_scored(self) -> None:
        fake = FakeApify(
            profile(5_000, externalUrl="https://nike.com"),
            twelve_comments_three_angry(),
        )
        findings = await self.research(fake)

        self.assertIsNone(findings.error)
        self.assertEqual(findings.handle, "shop")
        self.assertIn("nike.com", findings.comments.skip_reason or "")
        self.assertIn("not this store", findings.comments.skip_reason or "")
        self.assertIsNone(findings.comments.risk_score)
        self.assertEqual(findings.comments.analyzed, 0)

    async def test_no_website_or_link_in_bio_is_accepted_unverified(self) -> None:
        for extra in ({}, {"externalUrl": "https://linktr.ee/shop"}):
            with self.subTest(extra=extra):
                findings = await self.research(
                    FakeApify(profile(5_000, **extra), twelve_comments_three_angry())
                )

                self.assertIsNone(findings.website_match)
                self.assertEqual(findings.comments.risk_score, 95)

    async def test_the_borrowed_account_check_covers_page_links_too(self) -> None:
        with patch.object(
            instagram, "find_instagram_handle", AsyncMock(return_value=None)
        ):
            findings = await instagram.research_instagram(
                FakeApify(profile(9_000_000, externalUrl="https://nike.com")),  # type: ignore[arg-type]
                "https://shop.example/",
                page_links=["https://www.instagram.com/nike/"],
            )

        self.assertIsNone(findings.comments.risk_score)
        self.assertIn("nike.com", findings.comments.skip_reason or "")


class ResearchStoreInstagramTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        agent._instagram_cache.clear()

    async def test_failures_come_back_as_error_findings(self) -> None:
        with patch.object(agent, "get_apify_client", side_effect=RuntimeError("no token")):
            findings = await agent.research_store_instagram("https://store.example")

        self.assertIn("no token", findings.error or "")

    async def test_successful_results_are_cached_by_domain(self) -> None:
        research = AsyncMock(return_value=InstagramFindings(handle="store"))
        with patch.object(agent, "get_apify_client"), patch.object(
            agent, "research_instagram", research
        ):
            first = await agent.research_store_instagram("https://www.store.example/a")
            second = await agent.research_store_instagram("https://store.example/b?x=1")

        self.assertIs(first, second)
        research.assert_awaited_once()

    async def test_page_links_are_passed_to_the_research(self) -> None:
        research = AsyncMock(return_value=InstagramFindings(handle="store"))
        links = ["https://www.instagram.com/store/"]
        with patch.object(agent, "get_apify_client"), patch.object(
            agent, "research_instagram", research
        ):
            await agent.research_store_instagram("https://www.store.example/a", links)

        research.assert_awaited_once()
        self.assertEqual(research.await_args.kwargs["page_links"], links)
        self.assertEqual(research.await_args.kwargs["brand"], "Store")

    async def test_unscored_results_are_cached_too(self) -> None:
        research = AsyncMock(
            return_value=InstagramFindings(comments=CommentFindings(skip_reason="no link"))
        )
        with patch.object(agent, "get_apify_client"), patch.object(
            agent, "research_instagram", research
        ):
            await agent.research_store_instagram("https://store.example")
            await agent.research_store_instagram("https://store.example")

        research.assert_awaited_once()

    async def test_errors_are_not_cached(self) -> None:
        research = AsyncMock(side_effect=RuntimeError("apify down"))
        with patch.object(agent, "get_apify_client"), patch.object(
            agent, "research_instagram", research
        ):
            await agent.research_store_instagram("https://store.example")
            await agent.research_store_instagram("https://store.example")

        self.assertEqual(research.await_count, 2)


if __name__ == "__main__":
    unittest.main()
