from __future__ import annotations

import json
import unittest

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests


class KeyboardNavigationBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_keyboard_navigation_help_and_focus_restoration(self) -> None:
        results = {
            "items": [
                {
                    "id": media_id,
                    "title": title,
                    "duration": 12,
                    "thumbnailUrl": None,
                    "creator": {"id": "creator", "username": "sample"},
                    "tags": [],
                }
                for media_id, title in (
                    ("one", "First item"),
                    ("two", "Second item"),
                    ("three", "Third item"),
                )
            ],
            "page": 1,
            "limit": 20,
            "hasMore": False,
            "total": 3,
        }

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.route(
                    "**/api/search?*",
                    lambda route: route.fulfill(
                        content_type="application/json", body=json.dumps(results)
                    ),
                )
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
                page.route(
                    "**/api/stream/**",
                    lambda route: route.fulfill(
                        status=404,
                        content_type="application/json",
                        body='{"category":"not_found","message":"Unavailable"}',
                    ),
                )
                page.goto(
                    f"http://127.0.0.1:{self.web_port}/", wait_until="networkidle"
                )
                page.get_by_test_id("search-submit").click()
                expect(page.get_by_test_id("result-card")).to_have_count(3)
                opener = page.get_by_test_id("result-card").first.locator(
                    "button.card-button"
                )
                opener.click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "First item"
                )

                page.evaluate("document.activeElement?.blur()")
                page.keyboard.press("n")
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Second item"
                )
                page.keyboard.press("p")
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "First item"
                )
                page.keyboard.press("v")
                expect(
                    page.get_by_test_id("player-overlay").get_by_test_id(
                        "favorite-one"
                    )
                ).to_have_attribute("aria-pressed", "true")

                page.keyboard.press("?")
                dialog = page.get_by_role("dialog", name="Keyboard shortcuts")
                expect(dialog).to_be_visible()
                expect(dialog.get_by_role("button", name="Close")).to_be_focused()
                page.keyboard.press("Escape")
                expect(dialog).to_have_count(0)
                expect(page.get_by_test_id("player-overlay")).to_be_visible()

                page.keyboard.press("g")
                expect(page.get_by_test_id("player-overlay")).to_have_count(0)
                expect(opener).to_be_focused()
            finally:
                browser.close()


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(KeyboardNavigationBrowserTests)


if __name__ == "__main__":
    unittest.main()
