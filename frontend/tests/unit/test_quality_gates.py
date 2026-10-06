import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

from check_lockfiles import backend_lock_errors, frontend_lock_errors  # noqa: E402
from check_storage_api import scan_sources  # noqa: E402


class StorageApiLintTests(unittest.TestCase):
    def test_detects_banned_storage_apis_in_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "storage_fixture.ts"
            fixture.write_text(
                "\n".join(
                    (
                        "window.localStorage.setItem('a', 'b');",
                        "window.sessionStorage.clear();",
                        "indexedDB.open('db');",
                        "caches.open('media');",
                        "navigator.serviceWorker.register('/worker.js');",
                    )
                ),
                encoding="utf-8",
            )

            violations = scan_sources([fixture])

        self.assertEqual(
            [violation.api for violation in violations],
            [
                "localStorage",
                "sessionStorage",
                "indexedDB",
                "caches",
                "serviceWorker",
            ],
        )

    def test_clean_source_passes_and_non_source_files_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "app.ts"
            source.write_text("export const value = 1;", encoding="utf-8")
            documentation = root / "note.md"
            documentation.write_text("Do not use localStorage.", encoding="utf-8")

            violations = scan_sources([root])

        self.assertEqual(violations, [])


class LockfileFreshnessTests(unittest.TestCase):
    def test_frontend_manifest_mutation_fails_lockfile_check(self) -> None:
        manifest = {"name": "client", "version": "1.0.0", "dependencies": {"svelte": "^5"}}
        lockfile = {
            "lockfileVersion": 3,
            "packages": {
                "": {
                    "name": "client",
                    "version": "1.0.0",
                    "dependencies": {"svelte": "^5"},
                    "devDependencies": {},
                }
            },
        }
        self.assertEqual(frontend_lock_errors(manifest, lockfile), [])

        changed_manifest = copy.deepcopy(manifest)
        changed_manifest["dependencies"]["svelte"] = "^6"

        self.assertTrue(frontend_lock_errors(changed_manifest, lockfile))

    def test_backend_manifest_mutation_fails_lockfile_check(self) -> None:
        manifest = b'[project]\nname = "backend"\n'
        digest = hashlib.sha256(manifest).hexdigest()
        lock = "# pyproject-sha256: " + digest
        self.assertEqual(backend_lock_errors(manifest, lock), [])
        self.assertTrue(backend_lock_errors(manifest + b"# changed\n", lock))

    def test_compliance_manifest_mutation_fails_backend_lock_check(self) -> None:
        manifest = b'[project]\nname = "backend"\n'
        compliance = b"watchdog==6.0.0\n"
        digest = hashlib.sha256(manifest + b"\0" + compliance).hexdigest()
        lock = f"# pyproject-sha256: {digest}\nwatchdog==6.0.0\n"

        self.assertEqual(
            backend_lock_errors(manifest, lock, compliance),
            [],
        )
        self.assertTrue(
            backend_lock_errors(
                manifest,
                lock,
                b"watchdog==6.0.1\n",
            )
        )


if __name__ == "__main__":
    unittest.main()
