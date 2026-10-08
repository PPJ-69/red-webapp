import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "frontend" / "scripts"))

from check_schema_drift import check_schema_drift, render_types
from backend.app.domain.models import canonical_model_schemas


class SchemaDriftTests(unittest.TestCase):
    def test_checked_in_types_match_backend_openapi_models(self) -> None:
        self.assertTrue(check_schema_drift(ROOT / "frontend" / "src" / "types" / "api.ts"))

    def test_mutated_openapi_model_changes_generated_types(self) -> None:
        schemas = canonical_model_schemas()
        mutated = copy.deepcopy(schemas)
        mutated["MediaItem"]["properties"]["newField"] = {"type": "string"}

        self.assertNotEqual(render_types(schemas), render_types(mutated))
        self.assertIn("newField?: string;", render_types(mutated))
        self.assertFalse(
            check_schema_drift(
                ROOT / "frontend" / "src" / "types" / "api.ts",
                mutated,
            )
        )

    def test_unconstrained_schema_generates_unknown_type(self) -> None:
        generated = render_types(
            {
                "Example": {
                    "type": "object",
                    "properties": {
                        "value": {},
                        "nullableValue": {
                            "anyOf": [{}, {"type": "null"}],
                        },
                    },
                },
            }
        )

        self.assertIn("value?: unknown;", generated)
        self.assertIn("nullableValue?: unknown | null;", generated)


if __name__ == "__main__":
    unittest.main()
