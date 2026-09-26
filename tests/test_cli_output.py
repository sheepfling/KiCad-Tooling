"""Human summaries and machine JSON remain distinct CLI contracts."""
from __future__ import annotations

import json
import sys
import unittest
from io import StringIO
from unittest.mock import patch

from kicad_tooling.hwrepo.cli_output import issue_text, summary
from kicad_tooling.hwrepo.models import (
    CheckAllSummary,
    DocumentationIssue,
    EnvironmentCheck,
    GenerationReport,
    GovernanceLintReport,
    ProductPolicyReport,
    ProjectCheckSummary,
    ProjectStaticPipelineReport,
    ProjectTestsReport,
    RepositoryPolicyReport,
    TemplateDoctorReport,
)
from kicad_tooling.template import main as template_main


class CliOutputTests(unittest.TestCase):
    def test_documentation_issue_keeps_file_and_line(self) -> None:
        issue = DocumentationIssue(
            code="MD001", path="projects/board/docs/notes.md", line=12,
            message="Tabs are not permitted",
        )
        self.assertEqual(
            issue_text(issue.model_dump(mode="json")),
            "MD001 at projects/board/docs/notes.md:12: Tabs are not permitted",
        )

    def test_nested_issue_overflow_points_to_full_json(self) -> None:
        report = ProjectStaticPipelineReport(
            status="FAIL", projects=("controller",),
            registry=GovernanceLintReport(projects=("controller",), issues=(), status="PASS"),
            repository=RepositoryPolicyReport(
                status="FAIL", issues=tuple(f"Problem {n}" for n in range(6)),
            ),
            product=ProductPolicyReport(status="PASS", products=(), open_items={}, issues=()),
            generation=GenerationReport(status="PASS", issues=()),
            project_tests=ProjectTestsReport(status="PASS", commands={}),
        )
        output = summary("Portable check", report)
        self.assertIn("Problem 0", output)
        self.assertNotIn("Problem 5", output)
        self.assertIn("More findings are available with --format json", output)

    def test_native_summary_shows_failing_project_and_receipt(self) -> None:
        report = CheckAllSummary(
            governance=GovernanceLintReport(projects=("controller",), issues=(), status="PASS"),
            repository=RepositoryPolicyReport(status="PASS", issues=()),
            product_policy=ProductPolicyReport(
                status="PASS", products=(), open_items={}, issues=(),
            ),
            projects=(ProjectCheckSummary(
                id="controller", status="FAIL", summary="controller/summary.json",
            ),),
            status="FAIL",
        )
        output = summary("Native KiCad check", report)
        self.assertIn("controller: FAIL (controller/summary.json)", output)
        self.assertNotIn("{'id':", output)

    def test_doctor_text_coaches_while_default_stdout_remains_json(self) -> None:
        report = TemplateDoctorReport(
            native_requested=False,
            checks=(EnvironmentCheck(
                id="git", required=True, status="FAIL", expected="Git on PATH",
                observed=None, next_action="Install Git and retry.",
            ),),
            status="FAIL", next_actions=("Repair Git before adoption.",),
        )
        with (
            patch("kicad_tooling.template.doctor", return_value=report),
            patch.object(sys, "argv", ["kicad_tooling.template", "doctor", "--format", "text"]),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(template_main(), 1)
        self.assertIn("Template doctor: FAIL", output.getvalue())
        self.assertIn("git: FAIL", output.getvalue())
        self.assertIn("Next: Install Git and retry.", output.getvalue())
        with (
            patch("kicad_tooling.template.doctor", return_value=report),
            patch.object(sys, "argv", ["kicad_tooling.template", "doctor"]),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(template_main(), 1)
        self.assertEqual(json.loads(output.getvalue())["checks"][0]["id"], "git")


if __name__ == "__main__":
    unittest.main()
