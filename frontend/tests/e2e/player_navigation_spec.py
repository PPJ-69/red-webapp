from __future__ import annotations

import unittest
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests


class PlayerNavigationBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_queue_navigation_prefetch_and_close_restore(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.goto("about:blank")
                fixture = bytes(
                    page.evaluate(
                        """async () => {
                          const canvas = document.createElement("canvas");
                          canvas.width = 320;
                          canvas.height = 180;
                          const context = canvas.getContext("2d");
                          if (!context) throw new Error("Canvas context is unavailable.");
                          const mimeType = [
                            "video/webm;codecs=vp8",
                            "video/webm",
                          ].find((type) => MediaRecorder.isTypeSupported(type));
                          if (!mimeType) throw new Error("WebM recording is unavailable.");
                          const stream = canvas.captureStream(12);
                          const recorder = new MediaRecorder(stream, { mimeType });
                          const chunks = [];
                          recorder.addEventListener("dataavailable", (event) => {
                            if (event.data.size) chunks.push(event.data);
                          });
                          const stopped = new Promise((resolve) =>
                            recorder.addEventListener("stop", resolve, { once: true }),
                          );
                          const startedAt = performance.now();
                          const paint = () => {
                            const elapsed = (performance.now() - startedAt) / 1000;
                            context.fillStyle = `hsl(${(elapsed * 45) % 360} 70% 45%)`;
                            context.fillRect(0, 0, canvas.width, canvas.height);
                            if (elapsed < 7) requestAnimationFrame(paint);
                          };
                          paint();
                          recorder.start();
                          await new Promise((resolve) => setTimeout(resolve, 7200));
                          recorder.stop();
                          await stopped;
                          for (const track of stream.getTracks()) track.stop();
                          const fixture = new Blob(chunks, { type: mimeType });
                          return Array.from(new Uint8Array(await fixture.arrayBuffer()));
                        }"""
                    )
                )
                upload = Request(
                    f"http://127.0.0.1:{self.api_port}/__poc/fixture",
                    data=fixture,
                    headers={"Content-Type": "video/webm"},
                    method="POST",
                )
                with urlopen(upload, timeout=5) as response:
                    self.assertEqual(response.status, 200)

                stream_urls: list[str] = []
                source_urls: list[str] = []
                page.on(
                    "response",
                    lambda response: (
                        stream_urls.append(response.url)
                        if "/api/stream/" in response.url
                        else source_urls.append(response.url)
                        if "/api/media/" in response.url and "/source" in response.url
                        else None
                    ),
                )
                page.goto(
                    f"http://127.0.0.1:{self.web_port}/",
                    wait_until="networkidle",
                )
                video = page.get_by_test_id("media-player")
                def wait_for_item(media_id: str) -> None:
                    page.wait_for_function(
                        """mediaId => document.querySelector('video').currentSrc
                          .includes(mediaId)""",
                        arg=media_id,
                    )
                    video.evaluate("element => element.pause()")
                    page.wait_for_function(
                        """() => document.querySelector('[data-testid="player-state"]')
                          .textContent === "PAUSED" """
                    )

                page.wait_for_function(
                    "() => document.querySelector('video').readyState >= 1",
                    timeout=10000,
                )
                video.evaluate("element => element.pause()")
                expect(page.get_by_test_id("player-overlay")).to_be_visible()
                expect(page.get_by_test_id("previous-item")).to_be_disabled()
                expect(page.get_by_test_id("next-item")).to_be_enabled()
                page.wait_for_function(
                    """() => performance.getEntriesByType("resource")
                      .some(entry => entry.name.includes(
                        "/api/media/sample-media-two/source"
                      ))"""
                )
                self.assertTrue(source_urls)
                self.assertTrue(
                    all("/api/stream/sample-media" in url for url in stream_urls),
                    f"Non-current media stream was requested: {stream_urls}",
                )

                page.get_by_test_id("next-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Second sample"
                )
                page.wait_for_function(
                    "() => document.querySelector('video').currentSrc.includes('sample-media-two')"
                )
                expect(page.get_by_test_id("next-item")).to_be_disabled()
                page.get_by_test_id("previous-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Sample media"
                )
                wait_for_item("sample-media")
                page.get_by_test_id("random-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Second sample"
                )
                page.get_by_test_id("previous-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Sample media"
                )
                wait_for_item("sample-media")

                page.evaluate(
                    """() => document.querySelector("video")
                      .dispatchEvent(new Event("ended"))"""
                )
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Sample media"
                )
                expect(page.get_by_test_id("player-state")).to_have_text("ENDED")
                page.get_by_test_id("loop").click()
                expect(video).to_have_js_property("loop", True)
                page.get_by_test_id("next-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Second sample"
                )
                page.wait_for_function(
                    "() => document.querySelector('video').currentSrc.includes('sample-media-two')"
                )
                page.evaluate(
                    """() => document.querySelector("video")
                      .dispatchEvent(new Event("ended"))"""
                )
                expect(page.get_by_test_id("player-state")).to_have_text("ENDED")
                page.get_by_test_id("previous-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Sample media"
                )
                wait_for_item("sample-media")
                page.evaluate(
                    """() => document.querySelector("video")
                      .dispatchEvent(new Event("ended"))"""
                )
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Sample media"
                )

                page.get_by_test_id("loop").click()
                page.get_by_test_id("autoplay-setting").check()
                page.get_by_test_id("next-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Second sample"
                )
                page.get_by_test_id("previous-item").click()
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Sample media"
                )
                wait_for_item("sample-media")
                page.evaluate(
                    """() => document.querySelector("video")
                      .dispatchEvent(new Event("ended"))"""
                )
                expect(page.get_by_test_id("player-overlay")).to_contain_text(
                    "Second sample"
                )
                self.assertTrue(
                    all(
                        any(f"/api/stream/{media_id}" in url for url in stream_urls)
                        for media_id in ("sample-media", "sample-media-two")
                    ),
                    f"Expected streams only for current queue items: {stream_urls}",
                )

                page.get_by_test_id("close-player").click()
                expect(page.get_by_test_id("media-player")).to_have_count(0)
                opener = page.get_by_test_id("open-player")
                expect(opener).to_be_focused()
                opener.click()
                expect(page.get_by_test_id("media-player")).to_be_visible()
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
    return loader.loadTestsFromTestCase(PlayerNavigationBrowserTests)


if __name__ == "__main__":
    unittest.main()
