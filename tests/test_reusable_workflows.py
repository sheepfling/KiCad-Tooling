"""Guard the trust boundary of workflows executed inside an adopting repository."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github/workflows"
PROJECT_WORKFLOWS = (
    "kicad-template.yml",
    "3d-preview.yml",
    "electrical-analysis.yml",
    "release-candidate.yml",
)


class ReusableWorkflowTests(unittest.TestCase):
    def test_project_jobs_check_out_caller_source_and_install_its_reviewed_pin(self) -> None:
        for name in PROJECT_WORKFLOWS:
            with self.subTest(workflow=name):
                workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
                jobs = workflow.split("\njobs:\n", 1)[1]
                checkouts = jobs.count("uses: actions/checkout@")
                self.assertGreater(checkouts, 0)
                self.assertEqual(checkouts, jobs.count("-r requirements-tooling.txt"))
                self.assertEqual(checkouts, jobs.count("persist-credentials: false"))
                # No provider checkout, ref override, or alternate workspace may replace
                # the adopting repository and its pull-request merge commit.
                self.assertNotRegex(jobs, r"(?m)^\s+(repository|ref|working-directory):")
                self.assertNotIn("KICAD_TEMPLATE_ROOT", jobs)
                self.assertNotIn("PYTHONPATH", jobs)

    def test_calls_cannot_elevate_permissions_or_interpolate_inputs_into_shell(self) -> None:
        for name in PROJECT_WORKFLOWS:
            with self.subTest(workflow=name):
                workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
                self.assertIn("  workflow_call:\n", workflow)
                self.assertIn("permissions:\n  contents: read\n", workflow)
                for forbidden in (
                    "secrets:",
                    "write-all",
                    ": write",
                    "pull_request_target:",
                    "continue-on-error:",
                    "concurrency:",
                ):
                    self.assertNotIn(forbidden, workflow)
                for command in re.findall(r"(?ms)^\s+run:.*?(?=^\s+- |\Z)", workflow):
                    self.assertNotIn("${{ inputs.", command)
                for action in re.findall(r"uses: ([^\s]+)", workflow):
                    self.assertRegex(action, r"^[\w/-]+@[0-9a-f]{40}$")

    def test_manual_lanes_keep_failure_receipts(self) -> None:
        for name in PROJECT_WORKFLOWS[1:]:
            with self.subTest(workflow=name):
                workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
                self.assertIn("      project_id:\n", workflow)
                self.assertIn("        required: true\n        type: string", workflow)
                self.assertIn("if: always()", workflow)
                self.assertIn("build/ci-hosted/", workflow)
                self.assertIn("retention-days: 30", workflow)


if __name__ == "__main__":
    unittest.main()
