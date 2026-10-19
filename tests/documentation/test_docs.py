from __future__ import annotations

import re
from pathlib import Path
import unittest

from tools.docs.openapi_reference import REFERENCE, generated_openapi


ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "api.md",
    ROOT / "docs" / "privacy.md",
    ROOT / "docs" / "runbook.md",
    ROOT / "docs" / "upstream-compliance-checklist.md",
    ROOT / "docs" / "security-review.md",
    ROOT / "docs" / "poc-gate-checklist.md",
    ROOT / "deploy" / "README.md",
)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
OVERCLAIM_PATTERNS = (
    re.compile(r"\bno data is ever stored\b", re.IGNORECASE),
    re.compile(r"\bnothing is ever stored\b", re.IGNORECASE),
    re.compile(r"\bcompletely private\b", re.IGNORECASE),
    re.compile(r"\b100\s*%\s*private\b", re.IGNORECASE),
    re.compile(r"\bno data leaves your device\b", re.IGNORECASE),
)


class DocumentationTests(unittest.TestCase):
    def test_local_markdown_links_resolve(self) -> None:
        broken: list[str] = []
        for document in DOCUMENTS:
            self.assertTrue(document.is_file(), f"Missing documentation: {document}")
            for destination in MARKDOWN_LINK.findall(
                document.read_text(encoding="utf-8")
            ):
                if destination.startswith(("https://", "http://", "mailto:", "#")):
                    continue
                target = destination.split("#", 1)[0]
                if not target:
                    continue
                resolved = (document.parent / target).resolve()
                if not resolved.is_file():
                    broken.append(
                        f"{document.relative_to(ROOT)} -> {destination}"
                    )
        self.assertEqual(broken, [], "Broken local Markdown links: " + "; ".join(broken))

    def test_committed_openapi_matches_application_schema(self) -> None:
        self.assertTrue(REFERENCE.is_file(), "Generate docs/openapi.json first.")
        self.assertEqual(
            REFERENCE.read_text(encoding="utf-8"),
            generated_openapi(),
            "docs/openapi.json is stale; run tools/docs/openapi_reference.py.",
        )

    def test_privacy_statement_uses_qualified_claims(self) -> None:
        documents = [
            " ".join(document.read_text(encoding="utf-8").lower().split())
            for document in DOCUMENTS
        ]
        qualified_claim = (
            "does not intentionally persist media or application data on "
            "the local machine"
        )
        privacy = " ".join(
            (ROOT / "docs" / "privacy.md")
            .read_text(encoding="utf-8")
            .lower()
            .split()
        )
        self.assertIn(qualified_claim, privacy)
        for document, content in zip(DOCUMENTS, documents):
            for pattern in OVERCLAIM_PATTERNS:
                self.assertIsNone(
                    pattern.search(content),
                    f"{document.relative_to(ROOT)}: {pattern.pattern}",
                )


if __name__ == "__main__":
    unittest.main()
