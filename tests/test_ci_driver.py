"""Unit tests for the single CI entry point that GitHub invokes."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.ci import main, project_static_pipeline, run_command, static_pipeline
from kicad_tooling.ci_hosted import gate_result
from kicad_tooling.hwrepo.documentation import check as documentation_check
from kicad_tooling.hwrepo.models import CommandEvidence, StaticPipelineReport
from tests.support import reference_root

ROOT = reference_root()


def evidence(returncode: int) -> CommandEvidence:
    return CommandEvidence(
        argv=("quality-tool",),
        started_utc=datetime.now(UTC).isoformat(),
        returncode=returncode,
    )


class CiDriverTests(unittest.TestCase):
    def test_manual_focus_cannot_cancel_main_or_another_manual_run(self) -> None:
        workflow = (ROOT / ".github/workflows/kicad-template.yml").read_text(encoding="utf-8")
        self.assertIn(
            "group: kicad-template-${{ github.event_name }}-${{ github.event_name == 'workflow_dispatch' && github.run_id || github.ref }}",
            workflow,
        )

    def test_missing_quality_tool_is_a_typed_failure(self) -> None:
        result = run_command(ROOT, "intentionally-absent-quality-tool")
        self.assertEqual(result.returncode, 127)
        self.assertIsNotNone(result.error)

    def test_repository_pipeline_requires_markdown_and_leaves_tooling_tests_to_package_ci(self) -> None:
        with patch("kicad_tooling.ci.run_command", side_effect=(
            evidence(0), evidence(1))) as command:
            result = static_pipeline(ROOT, None)
        if not isinstance(result, StaticPipelineReport):
            self.fail("The unselected CI lane must return the full repository report")
        self.assertEqual(result.scope, "repository_static")
        self.assertIsNotNone(result.tooling_version)
        self.assertEqual(result.registry.status, "PASS")
        self.assertEqual(result.documentation.status, "PASS")
        self.assertEqual(result.rumdl.returncode, 0)
        self.assertEqual(result.mdrepo.returncode, 1)
        self.assertIsNone(result.ruff)
        self.assertIsNone(result.pyright)
        self.assertIsNone(result.unit_tests)
        self.assertEqual(command.call_count, 2)
        self.assertEqual(result.status, "FAIL")

    def test_each_markdown_command_is_required_by_full_pipeline(self) -> None:
        for failed_index, name in ((0, "rumdl"), (1, "mdrepo")):
            with self.subTest(check=name):
                outcomes = [evidence(0) for _ in range(2)]
                outcomes[failed_index] = evidence(1)
                with patch("kicad_tooling.ci.run_command", side_effect=outcomes):
                    result = static_pipeline(ROOT, None)
                if not isinstance(result, StaticPipelineReport):
                    self.fail("The full lane must return the full repository report")
                self.assertEqual(getattr(result, name).returncode, 1)
                self.assertEqual(result.status, "FAIL")

    def test_markdown_check_uses_the_installed_package_module(self) -> None:
        with patch("kicad_tooling.ci.run_command", return_value=evidence(0)) as command:
            static_pipeline(ROOT, None)
        self.assertEqual(command.call_args_list[0].args,
                         (ROOT, sys.executable, "-I", "-m", "kicad_tooling.markdown_check",
                          "check", ".", "--no-cache"))

    def test_mdrepo_roots_follow_documentation_roots(self) -> None:
        config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        configured = tuple(config["tool"]["mdrepo"]["orphans"]["roots"])
        self.assertEqual(configured, documentation_check(ROOT).roots)

    def test_project_pipeline_skips_repository_wide_python_quality_commands(self) -> None:
        with patch("kicad_tooling.ci.run_command") as command:
            result = project_static_pipeline(ROOT, ("controller",))
        command.assert_not_called()
        self.assertEqual(result.scope, "project_static")
        self.assertEqual(result.projects, ("controller",))
        self.assertEqual(result.status, "PASS")

    def test_module_entrypoint_scopes_a_local_project_check(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-m", "kicad_tooling.ci", "--project", "controller"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["scope"], "project_static")
        self.assertNotIn("ruff", report)

    def test_selected_project_can_print_a_short_human_summary(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-m", "kicad_tooling.ci", "--project", "controller",
             "--format", "text"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Portable check: PASS", result.stdout)
        self.assertIn("Projects: controller", result.stdout)
        self.assertIn("registry: PASS", result.stdout)

    def test_failed_project_text_points_to_the_diagnostic_command(self) -> None:
        with (
            patch.object(sys, "argv", [
                "ci.py", "--root", str(ROOT), "--project", "controller",
                "--format", "text",
            ]),
            patch("kicad_tooling.ci.check_generation", return_value=("Outdated BOM view",)),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(main(), 1)
        self.assertIn("generation: FAIL", output.getvalue())
        self.assertIn("Outdated BOM view", output.getvalue())
        self.assertIn(
            "python -B -m kicad_tooling.template diagnose --project-id controller",
            output.getvalue(),
        )

    def test_portable_journal_retains_completed_phases_after_crash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="portable-journal-") as temporary:
            output = Path(temporary) / "run"
            with (
                patch.object(sys, "argv", ["ci.py", "--root", str(ROOT), "--project", "controller",
                                         "--output", str(output)]),
                patch("kicad_tooling.ci.check_repository", side_effect=RuntimeError("unexpected failure")),
                patch("sys.stdout", new_callable=StringIO),
                patch("sys.stderr", new_callable=StringIO),
                self.assertRaisesRegex(RuntimeError, "unexpected failure"),
            ):
                main()
            self.assertEqual(json.loads((output / "run.json").read_text())["status"], "ERROR")
            self.assertTrue((output / "registry.json").is_file())
            self.assertFalse((output / "portable.json").exists())
            events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
            self.assertTrue(any(event["stage"] == "repository" and event["status"] == "ERROR"
                                for event in events))

    def test_module_entrypoint_selects_projects_by_metadata_tag(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-m", "kicad_tooling.ci", "--tag", "status-led"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(
            report["projects"],
            ['arduino-uno-status-led', 'raspberry-pi-status-led', 'status-indicator-harness-interface', 'status-indicator-wiring'],
        )

    def test_module_entrypoint_selects_an_indexed_product(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-m", "kicad_tooling.ci", "--product", "status-indicator-system"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["scope"], "project_static")
        self.assertEqual(
            report["projects"],
            [
                "arduino-uno-status-led",
                "raspberry-pi-status-led",
                "status-indicator-harness-interface",
                "status-indicator-wiring",
            ],
        )

    def test_unknown_product_is_an_explicit_selection_error(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-m", "kicad_tooling.ci", "--product", "unknown-product"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown-product", result.stderr)

    def test_native_matrix_honors_product_and_excluded_tag(self) -> None:
        result = subprocess.run(
            [
                sys.executable, "-I", "-B", "-m", "kicad_tooling.ci", "--matrix",
                "--product", "status-indicator-system", "--exclude-tag", "arduino",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            {entry["project"] for entry in json.loads(result.stdout)["include"]},
            {
                "raspberry-pi-status-led",
                "status-indicator-harness-interface",
                "status-indicator-wiring",
            },
        )

    def test_manual_impact_selectors_plan_only_requested_project_lanes(self) -> None:
        cases = (
            (("--select-project", "controller"), ["controller"]),
            (("--select-product", "status-indicator-system"), [
                "arduino-uno-status-led",
                "raspberry-pi-status-led",
                "status-indicator-harness-interface",
                "status-indicator-wiring",
            ]),
            (("--select-tag", "status-led", "--exclude-tag", "arduino"), [
                "raspberry-pi-status-led",
                "status-indicator-harness-interface",
                "status-indicator-wiring",
            ]),
        )
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-m", "kicad_tooling.impact", *arguments],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                plan = json.loads(result.stdout)
                self.assertEqual(plan["scope"], "focused")
                self.assertEqual(plan["projects"], expected)
                self.assertEqual(plan["changed_paths"], [])

    def test_manual_impact_selection_rejects_missing_or_empty_scope(self) -> None:
        cases = (
            ("--select-project", "unknown-board"),
            ("--select-product", "unknown-product"),
            ("--select-tag", "unknown-tag"),
            ("--select-project", "controller", "--exclude-tag", "legacy"),
            ("--full", "--exclude-tag", "reference"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-m", "kicad_tooling.impact", *arguments],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertTrue(result.stderr.strip())

    def test_matrix_mode_is_one_json_line_for_github_output(self) -> None:
        with (
            patch.object(sys, "argv", ["ci.py", "--root", str(ROOT), "--matrix"]),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(main(), 0)
        self.assertEqual(len(output.getvalue().splitlines()), 1)

    def test_metrics_text_reuses_the_read_only_summary(self) -> None:
        with (
            patch.object(sys, "argv", ["ci.py", "--root", str(ROOT), "--metrics", "--format", "text"]),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(main(), 0)
        self.assertIn("Template metrics:", output.getvalue())
        self.assertIn("Build authorized: no", output.getvalue())

    def test_module_entrypoint_resolves_the_package_without_path_injection(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-m", "kicad_tooling.ci", "--matrix"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("include", json.loads(result.stdout))

    def test_metrics_mode_uses_the_central_ci_driver(self) -> None:
        with (
            patch.object(sys, "argv", ["ci.py", "--root", str(ROOT), "--metrics"]),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(main(), 0)
        self.assertEqual(json.loads(output.getvalue())["lane"], "TEMPLATE_METRICS")

    def test_native_workflow_passes_the_selected_project_and_uses_declared_dependencies(self) -> None:
        workflow = (ROOT / ".github/workflows/kicad-template.yml").read_text(encoding="utf-8")
        native = workflow.split("  kicad:\n", 1)[1].split("  release-rehearsal:\n", 1)[0]
        self.assertIn('kicad_tooling.ci_hosted native --project "$PROJECT_ID"', native)
        self.assertIn('--image "$KICAD_IMAGE" --pr-head "$PR_HEAD"', native)
        self.assertIn('--fault-probes "$FAULT_PROBES"', native)
        self.assertNotIn("docker run", native)
        self.assertNotIn("kicad_tooling.native_deps", native)
        self.assertNotIn("pydantic==", workflow)
        self.assertIn("needs: [scope, project-matrix, python-tests, kicad, release-rehearsal]", workflow)

    def test_hosted_native_and_release_work_do_not_wait_for_windows(self) -> None:
        workflow = (ROOT / ".github/workflows/kicad-template.yml").read_text(encoding="utf-8")
        native = workflow.split("  kicad:\n", 1)[1].split("  release-rehearsal:\n", 1)[0]
        release = workflow.split("  release-rehearsal:\n", 1)[1].split("  engineering-gate:\n", 1)[0]
        self.assertIn("needs: [scope, project-matrix]", native)
        self.assertIn("needs: [scope, kicad]", release)
        self.assertNotIn("python-tests", native)
        self.assertNotIn("python-tests", release)

    def test_hosted_scope_runs_focused_prs_and_full_main_or_manual_checks(self) -> None:
        workflow = (ROOT / ".github/workflows/kicad-template.yml").read_text(encoding="utf-8")
        scope = workflow.split("  scope:\n", 1)[1].split("  project-matrix:\n", 1)[0]
        matrix = workflow.split("  project-matrix:\n", 1)[1].split("  python-tests:\n", 1)[0]
        portable = workflow.split("  python-tests:\n", 1)[1].split("  kicad:\n", 1)[0]
        release = workflow.split("  release-rehearsal:\n", 1)[1].split("  engineering-gate:\n", 1)[0]
        self.assertIn("fetch-depth: 0", scope)
        self.assertIn('kicad_tooling.ci_hosted plan --event "$EVENT_NAME" --base "$BASE_SHA"', scope)
        self.assertIn('--focus "$DISPATCH_FOCUS" --value "$DISPATCH_VALUE"', scope)
        self.assertIn('kicad_tooling.ci_hosted matrix --scope "$CHECK_SCOPE" --projects "$CI_PROJECTS"', matrix)
        self.assertIn("needs.scope.outputs.scope != 'docs'", matrix)
        self.assertIn('fromJSON(needs.scope.outputs.portable-matrix)', portable)
        self.assertIn('kicad_tooling.ci_hosted portable --scope "$CHECK_SCOPE"', portable)
        self.assertIn('--projects "$CI_PROJECTS" --docs-changed "$DOCS_CHANGED" --jobs 4', portable)
        self.assertIn("timeout-minutes: 13", portable)
        self.assertIn("cache-dependency-path: requirements-tooling.txt", portable)
        self.assertIn("if: matrix.os != 'windows-2022'", portable)
        self.assertIn("pip install --disable-pip-version-check -r requirements-tooling.txt", portable)
        self.assertNotIn("kicad_tooling.ci_hosted windows-types", portable)
        self.assertIn("kicad_tooling.ci_hosted windows-smoke", portable)
        self.assertIn("kicad_tooling.ci_hosted source-clean", portable)
        self.assertIn("if: needs.scope.outputs.scope == 'full' && matrix.os != 'windows-2022'", portable)
        self.assertIn("if: needs.scope.outputs.scope == 'full' && needs.kicad.result == 'success'", release)
        self.assertIn("kicad_tooling.ci_hosted release", release)

    def test_manual_dispatch_wires_typed_focus_inputs_into_the_planner(self) -> None:
        workflow = (ROOT / ".github/workflows/kicad-template.yml").read_text(encoding="utf-8")
        dispatch = workflow.split("  workflow_dispatch:\n", 1)[1].split("  push:\n", 1)[0]
        scope = workflow.split("  scope:\n", 1)[1].split("  project-matrix:\n", 1)[0]
        self.assertIn("options: [full, branch, project, product, tag]", dispatch)
        for field in ("focus", "value", "exclude_tag", "shard"):
            self.assertIn(f"      {field}:\n", dispatch)
        self.assertIn("DISPATCH_FOCUS: ${{ inputs.focus || 'full' }}", scope)
        self.assertIn("DISPATCH_VALUE: ${{ inputs.value || '' }}", scope)
        self.assertIn("DISPATCH_EXCLUDE_TAG: ${{ inputs.exclude_tag || '' }}", scope)
        self.assertIn("DISPATCH_SHARD: ${{ inputs.shard || '' }}", scope)
        self.assertIn('--exclude-tag "$DISPATCH_EXCLUDE_TAG" --shard "$DISPATCH_SHARD"', scope)

    def test_workflow_delegates_policy_work_to_the_driver(self) -> None:
        workflow = (ROOT / ".github/workflows/kicad-template.yml").read_text(encoding="utf-8")
        self.assertNotRegex(workflow, r"\bpython(?:3)?\s+(?!-m\b)[^\n]*tools[/\\][^\n]*\.py")
        for embedded in ("docker run", "<<'PY'", 'case "$CHECK_SCOPE"',
                         "tools/ci.py", "tools/check_all.py"):
            self.assertNotIn(embedded, workflow)
        for mode in ("plan", "matrix", "portable", "windows-smoke",
                     "native", "release", "gate"):
            self.assertIn(f"kicad_tooling.ci_hosted {mode}", workflow)
        self.assertLessEqual(len(workflow.splitlines()), 275)

    def test_dependency_updates_are_bounded_and_cover_python_and_actions(self) -> None:
        policy = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: pip", policy)
        self.assertIn("package-ecosystem: github-actions", policy)
        self.assertEqual(policy.count("interval: monthly"), 2)
        self.assertEqual(policy.count("open-pull-requests-limit: 3"), 2)

    def test_final_hosted_gate_rejects_incomplete_results(self) -> None:
        workflow = (ROOT / ".github/workflows/kicad-template.yml").read_text(encoding="utf-8")
        self.assertIn("run: python -B -m kicad_tooling.ci_hosted gate", workflow)
        baselines = (
            ("success", "docs", "success", "skipped", "skipped", "", "skipped"),
            ("success", "focused", "success", "success", "success", "true", "skipped"),
            ("success", "full", "success", "success", "success", "true", "success"),
            ("success", "full", "success", "success", "skipped", "false", "skipped"),
        )
        for baseline in baselines:
            with self.subTest(baseline=baseline):
                gate_result(*baseline)
                for position in (0, 1, 2, 3, 4, 6):
                    broken = list(baseline)
                    broken[position] = "cancelled"
                    with self.assertRaises(ValueError):
                        gate_result(*broken)
                if baseline[1] != "docs":
                    broken = list(baseline)
                    broken[5] = "" if baseline[5] == "true" else "true"
                    with self.assertRaises(ValueError):
                        gate_result(*broken)


if __name__ == "__main__":
    unittest.main()
