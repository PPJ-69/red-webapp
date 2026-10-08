from __future__ import annotations

import os
import shutil
import socket
import subprocess
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

import uvicorn
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect, sync_playwright

from backend.tests.fixtures.fake_cdn import FakeCDN
from backend.tests.poc_app import create_poc_app

ROOT = Path(__file__).resolve().parents[3]
FRONTEND_ROOT = ROOT / "frontend"


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_url(url: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("The Vite development server exited before starting.")
        try:
            with urlopen(url, timeout=0.25) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Server did not become ready: {url}")


class PlayerBasicBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.api_port = _available_port()
        cls.web_port = _available_port()
        cls.cdn = FakeCDN(chunk_delay=0.02)
        cls.app = create_poc_app(cls.cdn)
        cls.api_server = uvicorn.Server(
            uvicorn.Config(
                cls.app,
                host="127.0.0.1",
                port=cls.api_port,
                log_config=None,
                access_log=False,
            )
        )
        cls.api_thread = threading.Thread(
            target=cls.api_server.run, name="player-test-api", daemon=True
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
            raise RuntimeError("Node.js is required to run the player browser test.")
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
        _wait_for_url(f"http://127.0.0.1:{cls.web_port}/", cls.vite_process)

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

    def test_media_player_loads_plays_buffers_and_releases_previous_source(self) -> None:
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
                            context.fillText(`Player test ${elapsed.toFixed(1)}s`, 20, 50);
                            if (elapsed < 6) requestAnimationFrame(paint);
                          };
                          paint();
                          recorder.start();
                          await new Promise((resolve) => setTimeout(resolve, 6200));
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
                expiry_fault = Request(
                    f"http://127.0.0.1:{self.api_port}/__poc/fault?fault=expired_signature_once",
                    method="POST",
                )
                with urlopen(expiry_fault, timeout=5) as response:
                    self.assertEqual(response.status, 200)

                media_responses: list[tuple[str, int, str | None]] = []
                page.on(
                    "response",
                    lambda response: media_responses.append(
                        (
                            response.url,
                            response.status,
                            response.headers.get("content-type"),
                        )
                    )
                    if "/api/stream/" in response.url
                    else None,
                )
                page.goto(f"http://127.0.0.1:{self.web_port}/", wait_until="networkidle")
                video = page.get_by_test_id("media-player")
                try:
                    page.wait_for_function(
                        """() => {
                          const video = document.querySelector("video");
                          return video.readyState >= 1 || video.error !== null ||
                            document.querySelector('[data-testid="player-error"]') !== null;
                        }""",
                        timeout=10000,
                    )
                except PlaywrightTimeoutError:
                    self.fail(
                        "Player source did not load: "
                        + page.locator("body").inner_text()
                        + " "
                        + str(
                            video.evaluate(
                                """element => ({
                                  src: element.src,
                                  currentSrc: element.currentSrc,
                                  readyState: element.readyState,
                                  networkState: element.networkState,
                                  error: element.error?.code,
                                })"""
                            )
                        )
                    )
                self.assertIsNone(
                    video.evaluate(
                        """element => element.error && ({
                          code: element.error.code,
                          message: element.error.message,
                          src: element.currentSrc,
                          networkState: element.networkState,
                          readyState: element.readyState,
                        })"""
                    ),
                    f"{page.locator('body').inner_text()}; responses: {media_responses}",
                )
                self.assertEqual(
                    video.evaluate(
                        """element => ({
                          preload: element.preload,
                          playsInline: element.playsInline,
                          muted: element.muted,
                          loop: element.loop,
                          volume: element.volume,
                          playbackRate: element.playbackRate,
                        })"""
                    ),
                    {
                        "preload": "metadata",
                        "playsInline": True,
                        "muted": True,
                        "loop": False,
                        "volume": 1,
                        "playbackRate": 1,
                    },
                )
                source_url = video.get_attribute("src")
                self.assertIsNotNone(source_url)
                self.assertIn("/api/stream/sample-media", source_url or "")
                self.assertGreater(video.evaluate("element => element.duration"), 4)
                first_playback_stats = page.evaluate(
                    "async () => await (await fetch('/__poc/stats')).json()"
                )
                self.assertGreaterEqual(
                    first_playback_stats["cdnConnectionsOpened"],
                    2,
                    "Expired source did not recover through the relay's single re-resolution.",
                )
                self.assertGreaterEqual(first_playback_stats["cdnConnectionsClosed"], 1)

                video.evaluate("element => element.play()")
                expect(page.get_by_test_id("player-state")).to_have_text("PLAYING")
                page.evaluate(
                    """() => document.querySelector("video")
                      .dispatchEvent(new Event("waiting"))"""
                )
                expect(page.get_by_test_id("buffering")).to_be_visible()
                page.evaluate(
                    """() => document.querySelector("video")
                      .dispatchEvent(new Event("canplay"))"""
                )
                expect(page.get_by_test_id("buffering")).to_have_count(0)

                page.get_by_test_id("media-select").select_option("sample-media-two")
                try:
                    page.wait_for_function(
                        """() => document.querySelector("video").currentSrc
                          .includes("/api/stream/sample-media-two") ||
                          document.querySelector('[data-testid="player-error"]') !== null""",
                        timeout=5000,
                    )
                except PlaywrightTimeoutError:
                    self.fail(
                        "Switched source was not assigned: "
                        + str(
                            page.evaluate(
                                """() => ({
                                  src: document.querySelector("video").src,
                                  currentSrc: document.querySelector("video").currentSrc,
                                  state: document.querySelector(
                                    '[data-testid="player-state"]'
                                  ).textContent,
                                  selected: document.querySelector(
                                    '[data-testid="media-select"]'
                                  ).value,
                                })"""
                            )
                        )
                    )
                page.wait_for_function(
                    """async () => {
                      const stats = await (await fetch("/__poc/stats")).json();
                      return stats.cdnConnectionsOpened >= 2 &&
                        stats.cdnConnectionsActive === 0 &&
                        stats.streamActiveConnections === 0 &&
                        stats.cdnConnectionsOpened === stats.cdnConnectionsClosed;
                    }"""
                )
                expect(page.get_by_test_id("player-state")).to_have_text("PAUSED")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
