from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
for site_packages in (
    ROOT / ".venv" / "Lib" / "site-packages",
    *ROOT.glob(".venv/lib/python*/site-packages"),
):
    if site_packages.is_dir():
        sys.path.insert(0, str(site_packages))

from backend.app.domain.models import canonical_model_schemas  # noqa: E402


def _typescript_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    if "anyOf" in schema:
        return " | ".join(_typescript_type(option) for option in schema["anyOf"])
    schema_type = schema.get("type")
    if schema_type == "null":
        return "null"
    if schema_type == "array":
        return f"{_typescript_type(schema['items'])}[]"
    if schema_type == "string":
        return "string"
    if schema_type in ("integer", "number"):
        return "number"
    if schema_type == "boolean":
        return "boolean"
    raise ValueError(f"Unsupported OpenAPI schema: {schema!r}")


def render_types(schemas: dict[str, dict[str, Any]]) -> str:
    lines = [
        "// Generated from backend OpenAPI canonical schemas by scripts/check_schema_drift.py.",
    ]
    for name in sorted(schemas):
        schema = schemas[name]
        if "enum" in schema:
            values = " | ".join(json.dumps(value) for value in schema["enum"])
            lines.extend(("", f"export type {name} = {values};"))
            continue

        properties = schema.get("properties")
        if schema.get("type") != "object" or not isinstance(properties, dict):
            raise ValueError(f"Unsupported OpenAPI model schema for {name}.")
        required = set(schema.get("required", []))
        lines.extend(("", f"export type {name} = {{"))
        for prop_name, prop_schema in properties.items():
            optional = "" if prop_name in required else "?"
            lines.append(
                f"  {prop_name}{optional}: {_typescript_type(prop_schema)};"
            )
        lines.append("};")
    return "\n".join(lines) + "\n"


def check_schema_drift(
    types_path: Path, schemas: dict[str, dict[str, Any]] | None = None
) -> bool:
    expected = render_types(schemas if schemas is not None else canonical_model_schemas())
    actual = types_path.read_text(encoding="utf-8")
    if actual == expected:
        return True
    print(
        f"Schema drift detected: regenerate {types_path.relative_to(ROOT)} "
        "with `python scripts/check_schema_drift.py --write`.",
        file=sys.stderr,
    )
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Generate the checked-in TypeScript API types from backend schemas.",
    )
    args = parser.parse_args()
    types_path = ROOT / "frontend" / "src" / "types" / "api.ts"
    expected = render_types(canonical_model_schemas())
    if args.write:
        types_path.write_text(expected, encoding="utf-8")
        return 0
    return 0 if check_schema_drift(types_path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
