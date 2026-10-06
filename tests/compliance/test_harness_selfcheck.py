from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.compliance.fs_monitor.monitor import (
    FileSystemMonitor,
    default_monitor_roots,
)
from tools.compliance.browser_storage_check.check_browser_storage import (
    api_self_check,
    self_check as browser_self_check,
)

ROOT = Path(__file__).resolve().parents[2]


class ComplianceHarnessSelfCheckTests(unittest.TestCase):
    def test_detects_media_database_and_settings_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with FileSystemMonitor([root]) as monitor:
                (root / "clip.mp4").write_bytes(b"media")
                (root / "library.sqlite").write_bytes(b"database")
                (root / "settings.json").write_text("{}", encoding="utf-8")
                (root / "segment.webm.001.tmp").write_bytes(b"temporary media")
            violations = monitor.violations

        found = {(Path(item.path).name, item.type) for item in violations}
        self.assertIn(("clip.mp4", "media_file"), found)
        self.assertIn(("library.sqlite", "database_file"), found)
        self.assertIn(("settings.json", "settings_file"), found)
        self.assertIn(("segment.webm.001.tmp", "media_file"), found)

    def test_detects_violation_written_by_child_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with FileSystemMonitor([root]) as monitor:
                subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path('child.mp4').write_bytes(b'video')",
                    ],
                    cwd=root,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    check=True,
                )
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and not monitor.violations:
                    time.sleep(0.01)
            violations = monitor.violations

        self.assertTrue(any(item.type == "media_file" for item in violations))

    def test_excludes_committed_fixture_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture_directory = root / "tests" / "fixtures"
            fixture_directory.mkdir(parents=True)
            with FileSystemMonitor([root]) as monitor:
                (fixture_directory / "sample.mp4").write_bytes(b"fixture")
                (root / "runtime.mp4").write_bytes(b"runtime")
            violations = monitor.violations

        self.assertEqual(
            {Path(item.path).name for item in violations},
            {"runtime.mp4"},
        )

    def test_default_roots_include_existing_app_data_locations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app_data = Path(directory) / "app-data"
            app_data.mkdir()
            with patch.dict(
                os.environ,
                {
                    "APPDATA": str(app_data),
                    "LOCALAPPDATA": "",
                    "XDG_CONFIG_HOME": "",
                    "XDG_DATA_HOME": "",
                    "TEMP": str(directory),
                },
            ):
                roots = default_monitor_roots(ROOT)

        self.assertIn(app_data.resolve(), roots)

    def test_idle_backend_boot_creates_no_monitored_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with FileSystemMonitor([ROOT]) as monitor:
                environment = os.environ.copy()
                environment["APP_ENV"] = "test"
                environment["PYTHONDONTWRITEBYTECODE"] = "1"
                script = (
                    "from fastapi.testclient import TestClient; "
                    "from backend.app.main import app; "
                    "client = TestClient(app); "
                    "response = client.get('/health/ready'); "
                    "assert response.status_code == 200"
                )
                result = subprocess.run(
                    [sys.executable, "-c", script],
                    cwd=ROOT,
                    env=environment,
                    check=False,
                )
            violations = monitor.violations

        self.assertEqual(result.returncode, 0)
        self.assertEqual(violations, ())

    def test_browser_monitor_detects_service_worker_registration(self) -> None:
        violations = browser_self_check()

        self.assertTrue(
            any(
                item.get("type") == "service_worker_registration"
                for item in violations
            )
        )

    def test_browser_monitor_detects_storage_api_access(self) -> None:
        violations = api_self_check()

        self.assertTrue(
            {
                "browser:localStorage",
                "browser:sessionStorage",
                "browser:indexedDB",
                "browser:caches",
            }.issubset({item["path"] for item in violations})
        )


if __name__ == "__main__":
    unittest.main()
