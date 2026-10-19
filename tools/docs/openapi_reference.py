from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "docs" / "openapi.json"
sys.path.insert(0, str(ROOT))


def generated_openapi() -> str:
    from backend.app.main import app

    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the committed FastAPI OpenAPI reference."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if docs/openapi.json differs from the application schema",
    )
    arguments = parser.parse_args()
    expected = generated_openapi()

    if arguments.check:
        if not REFERENCE.is_file() or REFERENCE.read_text(encoding="utf-8") != expected:
            print(
                "docs/openapi.json is missing or stale; run "
                "python -B tools/docs/openapi_reference.py",
                file=sys.stderr,
            )
            return 1
        print("docs/openapi.json matches the generated FastAPI schema.")
        return 0

    REFERENCE.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Updated {REFERENCE.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
