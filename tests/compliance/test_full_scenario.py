from __future__ import annotations

import json
import os
from pathlib import Path
import time
import unittest
from urllib.parse import parse_qs, unquote, urlsplit

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests
from tools.compliance.fs_monitor.monitor import (
    FileSystemMonitor,
    IGNORED_DIRECTORY_NAMES,
    classify_path,
    default_monitor_roots,
)


ROOT = Path(__file__).resolve().parents[2]
STORAGE_MONITOR = (
    ROOT / "tools" / "compliance" / "browser_storage_check" / "storage_monitor.js"
)
_IMAGE_COUNT = 320
_PLAY_COUNT = 100
_QUERY_COUNT = 10
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00"
    b"\x00\x00\x90wS\xde\x00\x00\x00\x0bIDAT"
    b"\x08\xd7c\xf8\x0f\x00\x01\x01\x01\x00"
    b"\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _suspicious_paths(roots: tuple[Path, ...]) -> set[tuple[Path, str]]:
    found: set[tuple[Path, str]] = set()
    ignored = {name.casefold() for name in IGNORED_DIRECTORY_NAMES}
    ignored.discard("dist")
    ignored.discard("fixtures")
    for root in roots:
        if not root.is_dir():
            continue
        for directory, names, files in os.walk(root, followlinks=False):
            current = Path(directory)
            for name in tuple(names):
                candidate = current / name
                if name.casefold() in ignored:
                    names.remove(name)
                    continue
                violation = classify_path(candidate, is_directory=True)
                if violation is not None:
                    found.add((candidate.resolve(), violation))
            for name in files:
                candidate = current / name
                violation = classify_path(candidate)
                if violation is not None:
                    found.add((candidate.resolve(), violation))
    return found


class FullNoDownloadScenarioTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_full_browser_flow_keeps_state_and_media_ephemeral(self) -> None:
        roots = default_monitor_roots(ROOT)
        existing_artifacts = _suspicious_paths(roots)
        with FileSystemMonitor(
            roots,
            ignored_directories=IGNORED_DIRECTORY_NAMES - {"dist", "fixtures"},
        ) as monitor:
            self._exercise_browser_scenario()
        final_artifacts = _suspicious_paths(roots)
        added_artifacts = sorted(
            (str(path), kind)
            for path, kind in final_artifacts - existing_artifacts
        )
        self.assertEqual(
            monitor.violations,
            (),
            f"Filesystem monitor found forbidden writes: {monitor.violations}",
        )
        self.assertEqual(
            added_artifacts,
            [],
            f"Recursive artifact scan found new media/database/settings paths: {added_artifacts}",
        )

    def _exercise_browser_scenario(self) -> None:
        results_by_query: list[str] = []
        source_media_ids: set[str] = set()
        streamed_media_ids: set[str] = set()
        requested_thumbnails: set[str] = set()
        range_requests: list[str] = []
        results = self._results(_IMAGE_COUNT)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                context = browser.new_context(
                    viewport={"width": 1280, "height": 900}
                )
                context.add_init_script(path=str(STORAGE_MONITOR))
                context.add_init_script(
                    """(() => {
                      window.__fullScenarioPlayback = { playing: [], seeking: 0, seeked: 0 };
                      document.addEventListener("playing", (event) => {
                        const video = event.target;
                        if (!(video instanceof HTMLVideoElement) || !video.currentSrc) return;
                        const id = new URL(video.currentSrc).pathname.split("/").pop();
                        window.__fullScenarioPlayback.playing.push(id);
                      }, true);
                      document.addEventListener("seeking", () => {
                        window.__fullScenarioPlayback.seeking += 1;
                      }, true);
                      document.addEventListener("seeked", () => {
                        window.__fullScenarioPlayback.seeked += 1;
                      }, true);
                    })();"""
                )
                page = context.new_page()

                def search(route) -> None:
                    query = parse_qs(urlsplit(route.request.url).query).get("q", [""])[0]
                    results_by_query.append(query)
                    payload = (
                        results
                        if query == f"compliance-query-{_QUERY_COUNT - 1}"
                        else self._results(3)
                    )
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(payload),
                    )

                def source(route) -> None:
                    media_id = unquote(
                        urlsplit(route.request.url).path.split("/api/media/", 1)[1]
                    ).split("/", 1)[0]
                    source_media_ids.add(media_id)
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "playbackUrl": f"/api/stream/{media_id}?quality=auto",
                                "kind": "relay",
                                "requiresRelay": True,
                                "expiresAt": None,
                            }
                        ),
                    )

                def stream(route) -> None:
                    parsed = urlsplit(route.request.url)
                    media_id = unquote(parsed.path.rsplit("/", 1)[-1])
                    streamed_media_ids.add(media_id)
                    range_header = route.request.headers.get("range")
                    if range_header is None:
                        route.fulfill(
                            status=200,
                            content_type="video/webm",
                            headers={
                                "Accept-Ranges": "bytes",
                                "Content-Length": str(len(fixture)),
                                "Cache-Control": "no-store",
                            },
                            body=fixture,
                        )
                        return
                    range_requests.append(range_header)
                    start_end = range_header.removeprefix("bytes=").split("-", 1)
                    start = int(start_end[0] or "0")
                    end = min(
                        int(start_end[1]) if start_end[1] else len(fixture) - 1,
                        len(fixture) - 1,
                    )
                    if start > end:
                        route.fulfill(
                            status=416,
                            headers={
                                "Content-Range": f"bytes */{len(fixture)}",
                                "Content-Length": "0",
                            },
                            body=b"",
                        )
                        return
                    chunk = fixture[start : end + 1]
                    route.fulfill(
                        status=206,
                        content_type="video/webm",
                        headers={
                            "Accept-Ranges": "bytes",
                            "Content-Range": f"bytes {start}-{end}/{len(fixture)}",
                            "Content-Length": str(len(chunk)),
                            "Cache-Control": "no-store",
                        },
                        body=chunk,
                    )

                def thumbnail(route) -> None:
                    requested_thumbnails.add(route.request.url)
                    route.fulfill(
                        status=200,
                        content_type="image/png",
                        headers={"Cache-Control": "no-store"},
                        body=_PNG_1X1,
                    )

                page.route("**/api/search?*", search)
                page.route("**/api/media/*/source*", source)
                page.route("**/api/stream/*", stream)
                page.route("https://images.example.invalid/**", thumbnail)
                page.route(
                    "**/api/media/*",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(results["items"][0]),
                    ),
                )

                fixture = self._record_webm_fixture(page)
                page.goto(
                    f"http://127.0.0.1:{self.web_port}/",
                    wait_until="networkidle",
                )

                for index in range(_QUERY_COUNT):
                    query = f"compliance-query-{index}"
                    page.get_by_test_id("search-query").fill(query)
                    page.get_by_test_id("search-submit").click()
                    expected_count = _IMAGE_COUNT if index == _QUERY_COUNT - 1 else 3
                    expect(page.get_by_test_id("result-card")).to_have_count(
                        expected_count,
                        timeout=10000,
                    )
                self.assertEqual(len(results_by_query), _QUERY_COUNT)
                self.assertEqual(len(set(results_by_query)), _QUERY_COUNT)

                favorite = page.get_by_test_id("favorite-full-media-0")
                expect(favorite).to_have_attribute("aria-pressed", "false")
                favorite.click()
                expect(favorite).to_have_attribute("aria-pressed", "true")
                favorite.click()
                expect(favorite).to_have_attribute("aria-pressed", "false")
                favorite.click()
                expect(favorite).to_have_attribute("aria-pressed", "true")
                page.get_by_test_id("save-search").click()
                expect(page.get_by_test_id("search-history")).to_contain_text(
                    f"compliance-query-{_QUERY_COUNT - 1}"
                )
                expect(page.get_by_test_id("saved-searches")).to_contain_text(
                    f"compliance-query-{_QUERY_COUNT - 1}"
                )

                cards = page.get_by_test_id("result-card")
                cards.nth(0).locator("button.card-button").click()
                video = page.get_by_test_id("media-player")

                for index in range(_PLAY_COUNT):
                    media_id = f"full-media-{index}"
                    page.wait_for_function(
                        """id => {
                          const video = document.querySelector("video");
                          return !!video && video.readyState >= 1 && !!video.currentSrc &&
                            new URL(video.currentSrc).pathname.endsWith(`/api/stream/${id}`);
                        }""",
                        arg=media_id,
                        timeout=15000,
                    )
                    video.evaluate("element => element.play()")
                    page.wait_for_function(
                        "id => window.__fullScenarioPlayback.playing.includes(id)",
                        arg=media_id,
                        timeout=10000,
                    )
                    for fraction in (0.25, 0.7):
                        page.evaluate(
                            """async fraction => {
                              const video = document.querySelector("video");
                              const target = Math.min(
                                video.duration * fraction,
                                video.duration - 0.05,
                              );
                              if (!Number.isFinite(target) || target <= 0) {
                                throw new Error(
                                  "The in-memory media fixture is not seekable."
                                );
                              }
                              await new Promise((resolve, reject) => {
                                const timeout = setTimeout(
                                  () => reject(new Error("Media seek timed out.")),
                                  5000,
                                );
                                video.addEventListener("seeked", () => {
                                  clearTimeout(timeout);
                                  resolve();
                                }, { once: true });
                                video.currentTime = target;
                              });
                            }""",
                            fraction,
                        )
                    video.evaluate("element => element.pause()")
                    if index + 1 < _PLAY_COUNT:
                        page.get_by_test_id("next-item").click()

                playback_metrics = page.evaluate(
                    "() => window.__fullScenarioPlayback"
                )
                self.assertGreaterEqual(
                    len(set(playback_metrics["playing"])), _PLAY_COUNT
                )
                self.assertGreaterEqual(playback_metrics["seeking"], 2 * _PLAY_COUNT)
                self.assertGreaterEqual(playback_metrics["seeked"], 2 * _PLAY_COUNT)
                self.assertGreaterEqual(len(source_media_ids), _PLAY_COUNT)
                self.assertGreaterEqual(len(streamed_media_ids), _PLAY_COUNT)
                self.assertGreaterEqual(
                    sum(
                        item.startswith("full-media-")
                        for item in streamed_media_ids
                    ),
                    _PLAY_COUNT,
                )
                self.assertGreaterEqual(len(range_requests), _PLAY_COUNT)

                page.get_by_test_id("close-player").click()
                page.evaluate(
                    """async () => {
                      const step = Math.max(400, window.innerHeight * 0.6);
                      for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
                        window.scrollTo(0, y);
                        await new Promise(resolve => setTimeout(resolve, 30));
                      }
                      window.scrollTo(0, document.documentElement.scrollHeight);
                      await new Promise(resolve => setTimeout(resolve, 250));
                    }"""
                )
                deadline = time.monotonic() + 10
                while len(requested_thumbnails) < 200 and time.monotonic() < deadline:
                    page.wait_for_timeout(100)
                self.assertGreaterEqual(len(requested_thumbnails), 200)
                self.assertEqual(
                    page.evaluate("window.__complianceStorageViolations"),
                    [],
                )
                self.assertEqual(context.cookies(), [])
                context.close()
                print(
                    "Full no-download scenario: "
                    f"{len(set(results_by_query))} unique searches, "
                    f"{len(set(playback_metrics['playing']))} distinct media played, "
                    f"{playback_metrics['seeking']} seeks, "
                    f"{len(requested_thumbnails)} thumbnails fetched while scrolling, "
                    f"{len(range_requests)} ranged stream requests, "
                    "0 browser storage/cookies"
                )
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
                        status=200,
                        content_type="application/json",
                        body=json.dumps(self._results(3)),
                    ),
                )
                restarted_page.goto(
                    f"http://127.0.0.1:{self.web_port}/",
                    wait_until="networkidle",
                )
                expect(restarted_page.get_by_test_id("search-history")).to_have_count(0)
                expect(restarted_page.get_by_test_id("saved-searches")).to_have_count(0)
                restarted_page.get_by_test_id("navigate-favorites").click()
                expect(
                    restarted_page.get_by_test_id("favorites-panel")
                ).to_contain_text("No favorites yet.")
                self.assertEqual(
                    restarted_page.evaluate("window.__complianceStorageViolations"),
                    [],
                )
                self.assertEqual(restarted_context.cookies(), [])
                restarted_context.close()
            finally:
                restarted_browser.close()

    @staticmethod
    def _results(count: int) -> dict[str, object]:
        items = [
            {
                "id": f"full-media-{index}",
                "title": f"Compliance media {index}",
                "duration": 2,
                "thumbnailUrl": (
                    f"https://images.example.invalid/full-media-{index}.png"
                ),
                "creator": {"id": "compliance-creator", "username": "fixture"},
                "tags": ["compliance"],
            }
            for index in range(count)
        ]
        return {
            "items": items,
            "page": 1,
            "limit": 100,
            "hasMore": False,
            "total": count,
        }

    @staticmethod
    def _record_webm_fixture(page) -> bytes:
        values = page.evaluate(
            """async () => {
              const canvas = document.createElement("canvas");
              canvas.width = 320;
              canvas.height = 180;
              const context = canvas.getContext("2d");
              if (!context) throw new Error("Canvas context is unavailable.");
              const mimeType = ["video/webm;codecs=vp8", "video/webm"]
                .find(type => MediaRecorder.isTypeSupported(type));
              if (!mimeType) throw new Error("WebM recording is unavailable.");
              const stream = canvas.captureStream(15);
              const recorder = new MediaRecorder(stream, { mimeType });
              const chunks = [];
              recorder.addEventListener("dataavailable", event => {
                if (event.data.size) chunks.push(event.data);
              });
              const stopped = new Promise(resolve =>
                recorder.addEventListener("stop", resolve, { once: true }),
              );
              const startedAt = performance.now();
              const paint = () => {
                const seconds = (performance.now() - startedAt) / 1000;
                context.fillStyle = `hsl(${seconds * 80} 70% 45%)`;
                context.fillRect(0, 0, canvas.width, canvas.height);
                context.fillStyle = "white";
                context.font = "24px sans-serif";
                context.fillText(`Compliance ${seconds.toFixed(2)}`, 20, 50);
                if (seconds < 2.1) requestAnimationFrame(paint);
              };
              paint();
              recorder.start();
              await new Promise(resolve => setTimeout(resolve, 2200));
              recorder.stop();
              await stopped;
              for (const track of stream.getTracks()) track.stop();
              return Array.from(new Uint8Array(
                await new Blob(chunks, { type: mimeType }).arrayBuffer(),
              ));
            }"""
        )
        return bytes(values)


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(FullNoDownloadScenarioTests)


if __name__ == "__main__":
    unittest.main()
