from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
SOURCE_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".svelte"}
FORBIDDEN_API = re.compile(
    r"(?<![A-Za-z0-9_$])"
    r"(?P<api>localStorage|sessionStorage|indexedDB|caches|serviceWorker)"
    r"(?![A-Za-z0-9_$])"
)


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    api: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: forbidden browser storage API `{self.api}`"


def scan_file(path: Path) -> list[Violation]:
    source = path.read_text(encoding="utf-8")
    return [
        Violation(path, source.count("\n", 0, match.start()) + 1, match.group("api"))
        for match in FORBIDDEN_API.finditer(source)
    ]


def scan_sources(paths: Iterable[Path]) -> list[Violation]:
    violations: list[Violation] = []
    for path in paths:
        if path.is_dir():
            candidates = (
                child
                for child in path.rglob("*")
                if child.is_file() and child.suffix.casefold() in SOURCE_EXTENSIONS
            )
        elif path.is_file() and path.suffix.casefold() in SOURCE_EXTENSIONS:
            candidates = iter((path,))
        else:
            candidates = iter(())
        for candidate in candidates:
            violations.extend(scan_file(candidate))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reject persistent browser-storage API references in frontend source."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Source files/directories to inspect (defaults to frontend/src).",
    )
    args = parser.parse_args()
    paths = args.paths or [SOURCE_ROOT]
    violations = scan_sources(paths)
    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        print(f"Storage API lint failed: {len(violations)} violation(s).", file=sys.stderr)
        return 1
    print(f"Storage API lint passed: {len(paths)} source path(s) scanned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
