from __future__ import annotations

import unittest

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests


class SessionFeaturesBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_favorites_seen_random_history_and_saved_searches(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.route(
                    "**/api/search?*",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=(
                            '{"items":[{"id":"sample-media","title":"Sample media",'
                            '"tags":[],"creator":{"id":"creator","username":"maker"}},'
                            '{"id":"sample-media-two","title":"Second sample",'
                            '"tags":[],"creator":{"id":"creator","username":"maker"}}],'
                            '"page":1,"limit":20,"hasMore":false}'
                        ),
                    ),
                )
                page.route(
                    "**/api/media/sample-media",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=(
                            '{"id":"sample-media","title":"Hydrated favorite",'
                            '"tags":[],"creator":{"id":"creator","username":"maker"}}'
                        ),
                    ),
                )
                page.goto(
                    f"http://127.0.0.1:{self.web_port}/",
                    wait_until="networkidle",
                )

                page.get_by_test_id("search-query").fill("cats #cute")
                page.get_by_test_id("search-submit").click()
                expect(page.get_by_test_id("search-history")).to_contain_text(
                    "cats #cute"
                )
                expect(page.get_by_test_id("result-card")).to_have_count(2)
                page.get_by_test_id("save-search").click()
                expect(page.get_by_test_id("saved-searches")).to_contain_text(
                    "cats #cute"
                )
                page.get_by_test_id("history-search").click()
                page.get_by_test_id("saved-search").click()
                expect(page.get_by_test_id("search-status")).to_contain_text(
                    "2 results loaded."
                )

                card_favorite = page.get_by_test_id("result-card").get_by_test_id(
                    "favorite-sample-media"
                )
                card_favorite.click()
                expect(card_favorite).to_have_attribute("aria-pressed", "true")
                page.get_by_test_id("navigate-favorites").click()
                expect(page.get_by_test_id("favorites-panel")).to_contain_text(
                    "Hydrated favorite"
                )
                page.get_by_test_id("navigate-discovery").click()
                page.get_by_test_id("result-card").first.locator(
                    "button.card-button"
                ).click()

                page.evaluate(
                    "document.activeElement instanceof HTMLElement && "
                    "document.activeElement.blur()"
                )
                page.keyboard.press("v")
                player_favorite = page.get_by_test_id("player-overlay").get_by_test_id(
                    "favorite-sample-media"
                )
                expect(player_favorite).to_have_attribute("aria-pressed", "false")
                page.keyboard.press("v")
                expect(player_favorite).to_have_attribute("aria-pressed", "true")

                page.get_by_test_id("media-player").evaluate(
                    "video => video.dispatchEvent(new Event('playing'))"
                )
                expect(
                    page.get_by_test_id("player-overlay").get_by_test_id(
                        "seen-sample-media"
                    )
                ).to_be_visible()
                page.get_by_test_id("random-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Second sample"
                )
            finally:
                browser.close()


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(SessionFeaturesBrowserTests)


if __name__ == "__main__":
    unittest.main()
