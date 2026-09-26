"""Deterministic contracts for Markdown produced by repository workflows."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from snakemd import Document

from kicad_tooling.hwrepo.markdown import (
    design_notes,
    imported_project_readme,
    markdown_text,
    project_readme,
    release_review,
    retitled_document,
    write_markdown,
)


class MarkdownGenerationTests(unittest.TestCase):
    def test_project_scaffold_documents_are_typed_and_deterministic(self) -> None:
        readme = project_readme("battery-board")
        notes = design_notes()
        self.assertIsInstance(readme, Document)
        self.assertIsInstance(notes, Document)
        self.assertEqual(
            f"{readme}\n",
            "# battery-board\n\n"
            "Development project — NOT FOR MANUFACTURE.\n\n"
            "Create the native project in `kicad/` using the toolchain selected in "
            "[project.json](project.json). Complete the source inventory and "
            "[test contract](tests/contract.json). See [design notes](docs/README.md).\n\n"
            "From the repository root: "
            "`python -B -m kicad_tooling.verify --project battery-board`.\n\n"
            "Checks will fail until the native files and engineering expectations exist. "
            "After they are authored, add --depth native for exact KiCad checks and an ignored receipt.\n",
        )
        self.assertEqual(
            f"{notes}\n",
            "# Design notes\n\n"
            "Record purpose, requirements, interfaces, design decisions and "
            "bring-up results here.\n",
        )

    def test_import_document_encodes_native_paths_and_lists_upstream_docs(self) -> None:
        document = imported_project_readme(
            "battery-board",
            "kicad/Old board.kicad_pro",
            ("Board notes.md", "docs/Bring-up #1.md"),
        )
        rendered = str(document)
        self.assertIn("[the native project](kicad/Old%20board.kicad_pro)", rendered)
        self.assertIn("- [Upstream Board notes.md](kicad/Board%20notes.md)", rendered)
        self.assertIn(
            "- [Upstream docs/Bring-up #1.md](kicad/docs/Bring-up%20%231.md)", rendered
        )

    def test_release_review_uses_inline_code_and_writer_adds_one_final_newline(self) -> None:
        document = release_review("review-001", "abc123", "engineering_review")
        self.assertEqual(
            str(document),
            "# review-001\n\n"
            "Source: `abc123`. Class: `engineering_review`.\n\n"
            "Candidate for engineering review. This report records executed checks; "
            "it is not human approval.\n\n"
            "Manufacturing and assembly files require review of layers, origin, "
            "population, and supplier requirements. Electrical models do not establish physical "
            "grounding, thermal margin, transient behavior, signal integrity or EMC. Retain the "
            "responsible engineers' design reviews and applicable measurements separately.",
        )
        with tempfile.TemporaryDirectory(prefix="markdown-writer-") as directory:
            path = Path(directory) / "review.md"
            write_markdown(path, document)
            self.assertEqual(path.read_text(encoding="utf-8"), markdown_text(document))

    def test_retitle_preserves_authored_body_with_structured_heading(self) -> None:
        document = retitled_document(
            "# Generic template\n\nIntroduction.\n\n## Usage\n\nKeep this body.\n",
            "company-hardware",
        )
        self.assertEqual(
            markdown_text(document),
            "# company-hardware\n\nIntroduction.\n\n## Usage\n\nKeep this body.\n",
        )


if __name__ == "__main__":
    unittest.main()
