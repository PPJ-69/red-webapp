from __future__ import annotations

import json
import unittest

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests


class BrowsePlayFlowBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_search_open_navigate_close_and_creator_search(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 500})
                search_requests: list[str] = []
                results = {
                    "items": [
                        {
                            "id": media_id,
                            "title": title,
                            "duration": 13,
                            "thumbnailUrl": "https://images.example.invalid/thumb.jpg",
                            "creator": {
                                "id": "creator-id",
                                "username": "sample",
                                "displayName": "Sample creator",
                            },
                            "tags": ["featured"],
                        }
                        for media_id, title in (
                            ("sample-media", "Sample media"),
                            ("sample-media-two", "Second sample"),
                            ("sample-media-failure", "Unavailable sample"),
                        )
                    ],
                    "page": 1,
                    "limit": 20,
                    "hasMore": False,
                    "total": 3,
                }

                def search(route) -> None:
                    from urllib.parse import parse_qs, urlsplit

                    query = parse_qs(urlsplit(route.request.url).query)
                    search_requests.append(query.get("q", [""])[0])
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(results),
                    )

                def source(route) -> None:
                    media_id = route.request.url.split("/api/media/", 1)[1].split(
                        "/source", 1
                    )[0]
                    if media_id == "sample-media-failure":
                        route.fulfill(
                            status=404,
                            content_type="application/json",
                            body=json.dumps(
                                {
                                    "category": "not_found",
                                    "message": "Missing media.",
                                    "correlationId": "browse-play-test",
                                }
                            ),
                        )
                        return
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "playbackUrl": "/api/stream/sample-media?quality=auto",
                                "kind": "relay",
                                "requiresRelay": True,
                                "expiresAt": None,
                            }
                        ),
                    )

                page.route("**/api/search?*", search)
                page.route("**/api/media/*/source?*", source)
                page.route(
                    "**/api/creator/sample",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "id": "creator-id",
                                "username": "sample",
                                "displayName": "Sample creator",
                            }
                        ),
                    ),
                )
                page.goto(
                    f"http://127.0.0.1:{self.web_port}/",
                    wait_until="networkidle",
                )
                page.get_by_test_id("search-submit").click()
                expect(page.get_by_test_id("result-card")).to_have_count(3)

                page.evaluate("window.scrollTo(0, 250)")
                page.get_by_test_id("result-card").nth(1).locator(
                    "button.card-button"
                ).click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Second sample"
                )
                expect(page.get_by_test_id("thumbnail-sample-media-two")).to_have_attribute(
                    "aria-current", "true"
                )
                page.get_by_test_id("previous-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Sample media"
                )
                page.get_by_test_id("next-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Second sample"
                )

                page.get_by_test_id("creator-link").click()
                expect(page.get_by_test_id("creator-panel")).to_contain_text(
                    "Sample creator"
                )
                page.get_by_test_id("creator-search").click()
                expect(page.get_by_test_id("search-query")).to_have_value("@sample")
                expect(page.get_by_test_id("player-overlay")).to_have_count(0)
                self.assertEqual(search_requests[-1], "@sample")

                expect(page.get_by_test_id("result-card")).to_have_count(3)
                page.evaluate("window.scrollTo(0, 375)")
                saved_position = page.evaluate("window.scrollY")
                page.get_by_test_id("result-card").nth(2).locator(
                    "button.card-button"
                ).click()
                expect(
                    page.get_by_test_id("player-error").get_by_role(
                        "heading", name="Unavailable"
                    )
                ).to_be_visible()
                page.get_by_test_id("close-player").click()
                expect(page.get_by_test_id("result-grid")).to_be_visible()
                self.assertEqual(page.evaluate("window.scrollY"), saved_position)
                expect(page.get_by_test_id("result-card")).to_have_count(3)
            finally:
                browser.close()


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(BrowsePlayFlowBrowserTests)


if __name__ == "__main__":
    unittest.main()
