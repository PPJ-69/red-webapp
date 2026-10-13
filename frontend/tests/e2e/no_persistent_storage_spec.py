from __future__ import annotations

import json
import unittest

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests, ROOT


STORAGE_MONITOR = (
    ROOT / "tools" / "compliance" / "browser_storage_check" / "storage_monitor.js"
)


class NoPersistentStorageBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_session_state_is_ram_only_and_empty_after_browser_restart(self) -> None:
        results = {
            "items": [
                {
                    "id": "one",
                    "title": "Sample item",
                    "duration": 12,
                    "thumbnailUrl": None,
                    "creator": {"id": "creator", "username": "sample"},
                    "tags": [],
                }
            ],
            "page": 1,
            "limit": 20,
            "hasMore": False,
            "total": 1,
        }

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                first_context = browser.new_context()
                first_context.add_init_script(path=str(STORAGE_MONITOR))
                first_page = first_context.new_page()
                first_page.route(
                    "**/api/search?*",
                    lambda route: route.fulfill(
                        content_type="application/json", body=json.dumps(results)
                    ),
                )
                first_page.goto(
                    f"http://127.0.0.1:{self.web_port}/", wait_until="networkidle"
                )
                first_page.get_by_test_id("search-submit").click()
                favorite = first_page.get_by_test_id("favorite-one")
                expect(favorite).to_be_visible()
                favorite.click()
                expect(favorite).to_have_attribute("aria-pressed", "true")

                search = first_page.get_by_test_id("search-query")
                search.fill("restart marker")
                first_page.get_by_test_id("search-submit").click()
                first_page.get_by_test_id("save-search").click()
                expect(first_page.get_by_test_id("saved-search")).to_contain_text(
                    "restart marker"
                )
                expect(first_page.get_by_test_id("search-history")).to_contain_text(
                    "restart marker"
                )
                self.assertEqual(
                    first_page.evaluate("window.__complianceStorageViolations"), []
                )
                self.assertEqual(first_context.cookies(), [])
                first_context.close()
            finally:
                browser.close()

            restarted_browser = playwright.chromium.launch()
            try:
                restarted_context = restarted_browser.new_context()
                restarted_context.add_init_script(path=str(STORAGE_MONITOR))
                restarted_page = restarted_context.new_page()
                restarted_page.route(
                    "**/api/search?*",
                    lambda route: route.fulfill(
                        content_type="application/json", body=json.dumps(results)
                    ),
                )
                restarted_page.goto(
                    f"http://127.0.0.1:{self.web_port}/", wait_until="networkidle"
                )
                expect(restarted_page.get_by_test_id("search-history")).to_have_count(0)
                expect(restarted_page.get_by_test_id("saved-searches")).to_have_count(0)
                restarted_page.get_by_test_id("navigate-favorites").click()
                expect(
                    restarted_page.get_by_test_id("favorites-panel")
                ).to_contain_text("No favorites yet.")
                self.assertEqual(
                    restarted_page.evaluate(
                        "window.__complianceStorageViolations"
                    ),
                    [],
                )
                self.assertEqual(restarted_context.cookies(), [])
                restarted_context.close()
            finally:
                restarted_browser.close()


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(NoPersistentStorageBrowserTests)


if __name__ == "__main__":
    unittest.main()
