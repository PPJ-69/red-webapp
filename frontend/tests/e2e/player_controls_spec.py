from __future__ import annotations

import unittest
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests


class PlayerControlsBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_controls_and_keyboard_seek(self) -> None:
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

                page.goto(
                    f"http://127.0.0.1:{self.web_port}/",
                    wait_until="networkidle",
                )
                video = page.get_by_test_id("media-player")
                page.wait_for_function(
                    """() => {
                      const video = document.querySelector("video");
                      return video.readyState >= 1 || video.error !== null;
                    }""",
                    timeout=10000,
                )
                expect(page.get_by_test_id("player-controls")).to_be_visible()
                expect(
                    page.get_by_role("button", name="Unmute")
                ).to_be_visible()
                expect(
                    page.get_by_role("slider", name="Playback position")
                ).to_be_visible()
                expect(page.get_by_role("slider", name="Volume")).to_be_visible()
                expect(page.get_by_label("Playback speed")).to_be_visible()
                self.assertGreater(video.evaluate("element => element.duration"), 5)

                page.get_by_test_id("mute").click()
                self.assertFalse(video.evaluate("element => element.muted"))
                page.get_by_test_id("mute").click()
                self.assertTrue(video.evaluate("element => element.muted"))

                page.get_by_test_id("volume").evaluate(
                    """element => {
                      element.value = "0.35";
                      element.dispatchEvent(new Event("input", { bubbles: true }));
                    }"""
                )
                self.assertAlmostEqual(
                    video.evaluate("element => element.volume"),
                    0.35,
                    delta=0.01,
                )
                page.get_by_test_id("speed").select_option("2")
                self.assertEqual(video.evaluate("element => element.playbackRate"), 2)

                page.get_by_test_id("loop").click()
                self.assertTrue(video.evaluate("element => element.loop"))
                page.get_by_test_id("fullscreen").click()
                page.wait_for_function(
                    "document.fullscreenElement?.matches('.player') === true"
                )
                page.get_by_test_id("fullscreen").click()
                page.wait_for_function("document.fullscreenElement === null")

                page.evaluate("document.activeElement?.blur()")
                page.keyboard.press("ArrowRight")
                page.wait_for_function(
                    "document.querySelector('video').currentTime >= 4.9"
                )
                page.keyboard.press("ArrowLeft")
                page.wait_for_function(
                    "document.querySelector('video').currentTime <= 2.1"
                )

                page.get_by_test_id("keyboard-help").click()
                expect(page.get_by_role("dialog")).to_be_visible()
                expect(page.get_by_role("dialog")).to_contain_text("Space")
                page.keyboard.press("Escape")
                expect(page.get_by_role("dialog")).to_have_count(0)
            finally:
                browser.close()


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(PlayerControlsBrowserTests)


if __name__ == "__main__":
    unittest.main()
