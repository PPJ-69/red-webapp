from __future__ import annotations

import json
import unittest

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests


class MetadataXSSBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_hostile_metadata_is_rendered_as_inert_text(self) -> None:
        hostile = (
            '<img src="x" onerror="window.__metadataXss = true">'
            '<script>window.__metadataXss = true</script>'
        )
        results = {
            "items": [
                {
                    "id": "hostile-media",
                    "title": hostile,
                    "description": hostile,
                    "tags": [hostile],
                    "creator": {
                        "id": "hostile-creator",
                        "username": "hostile",
                        "displayName": hostile,
                    },
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
                page = browser.new_page()
                page.add_init_script("window.__metadataXss = false;")
                page.route(
                    "**/api/search?*",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(results),
                    ),
                )
                page.route(
                    "**/api/media/hostile-media/source**",
                    lambda route: route.fulfill(
                        status=404,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "category": "not_found",
                                "message": "Missing media.",
                                "correlationId": "xss-test",
                            }
                        ),
                    ),
                )
                response = page.goto(
                    f"http://127.0.0.1:{self.web_port}/",
                    wait_until="networkidle",
                )
                self.assertIsNotNone(response)
                self.assertEqual(
                    response.headers.get("x-content-type-options"), "nosniff"
                )
                csp = response.headers.get("content-security-policy", "")
                self.assertIn("script-src 'self'", csp)
                self.assertIn("frame-ancestors 'none'", csp)

                page.get_by_test_id("search-submit").click()
                result_card = page.get_by_test_id("result-card")
                expect(result_card).to_contain_text(hostile)
                result_card.locator("button.card-button").click()
                expect(page.get_by_test_id("media-info")).to_contain_text(hostile)
                self.assertEqual(page.locator("img[src='x']").count(), 0)
                self.assertEqual(page.evaluate("window.__metadataXss"), False)
            finally:
                browser.close()


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(MetadataXSSBrowserTests)


if __name__ == "__main__":
    unittest.main()
