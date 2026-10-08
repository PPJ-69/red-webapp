from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

import uvicorn
from playwright.sync_api import expect, sync_playwright

from backend.tests.poc_app import create_poc_app
from backend.tests.fixtures.fake_cdn import FakeCDN
from tools.compliance.fs_monitor.monitor import FileSystemMonitor

ROOT = Path(__file__).resolve().parents[3]
FRONTEND_ROOT = ROOT / "frontend"
STORAGE_MONITOR = (
    ROOT / "tools" / "compliance" / "browser_storage_check" / "storage_monitor.js"
)


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_url(url: str, process: subprocess.Popen | None = None) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError("The Vite development server exited before starting.")
        try:
            with urlopen(url, timeout=0.25) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Server did not become ready: {url}")


class StreamingPocBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.api_port = _available_port()
        cls.web_port = _available_port()
        cls.cdn = FakeCDN(chunk_delay=0.001)
        cls.app = create_poc_app(cls.cdn)
        config = uvicorn.Config(
            cls.app,
            host="127.0.0.1",
            port=cls.api_port,
            log_config=None,
            access_log=False,
        )
        cls.api_server = uvicorn.Server(config)
        cls.api_thread = threading.Thread(
            target=cls.api_server.run, name="poc-api", daemon=True
        )
        cls.api_thread.start()
        deadline = time.monotonic() + 10
        while not cls.api_server.started and time.monotonic() < deadline:
            if not cls.api_thread.is_alive():
                raise RuntimeError("The POC API failed to start.")
            time.sleep(0.05)
        if not cls.api_server.started:
            raise TimeoutError("The POC API did not start.")

        node = shutil.which("node")
        if node is None:
            cls.api_server.should_exit = True
            cls.api_thread.join(timeout=5)
            raise RuntimeError("Node.js is required to run the POC browser test.")
        vite_entry = FRONTEND_ROOT / "node_modules" / "vite" / "bin" / "vite.js"
        cls.vite_process = subprocess.Popen(
            [
                node,
                str(vite_entry),
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
        _wait_for_url(f"http://127.0.0.1:{cls.web_port}/poc.html", cls.vite_process)

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

    def test_native_playback_range_retry_switch_and_compliance(self) -> None:
        with FileSystemMonitor([ROOT]) as filesystem_monitor:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = browser.new_page()
                    page.add_init_script(path=str(STORAGE_MONITOR))
                    page.goto(
                        f"http://127.0.0.1:{self.web_port}/poc.html",
                        wait_until="networkidle",
                    )
                    page.evaluate(
                        """async () => {
                          const canvas = document.createElement("canvas");
                          canvas.width = 320;
                          canvas.height = 180;
                          const context = canvas.getContext("2d");
                          if (!context || !HTMLCanvasElement.prototype.captureStream) {
                            throw new Error("Canvas recording is not supported.");
                          }
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
                            context.fillText(`Relay POC ${elapsed.toFixed(1)}s`, 20, 50);
                            if (elapsed < 8) requestAnimationFrame(paint);
                          };
                          paint();
                          recorder.start();
                          await new Promise((resolve) => setTimeout(resolve, 8200));
                          recorder.stop();
                          await stopped;
                          for (const track of stream.getTracks()) track.stop();
                          const fixture = new Blob(chunks, { type: mimeType });
                          const uploaded = await fetch("/__poc/fixture", {
                            method: "POST",
                            headers: { "Content-Type": "video/webm" },
                            body: fixture,
                          });
                          if (!uploaded.ok) throw new Error("Could not configure test media.");
                        }"""
                    )

                    page.get_by_test_id("load").click()
                    expect(page.get_by_test_id("source-kind")).to_contain_text("relay")
                    page.wait_for_function(
                        "document.querySelector('video').readyState >= 1"
                    )
                    self.assertGreater(
                        page.locator("video").evaluate("(video) => video.duration"), 5
                    )
                    page.get_by_test_id("play").click()
                    expect(page.get_by_test_id("status")).to_have_text("Playing")
                    page.wait_for_function(
                        "document.querySelector('video').currentTime > 0.5"
                    )
                    page.get_by_test_id("pause").click()
                    expect(page.get_by_test_id("status")).to_have_text("Paused")

                    page.get_by_test_id("seek-forward").click()
                    page.wait_for_function(
                        "document.querySelector('video').currentTime > 2"
                    )
                    page.get_by_test_id("seek-back").click()
                    page.wait_for_function(
                        "document.querySelector('video').currentTime < 2.5"
                    )
                    page.get_by_test_id("next").click()
                    expect(page.get_by_test_id("source-kind")).to_contain_text(
                        "/api/stream/sample-media-two"
                    )
                    page.get_by_test_id("inject-failure").click()
                    page.wait_for_function(
                        "document.querySelector('video').error !== null"
                    )
                    expect(page.get_by_test_id("status")).to_contain_text("Playback failed")
                    page.get_by_test_id("retry").click()
                    page.get_by_test_id("play").click()
                    expect(page.get_by_test_id("status")).to_have_text("Playing")
                    page.wait_for_function(
                        "document.querySelector('video').currentTime > 0.3"
                    )

                    page.get_by_test_id("next").click()
                    expect(page.get_by_test_id("source-kind")).to_contain_text(
                        "/api/stream/sample-media"
                    )
                    page.get_by_test_id("play").click()
                    expect(page.get_by_test_id("status")).to_have_text("Playing")
                    page.wait_for_function(
                        "document.querySelector('video').currentTime > 0.3"
                    )
                    page.get_by_test_id("stop").click()
                    expect(page.get_by_test_id("status")).to_have_text("Stopped")
                    page.wait_for_function(
                        """async () => {
                          const stats = await (await fetch("/__poc/stats")).json();
                          return stats.cdnConnectionsActive === 0 &&
                            stats.streamActiveConnections === 0 &&
                            stats.cdnConnectionsOpened === stats.cdnConnectionsClosed;
                        }"""
                    )
                    violations = page.evaluate(
                        "window.__complianceStorageViolations || []"
                    )
                    self.assertEqual(violations, [])
                finally:
                    browser.close()
        self.assertEqual(filesystem_monitor.violations, ())


if __name__ == "__main__":
    unittest.main()
