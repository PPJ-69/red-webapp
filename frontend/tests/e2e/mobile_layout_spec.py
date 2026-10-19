from __future__ import annotations

import json
import unittest
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests


class MobileLayoutBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_mobile_layout_infinite_scroll_and_player_fit(self) -> None:
        items = [
            {
                "id": media_id,
                "title": f"Sample {media_id}",
                "duration": 12,
                "thumbnailUrl": None,
                "creator": {"id": "creator", "username": "sample"},
                "tags": ["sample"],
            }
            for media_id in ("one", "two", "three")
        ]
        requested_pages: list[int] = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 320, "height": 700})

                def search(route) -> None:
                    page_number = int(
                        parse_qs(urlsplit(route.request.url).query).get(
                            "page", ["1"]
                        )[0]
                    )
                    requested_pages.append(page_number)
                    page_items = items[:2] if page_number == 1 else [items[1], items[2]]
                    route.fulfill(
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "items": page_items,
                                "page": page_number,
                                "limit": 20,
                                "hasMore": page_number == 1,
                                "total": 3,
                            }
                        ),
                    )

                page.route("**/api/search?*", search)
                page.route(
                    "**/api/media/*/source?*",
                    lambda route: route.fulfill(
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "playbackUrl": "/api/stream/one?quality=auto",
                                "kind": "relay",
                                "requiresRelay": True,
                                "expiresAt": None,
                            }
                        ),
                    ),
                )
                page.route("**/api/stream/**", lambda route: route.abort())
                page.goto(
                    f"http://127.0.0.1:{self.web_port}/", wait_until="networkidle"
                )
                page.get_by_test_id("search-submit").click()
                expect(page.get_by_test_id("result-card")).to_have_count(2)
                self.assertEqual(
                    requested_pages,
                    [1],
                    page.locator("body").inner_text(),
                )
                expect(page.get_by_test_id("result-grid-sentinel")).to_be_visible()
                page.get_by_test_id("result-grid-sentinel").scroll_into_view_if_needed()
                expect(page.get_by_test_id("result-card")).to_have_count(3)
                self.assertEqual(requested_pages, [1, 2])

                for width in (320, 375, 768):
                    page.set_viewport_size({"width": width, "height": 700})
                    self.assertEqual(
                        page.evaluate(
                            """() => ({
                              viewport: window.innerWidth,
                              body: document.body.scrollWidth,
                              document: document.documentElement.scrollWidth,
                            })"""
                        ),
                        {
                            "viewport": width,
                            "body": width,
                            "document": width,
                        },
                        f"Horizontal overflow at viewport width {width}px.",
                    )

                page.set_viewport_size({"width": 320, "height": 700})
                page.get_by_test_id("result-card").first.locator(
                    "button.card-button"
                ).click()
                expect(page.get_by_test_id("player-overlay")).to_be_visible()
                expect(page.get_by_test_id("player-controls")).to_be_visible()
                expect(page.get_by_test_id("close-player")).to_be_visible()
                self.assertEqual(
                    page.evaluate(
                        """() => ({
                          viewport: window.innerWidth,
                          body: document.body.scrollWidth,
                          document: document.documentElement.scrollWidth,
                        })"""
                    ),
                    {"viewport": 320, "body": 320, "document": 320},
                    "The player overflows the 320px viewport.",
                )
            finally:
                browser.close()


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(MobileLayoutBrowserTests)


if __name__ == "__main__":
    unittest.main()
