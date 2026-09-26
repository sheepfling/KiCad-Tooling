"""Tests for deterministic Markdown layout and repository-documentation policy."""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.documentation import check
from kicad_tooling.hwrepo.models import DocumentationException, DocumentationPolicy


class DocumentationPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory[str]()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        (self.root / "catalog").mkdir()

    def write_policy(
        self,
        roots: tuple[str, ...] = ("README.md",),
        exceptions: tuple[DocumentationException, ...] = (),
    ) -> None:
        write_model(
            self.root / "catalog/documentation-policy.json",
            DocumentationPolicy(roots=roots, exceptions=exceptions),
        )

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def codes(self) -> set[str]:
        return {finding.code for finding in check(self.root).issues}

    def test_valid_document_graph_passes(self) -> None:
        self.write_policy()
        self.write("README.md", "# Root\n\n[Guide](docs/guide.md#usage)\n")
        self.write("docs/guide.md", "# Guide\n\n## Usage\n")

        report = check(self.root)

        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.documents, 2)

    def test_uppercase_markdown_extension_is_checked(self) -> None:
        self.write_policy()
        self.write("README.md", "# Root\n\n[Review](docs/REVIEW.MD)\n")
        self.write("docs/REVIEW.MD", "# Review\n\n[Broken](missing.md)\n")
        report = check(self.root)
        self.assertEqual(report.documents, 2)
        self.assertIn("DOC102", {finding.code for finding in report.issues})

    def test_legal_text_keeps_upstream_format_but_unsafe_links_still_fail(self) -> None:
        self.write_policy()
        self.write("README.md", "# Root\n")
        original = "Copyright fixture\n\tPreserve this upstream layout.  \n"
        self.write("vendor/LICENSE.md", original)
        self.assertEqual(self.codes(), set())
        self.assertEqual((self.root / "vendor/LICENSE.md").read_text(), original)
        self.write("vendor/LICENSE.md", original + "[Missing](missing.md)\n")
        self.assertEqual(self.codes(), {"DOC102"})

    def test_case_mismatch_and_missing_fragment_fail(self) -> None:
        self.write_policy()
        self.write(
            "README.md",
            "# Root\n\n[Wrong case](docs/Guide.md)\n[Bad fragment](#not-here)\n",
        )
        self.write("docs/guide.md", "# Guide\n")

        self.assertEqual(self.codes(), {"DOC101", "DOC103", "DOC105"})

    def test_project_readme_is_discovered_without_a_central_link_edit(self) -> None:
        self.write_policy()
        self.write("README.md", "# Repository\n")
        self.write("projects/battery-board/README.md", "# Battery board\n\n[Design](docs/design.md)\n")
        self.write("projects/battery-board/docs/design.md", "# Design notes\n")
        self.assertEqual(self.codes(), set())
        self.write("projects/battery-board/docs/forgotten.md", "# Forgotten notes\n")
        self.assertEqual(self.codes(), {"DOC105"})

    def test_parent_relative_links_within_repository_are_valid(self) -> None:
        self.write_policy()
        self.write("README.md", "# Root\n\n[Guide](docs/guide.md)\n")
        self.write("docs/guide.md", "# Guide\n\n[Home](../README.md)\n")
        self.assertEqual(self.codes(), set())
        self.write("docs/guide.md", "# Guide\n\n[Escape](../../outside.md)\n")
        self.assertEqual(self.codes(), {"DOC101"})

    def test_encoded_and_angle_bracket_spaces_resolve_without_allowing_encoded_escape(self) -> None:
        self.write_policy()
        self.write("docs/board notes.md", "# Board notes\n")
        self.write("docs/native #1.kicad_pro", "{}")
        for link in ('docs/board%20notes.md', '<docs/board notes.md> "Title"'):
            self.write("README.md", f"# Root\n\n[Board]({link})\n[Native](docs/native%20%231.kicad_pro)\n")
            self.assertEqual(self.codes(), set())
        self.write("docs/board notes.md", "# Board notes\n\n[Escape](%2E%2E/%2E%2E/outside.md)\n")
        self.assertEqual(self.codes(), {"DOC101"})

    def test_path_escape_and_orphan_fail(self) -> None:
        self.write_policy()
        self.write("README.md", "# Root\n\n[Escape](../outside.md)\n")
        self.write("docs/orphan.md", "# Orphan\n")

        self.assertEqual(self.codes(), {"DOC101", "DOC105"})

    def test_configured_documentation_namespaces_keep_the_root_uncluttered(self) -> None:
        write_model(
            self.root / "catalog/documentation-policy.json",
            DocumentationPolicy(
                roots=("README.md",),
                documentation_namespaces=("docs/workflow", "docs/team"),
            ),
        )
        self.write(
            "README.md",
            "# Root\n\n[Docs](docs/README.md)\n",
        )
        self.write(
            "docs/README.md",
            "# Documentation\n\n[Workflow](workflow/guide.md)\n[Team](team/README.md)\n"
        )
        self.write("docs/workflow/guide.md", "# Guide\n")
        self.write("docs/team/README.md", "# Team documentation\n")
        self.assertEqual(self.codes(), set())

        self.write("docs/run-2026-09-10.md", "# One run\n")
        self.assertEqual(self.codes(), {"DOC105", "DOC106"})

    def test_documentation_namespace_must_be_below_docs(self) -> None:
        write_model(
            self.root / "catalog/documentation-policy.json",
            DocumentationPolicy(
                roots=("README.md",),
                documentation_namespaces=("reports",),
            ),
        )
        self.write("README.md", "# Root\n")
        self.assertEqual(self.codes(), {"DOC900"})

    def test_unsafe_policy_path_fails_closed(self) -> None:
        self.write_policy(roots=("../outside.md",))
        self.write("README.md", "# Root\n")

        self.assertEqual(self.codes(), {"DOC900"})

    def test_layout_rules_fail_before_review(self) -> None:
        self.write_policy()
        self.write("README.md", "# Root\n\tTabbed\n\n#### Skipped\n\n```python\n")

        self.assertEqual(self.codes(), {"MD001", "MD003", "MD005"})

    def test_active_scoped_exception_is_used_but_expired_exception_fails(self) -> None:
        active = DocumentationException(
            id="permit-tabs",
            code="MD001",
            path="README.md",
            reason="Compatibility fixture under review.",
            expires=date(2026, 9, 8),
        )
        expired = DocumentationException(
            id="expired-example",
            code="MD002",
            path="README.md",
            reason="Demonstrates expiry enforcement.",
            expires=date(2026, 9, 6),
        )
        self.write_policy(exceptions=(active, expired))
        self.write("README.md", "# Root\n\tCompatibility fixture\n")

        report = check(self.root, today=date(2026, 9, 7))

        self.assertEqual(report.status, "FAIL")
        self.assertEqual({finding.code for finding in report.issues}, {"DOC201"})


if __name__ == "__main__":
    unittest.main()
