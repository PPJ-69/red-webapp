from __future__ import annotations

import unittest

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests


class SearchBarBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_debounced_tag_suggestions_and_search_parameters(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                suggestion_queries: list[str] = []
                search_requests: list[dict[str, str | list[str]]] = []

                def suggest_tags(route) -> None:
                    query = route.request.url.split("q=", maxsplit=1)[-1]
                    suggestion_queries.append(query)
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body='["funny","cute"]',
                    )

                def search(route) -> None:
                    from urllib.parse import parse_qs, urlparse

                    search_requests.append(
                        parse_qs(urlparse(route.request.url).query)
                    )
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body='{"items":[],"page":1,"limit":50,"hasMore":false}',
                    )

                page.route("**/api/tags/suggest?*", suggest_tags)
                page.route("**/api/search?*", search)
                page.goto(
                    f"http://127.0.0.1:{self.web_port}/",
                    wait_until="networkidle",
                )
                query = page.get_by_test_id("search-query")
                query.fill("cats #fu")
                expect(page.get_by_test_id("tag-suggestions")).to_be_visible()
                expect(page.get_by_test_id("tag-suggestion").first).to_have_text(
                    "#funny"
                )
                self.assertEqual(suggestion_queries, ["fu"])
                page.get_by_test_id("tag-suggestion").first.click()
                expect(page.get_by_test_id("search-query")).to_have_value(
                    "cats #funny "
                )
                expect(page.get_by_test_id("query-chips")).to_contain_text("#funny")

                query.fill("cats #funny @alice")
                page.get_by_test_id("search-order").select_option("score")
                page.get_by_test_id("search-limit").fill("50")
                page.get_by_test_id("search-limit").dispatch_event("change")
                page.get_by_test_id("search-submit").click()

                expect(page.get_by_test_id("search-status")).to_have_text(
                    "0 results loaded."
                )
                self.assertEqual(
                    search_requests,
                    [
                        {
                            "q": ["cats @alice"],
                            "tags": ["funny"],
                            "mode": ["search"],
                            "order": ["score"],
                            "page": ["1"],
                            "limit": ["50"],
                        }
                    ],
                )
                video = page.get_by_test_id("media-player")
                video.evaluate("element => element.pause()")
                query.focus()
                query.press("Space")
                expect(query).to_have_value("cats #funny @alice ")
                self.assertTrue(video.evaluate("element => element.paused"))
            finally:
                browser.close()


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(SearchBarBrowserTests)


if __name__ == "__main__":
    unittest.main()
