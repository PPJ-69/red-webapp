from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MONITOR_SCRIPT = Path(__file__).with_name("storage_monitor.js")
SERVICE_WORKER_SELF_CHECK = """
<!doctype html>
<script>
  for (const api of ['localStorage', 'sessionStorage', 'indexedDB', 'caches']) {
    try { window[api]; } catch (_) {}
  }
  navigator.serviceWorker.register('/sw.js').catch(() => {});
</script>
"""


class _SelfCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/sw.js":
            body = b"self.addEventListener('install', () => self.skipWaiting());"
            content_type = "application/javascript"
        else:
            body = SERVICE_WORKER_SELF_CHECK.encode()
            content_type = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _launch_browser():
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Browser storage checking requires Playwright. Install "
            "`tools/compliance/requirements.txt` and its Chromium browser."
        ) from exc
    return sync_playwright(), PlaywrightError


def inspect_url(url: str, duration: float = 0) -> list[dict[str, str]]:
    playwright_context, playwright_error = _launch_browser()
    try:
        with playwright_context as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.add_init_script(path=str(MONITOR_SCRIPT))
                page.goto(url, wait_until="domcontentloaded")
                if duration > 0:
                    page.wait_for_timeout(duration * 1000)
                return page.evaluate("window.__complianceStorageViolations || []")
            finally:
                browser.close()
    except playwright_error as exc:
        raise RuntimeError(f"Browser storage check failed: {exc}") from exc


def self_check() -> list[dict[str, str]]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SelfCheckHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        violations = inspect_url(
            f"http://127.0.0.1:{server.server_port}/", duration=0.5
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    if not any(
        item.get("type") == "service_worker_registration" for item in violations
    ):
        raise AssertionError("Browser monitor did not detect service-worker registration.")
    return violations


def api_self_check() -> list[dict[str, str]]:
    violations = self_check()
    detected = {item.get("path") for item in violations}
    expected = {
        "browser:localStorage",
        "browser:sessionStorage",
        "browser:indexedDB",
        "browser:caches",
    }
    if not expected.issubset(detected):
        raise AssertionError(
            f"Browser monitor missed storage API access: {sorted(expected - detected)}"
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect browser use of persistent storage APIs."
    )
    parser.add_argument("url", nargs="?")
    parser.add_argument("--duration", type=float, default=0)
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Register a service worker in a local browser page and verify detection.",
    )
    arguments = parser.parse_args()
    if not arguments.self_check and not arguments.url:
        parser.error("provide a URL or --self-check")

    expected_violations = arguments.self_check
    try:
        violations: list[dict[str, Any]]
        if arguments.self_check:
            violations = self_check()
        else:
            violations = inspect_url(arguments.url, arguments.duration)
    except (RuntimeError, AssertionError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 2

    print(
        json.dumps(
            {
                "status": (
                    "self_check_passed"
                    if expected_violations
                    else "violations" if violations else "passed"
                ),
                "violations": violations,
            },
            indent=2,
        )
    )
    return 0 if expected_violations or not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
