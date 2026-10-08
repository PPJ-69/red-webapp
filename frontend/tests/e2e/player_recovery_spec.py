from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

import uvicorn
from playwright.sync_api import expect, sync_playwright

from backend.tests.fixtures.fake_cdn import FakeCDN
from backend.tests.poc_app import create_poc_app

ROOT = Path(__file__).resolve().parents[3]
FRONTEND_ROOT = ROOT / "frontend"


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _error_envelope(category: str, message: str, retry_after: int | None = None) -> str:
    payload: dict[str, str | int] = {
        "category": category,
        "message": message,
        "correlationId": "player-recovery-test",
    }
    if retry_after is not None:
        payload["retryAfter"] = retry_after
    return json.dumps(payload)


class PlayerRecoveryBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.api_port = _available_port()
        cls.web_port = _available_port()
        cls.cdn = FakeCDN()
        cls.api_server = uvicorn.Server(
            uvicorn.Config(
                create_poc_app(cls.cdn),
                host="127.0.0.1",
                port=cls.api_port,
                log_config=None,
                access_log=False,
            )
        )
        cls.api_thread = threading.Thread(
            target=cls.api_server.run, name="player-recovery-api", daemon=True
        )
        cls.api_thread.start()
        deadline = time.monotonic() + 10
        while not cls.api_server.started and time.monotonic() < deadline:
            if not cls.api_thread.is_alive():
                raise RuntimeError("The fake-provider API failed to start.")
            time.sleep(0.05)
        if not cls.api_server.started:
            raise TimeoutError("The fake-provider API did not start.")

        node = shutil.which("node")
        if node is None:
            cls.api_server.should_exit = True
            cls.api_thread.join(timeout=5)
            raise RuntimeError("Node.js is required to run the player recovery test.")
        cls.vite_process = subprocess.Popen(
            [
                node,
                str(FRONTEND_ROOT / "node_modules" / "vite" / "bin" / "vite.js"),
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.web_port),
                "--strictPort",
            ],
            cwd=FRONTEND_ROOT,
            env={
                **os.environ,
                "POC_API_ORIGIN": f"http://127.0.0.1:{cls.api_port}",
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 20
        vite_ready = False
        while time.monotonic() < deadline:
            if cls.vite_process.poll() is not None:
                raise RuntimeError("The Vite development server exited before starting.")
            try:
                with urlopen(f"http://127.0.0.1:{cls.web_port}/", timeout=0.25) as response:
                    if response.status == 200:
                        vite_ready = True
                        break
            except OSError:
                time.sleep(0.1)
        if not vite_ready:
            raise TimeoutError("The frontend development server did not start.")

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
                            context.fillStyle = "white";
                            context.font = "24px sans-serif";
                            context.fillText(`Recovery ${elapsed.toFixed(1)}s`, 20, 50);
                            if (elapsed < 6) requestAnimationFrame(paint);
                          };
                          paint();
                          recorder.start();
                          await new Promise((resolve) => setTimeout(resolve, 6200));
                          recorder.stop();
                          await stopped;
                          for (const track of stream.getTracks()) track.stop();
                          return Array.from(
                            new Uint8Array(
                              await new Blob(chunks, { type: mimeType }).arrayBuffer(),
                            ),
                          );
                        }"""
                    )
                )
                upload = Request(
                    f"http://127.0.0.1:{cls.api_port}/__poc/fixture",
                    data=fixture,
                    headers={"Content-Type": "video/webm"},
                    method="POST",
                )
                with urlopen(upload, timeout=5) as response:
                    if response.status != 200:
                        raise RuntimeError("Could not configure recovery test video.")
            finally:
                browser.close()

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "vite_process"):
            cls.vite_process.terminate()
            try:
                cls.vite_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.vite_process.kill()
                cls.vite_process.wait(timeout=5)
        if hasattr(cls, "api_server"):
            cls.api_server.should_exit = True
            cls.api_thread.join(timeout=10)

    def test_expired_auth_resolves_once_then_loads_source(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                source_requests = 0
                qualities: list[str] = []

                def resolve_source(route) -> None:
                    nonlocal source_requests
                    source_requests += 1
                    qualities.append(
                        parse_qs(urlsplit(route.request.url).query).get(
                            "quality", [""]
                        )[0]
                    )
                    if source_requests == 1:
                        route.fulfill(
                            status=502,
                            content_type="application/json",
                            body=_error_envelope(
                                "upstream_authentication_failed",
                                "Playback authorization expired.",
                            ),
                        )
                    else:
                        route.continue_()

                page.route("**/api/media/sample-media/source*", resolve_source)
                page.goto(f"http://127.0.0.1:{self.web_port}/", wait_until="networkidle")
                page.wait_for_function(
                    """() => document.querySelector("video").src
                      .includes("/api/stream/sample-media")"""
                )
                self.assertEqual(qualities.count("auto"), 2)
                self.assertLessEqual(source_requests, 3)
            finally:
                browser.close()

    def test_not_found_is_unavailable_without_retry_or_bypass(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.route(
                    "**/api/media/sample-media/source*",
                    lambda route: route.fulfill(
                        status=404,
                        content_type="application/json",
                        body=_error_envelope("not_found", "Missing media."),
                    ),
                )
                page.goto(f"http://127.0.0.1:{self.web_port}/", wait_until="networkidle")
                expect(page.get_by_role("heading", name="Unavailable")).to_be_visible()
                expect(page.get_by_test_id("retry")).to_have_count(0)
                expect(page.get_by_test_id("skip")).to_be_visible()
                expect(page.get_by_test_id("open")).to_have_count(0)
                page.get_by_test_id("skip").click()
                expect(page.get_by_test_id("player-state")).to_have_text("IDLE")
                expect(page.get_by_test_id("player-error")).to_have_count(0)
            finally:
                browser.close()

    def test_rate_limit_timing_and_manual_retry(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                source_requests = 0

                def resolve_source(route) -> None:
                    nonlocal source_requests
                    source_requests += 1
                    if source_requests == 1:
                        route.fulfill(
                            status=429,
                            content_type="application/json",
                            body=_error_envelope(
                                "rate_limited", "Rate limited.", retry_after=7
                            ),
                        )
                    else:
                        route.continue_()

                page.route("**/api/media/sample-media/source*", resolve_source)
                page.goto(f"http://127.0.0.1:{self.web_port}/", wait_until="networkidle")
                expect(page.get_by_test_id("player-error")).to_contain_text(
                    "Wait 7 seconds before retrying."
                )
                page.get_by_test_id("retry").click()
                page.wait_for_function(
                    """() => document.querySelector("video").src
                      .includes("/api/stream/sample-media")"""
                )
                self.assertEqual(source_requests, 2)
                expect(page.get_by_test_id("player-state")).to_have_text("PAUSED")
                expect(page.get_by_test_id("player-error")).to_have_count(0)
            finally:
                browser.close()

    def test_fake_cdn_404_is_unavailable_and_429_can_be_retried(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{self.web_port}/", wait_until="networkidle")
                page.wait_for_function(
                    "document.querySelector('video').readyState >= 1"
                )

                page.evaluate(
                    """async () => {
                      await fetch("/__poc/fault?fault=not_found", { method: "POST" });
                    }"""
                )
                page.get_by_test_id("media-select").select_option("sample-media-two")
                expect(page.get_by_test_id("player-error")).to_be_visible()
                self.assertIn(
                    "Unavailable",
                    page.get_by_test_id("player-error").inner_text(),
                    str(
                        page.evaluate(
                            """() => performance.getEntriesByName(
                              document.querySelector("video").currentSrc
                            ).map((entry) => ({
                              name: entry.name,
                              responseStatus: entry.responseStatus,
                              transferSize: entry.transferSize,
                              responseStart: entry.responseStart,
                            }))"""
                        )
                    ),
                )
                expect(page.get_by_test_id("retry")).to_have_count(0)
                expect(page.get_by_test_id("skip")).to_be_visible()

                page.evaluate(
                    """async () => {
                      await fetch("/__poc/fault?fault=clear", { method: "POST" });
                    }"""
                )
                page.get_by_test_id("media-select").select_option("sample-media")
                expect(page.get_by_test_id("player-state")).to_have_text("PAUSED")

                page.evaluate(
                    """async () => {
                      await fetch("/__poc/fault?fault=rate_limited", { method: "POST" });
                    }"""
                )
                page.get_by_test_id("media-select").select_option("sample-media-two")
                expect(page.get_by_test_id("player-error")).to_contain_text(
                    "rate limited"
                )
                expect(page.get_by_test_id("player-error")).to_contain_text("Wait")

                page.evaluate(
                    """async () => {
                      await fetch("/__poc/fault?fault=clear", { method: "POST" });
                    }"""
                )
                page.get_by_test_id("retry").click()
                expect(page.get_by_test_id("player-state")).to_have_text("PAUSED")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
