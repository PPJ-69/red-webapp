from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FRONTEND_ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"


def frontend_lock_errors(
    manifest: dict[str, Any], lockfile: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if lockfile.get("lockfileVersion") != 3:
        errors.append("frontend/package-lock.json must use lockfileVersion 3.")
    locked_root = lockfile.get("packages", {}).get("")
    if not isinstance(locked_root, dict):
        return errors + ["frontend/package-lock.json has no root package entry."]
    for key in ("name", "version", "dependencies", "devDependencies"):
        if locked_root.get(key, {} if key.endswith("Dependencies") else None) != manifest.get(
            key, {} if key.endswith("Dependencies") else None
        ):
            errors.append(f"frontend/package-lock.json root {key} is stale.")
    return errors


def backend_lock_errors(
    pyproject: bytes,
    lockfile: str,
    compliance_requirements: bytes = b"",
) -> list[str]:
    digest_source = pyproject + (
        b"\0" + compliance_requirements if compliance_requirements else b""
    )
    digest = hashlib.sha256(digest_source).hexdigest()
    expected = f"# pyproject-sha256: {digest}"
    first_line = lockfile.splitlines()[0] if lockfile else ""
    if first_line != expected:
        return [
            "backend/requirements.lock is stale; regenerate it from pyproject.toml "
            "and tools/compliance/requirements.txt."
        ]

    locked_packages = {
        re.split(r"[<=>!~]", line.strip(), maxsplit=1)[0]
        .casefold()
        .replace("_", "-"): line.strip().split("==", 1)[-1]
        for line in lockfile.splitlines()[1:]
        if line and not line.startswith("#") and "==" in line
    }
    errors: list[str] = []
    for requirement in compliance_requirements.decode("utf-8").splitlines():
        requirement = requirement.strip()
        if not requirement or requirement.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", requirement)
        if match is None:
            errors.append(f"Compliance requirement is not exactly pinned: {requirement}")
            continue
        name, version = match.groups()
        locked_version = locked_packages.get(name.casefold().replace("_", "-"))
        if locked_version != version:
            errors.append(
                f"backend/requirements.lock must pin {name}=={version} "
                "from tools/compliance/requirements.txt."
            )
    return errors


def check_lockfiles(
    frontend_manifest_path: Path = FRONTEND_ROOT / "package.json",
    frontend_lock_path: Path = FRONTEND_ROOT / "package-lock.json",
    backend_manifest_path: Path = BACKEND_ROOT / "pyproject.toml",
    backend_lock_path: Path = BACKEND_ROOT / "requirements.lock",
) -> list[str]:
    errors: list[str] = []
    try:
        manifest = json.loads(frontend_manifest_path.read_text(encoding="utf-8"))
        lockfile = json.loads(frontend_lock_path.read_text(encoding="utf-8"))
        errors.extend(frontend_lock_errors(manifest, lockfile))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Unable to read frontend manifest/lockfile: {exc}")

    try:
        pyproject = backend_manifest_path.read_bytes()
        tomllib.loads(pyproject.decode("utf-8"))
        lock = backend_lock_path.read_text(encoding="utf-8")
        compliance_requirements = (
            PROJECT_ROOT / "tools" / "compliance" / "requirements.txt"
        ).read_bytes()
        errors.extend(
            backend_lock_errors(pyproject, lock, compliance_requirements)
        )
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"Unable to read backend manifest/lockfile: {exc}")
    return errors


def main() -> int:
    errors = check_lockfiles()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Frontend and backend lockfiles match their manifests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
