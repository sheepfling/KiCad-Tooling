"""Selected one-command verification retains useful evidence across runner failures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.check_toolchain import cli_executable
from kicad_tooling.ci import project_static_pipeline
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.models import (
    CheckAllSummary,
    CheckEvidence,
    CommandEvidence,
    GovernanceLintReport,
    ProductPolicyReport,
    ProjectCheckSummary,
    RepositoryPolicyReport,
    ValidationSummary,
)
from kicad_tooling.verify import container_command, format_report, run_command, verify
from tests.support import initialize_git, reference_root


def native_summary(status: str = "PASS") -> CheckAllSummary:
    return CheckAllSummary(
        governance=GovernanceLintReport(projects=("controller",), issues=(), status="PASS"),
        repository=RepositoryPolicyReport(status="PASS", issues=()),
        product_policy=ProductPolicyReport(status="PASS", products=(), open_items={}, issues=()),
        projects=(
            ProjectCheckSummary(
                id="controller",
                status=status,
                summary="controller/summary.json",
            ),
        ),
        status=status,
    )


class VerifyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-verify-")
        self.addCleanup(temporary.cleanup)
        self.root = (Path(temporary.name) / "repository").resolve()
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        initialize_git(self.root)

    @staticmethod
    @contextmanager
    def runner_environment(local_version: str | None, docker: bool = False) -> Iterator[None]:
        def which(name: str) -> str | None:
            if name == "git":
                return "/usr/bin/git"
            if name == "docker" and docker:
                return "/usr/bin/docker"
            return None

        def output(argv: tuple[str, ...]) -> str | None:
            if "--version" in argv:
                return "git version 2.54.0"
            if "rev-parse" in argv:
                return "true"
            if "version" in argv:
                return "27.5.1"
            return None

        with (
            patch("kicad_tooling.hwrepo.doctor.shutil.which", side_effect=which),
            patch("kicad_tooling.hwrepo.doctor.command_output", side_effect=output),
            patch("kicad_tooling.hwrepo.doctor.observed_version", return_value=local_version),
        ):
            yield

    def test_portable_attempts_use_distinct_ignored_receipts_and_typed_json(self) -> None:
        first = verify(self.root, "controller")
        second = verify(self.root, "controller")
        self.assertEqual(first.status, "PASS")
        self.assertEqual(first.portable.status if first.portable is not None else None, "PASS")
        self.assertNotEqual(first.run_directory, second.run_directory)
        receipt = Path(first.run_directory)
        self.assertTrue(receipt.is_relative_to(self.root / "build"))
        self.assertEqual(json.loads((receipt / "verification.json").read_text())["status"], "PASS")
        self.assertIn("portable", (receipt / "events.log").read_text())
        self.assertEqual(json.loads((receipt / "run.json").read_text())["status"], "PASS")
        self.assertIn("Electrical analysis: NOT_RUN", format_report(first))
        self.assertIn("--init", " ".join(first.next_actions))

    def test_cli_json_stdout_stays_parseable_while_progress_goes_to_stderr(self) -> None:
        command = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.verify",
                "--root",
                str(self.root),
                "--project",
                "controller",
                "--format",
                "json",
            ),
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(command.returncode, 0, command.stderr)
        result = json.loads(command.stdout)
        self.assertEqual(result["status"], "PASS")
        self.assertIn("verify: project-selection", command.stderr)

    def test_unknown_project_produces_discovery_coaching_not_a_tool_crash(self) -> None:
        result = verify(self.root, "not-a-board")
        self.assertEqual(result.status, "FAIL")
        self.assertIsNotNone(result.diagnosis)
        assert result.diagnosis is not None
        self.assertEqual(result.diagnosis.findings[0].code, "DISCOVERY")
        self.assertTrue((Path(result.run_directory) / "diagnosis.txt").is_file())

    def test_failed_portable_diagnosis_reuses_the_captured_report(self) -> None:
        baseline = project_static_pipeline(self.root, ("controller",))
        failed = baseline.model_copy(
            update={
                "status": "FAIL",
                "registry": baseline.registry.model_copy(
                    update={
                        "status": "FAIL",
                        "issues": ("Deliberate captured registry finding",),
                    }
                ),
            }
        )
        with (
            patch("kicad_tooling.verify.project_static_pipeline", return_value=failed) as first_run,
            patch(
                "kicad_tooling.ci.project_static_pipeline",
                side_effect=AssertionError("portable rerun"),
            ) as rerun,
        ):
            result = verify(self.root, "controller")
        self.assertEqual(result.status, "FAIL", result.error)
        first_run.assert_called_once_with(self.root, ("controller",))
        rerun.assert_not_called()
        self.assertEqual(
            json.loads((Path(result.run_directory) / "portable.json").read_text()),
            failed.model_dump(mode="json"),
        )
        self.assertIsNotNone(result.diagnosis)
        assert result.diagnosis is not None
        self.assertIn(
            "Deliberate captured registry finding",
            {item.observed for item in result.diagnosis.findings},
        )

    def test_local_runner_uses_the_selected_project_and_exact_version(self) -> None:
        with (
            self.runner_environment("10.0.0"),
            patch("kicad_tooling.verify.check_all", return_value=native_summary()) as native,
        ):
            result = verify(self.root, "controller", depth="native", runner="local")
        self.assertEqual(result.status, "PASS", result.error)
        self.assertEqual(result.runner, "local")
        args = native.call_args.args
        self.assertEqual(args[0], self.root.resolve())
        self.assertEqual(args[2:], ("kicad-cli", ["controller"]))
        self.assertTrue(args[1].is_relative_to(self.root / "build"))

    def test_relative_cli_path_uses_callers_cwd_with_a_different_root(self) -> None:
        caller = self.root.parent / "caller"
        executable = caller / "bin" / "kicad-cli"
        executable.parent.mkdir(parents=True)
        executable.write_text("fixture", encoding="utf-8")
        relative_cli = "./bin/kicad-cli"

        def native(_root: Path, _output: Path, cli: str, projects: list[str]) -> CheckAllSummary:
            self.assertEqual(projects, ["controller"])
            self.assertEqual(cli, relative_cli)
            self.assertEqual(cli_executable(cli), str(executable.resolve()))
            return native_summary()

        original_cwd = Path.cwd()
        try:
            os.chdir(caller)
            with (
                self.runner_environment("10.0.0"),
                patch("kicad_tooling.verify.check_all", side_effect=native),
            ):
                result = verify(
                    self.root, "controller", depth="native", runner="local", cli=relative_cli
                )
        finally:
            os.chdir(original_cwd)
        self.assertEqual(result.status, "PASS", result.error)

    def test_windows_container_command_does_not_request_posix_user(self) -> None:
        with patch("kicad_tooling.verify.sys.platform", "win32"):
            command = container_command(
                self.root,
                "kicad@sha256:" + "0" * 64,
                "controller",
                self.root / "build/deps",
                self.root / "build/native",
            )
        self.assertNotIn("--user", command)

    def test_container_runner_uses_only_catalogued_image_and_captures_commands(self) -> None:
        commands: list[tuple[str, ...]] = []

        def execute(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
            commands.append(argv)
            if argv[0] == "docker":
                output = root / argv[argv.index("--output") + 1]
                output.mkdir(parents=True)
                write_model(output / "summary.json", native_summary())
            return CommandEvidence(
                argv=argv,
                started_utc=datetime.now(UTC).isoformat(),
                returncode=0,
            )

        with (
            self.runner_environment("9.0.0", docker=True),
            patch("kicad_tooling.verify.run_command", side_effect=execute),
        ):
            result = verify(self.root, "controller", depth="native", runner="container")
        self.assertEqual(result.status, "PASS", result.error)
        self.assertEqual(result.runner, "container")
        self.assertEqual(len(commands), 2)
        self.assertIn("@sha256:", " ".join(commands[0]))
        self.assertIn("@sha256:", " ".join(commands[1]))
        self.assertEqual(commands[1][commands[1].index("--project") + 1], "controller")
        self.assertTrue((Path(result.run_directory) / "dependency-command.json").is_file())
        self.assertTrue((Path(result.run_directory) / "native-command.json").is_file())

    def test_dependency_failure_stops_native_and_retains_setup_stderr(self) -> None:
        failed = CommandEvidence(
            argv=("python", "-m", "kicad_tooling.native_deps"),
            started_utc=datetime.now(UTC).isoformat(),
            returncode=1,
            stderr="docker: image manifest unavailable",
        )
        with (
            self.runner_environment("9.0.0", docker=True),
            patch("kicad_tooling.verify.run_command", return_value=failed) as command,
        ):
            result = verify(self.root, "controller", depth="native", runner="container")
        self.assertEqual(result.status, "FAIL")
        self.assertIsNone(result.native)
        self.assertEqual(command.call_count, 1)
        self.assertIn(
            "image manifest unavailable",
            (Path(result.run_directory) / "dependency-command.json").read_text(),
        )
        self.assertIn("dependency-command.json", result.next_actions[0])

    def test_container_success_without_summary_is_a_runner_failure(self) -> None:
        success = CommandEvidence(
            argv=("docker", "run"),
            started_utc=datetime.now(UTC).isoformat(),
            returncode=0,
        )
        with (
            self.runner_environment("9.0.0", docker=True),
            patch("kicad_tooling.verify.run_command", return_value=success),
        ):
            result = verify(self.root, "controller", depth="native", runner="container")
        self.assertEqual(result.status, "FAIL")
        self.assertIn("without native/summary.json", result.next_actions[0])

    def test_timeout_preserves_partial_runner_output(self) -> None:
        expired = subprocess.TimeoutExpired(
            ("docker", "run"),
            30,
            output=b"starting image",
            stderr=b"probe hung",
        )
        with patch("kicad_tooling.verify.subprocess.run", side_effect=expired):
            result = run_command(self.root, ("docker", "run"), 30)
        self.assertEqual(result.returncode, 124)
        self.assertEqual(result.stdout, "starting image")
        self.assertEqual(result.stderr, "probe hung")

    def test_native_failure_keeps_report_and_specific_repair_findings(self) -> None:
        def failing_native(
            root: Path, output: Path, cli: str, projects: list[str]
        ) -> CheckAllSummary:
            project_output = output / "controller"
            project_output.mkdir(parents=True)
            write_model(
                project_output / "summary.json",
                ValidationSummary(
                    timestamp_utc=datetime.now(UTC).isoformat(),
                    checked_commit="LOCAL_UNBOUND",
                    project_id="controller",
                    checks={
                        "erc": CheckEvidence(
                            status="FAIL",
                            error="2 rule violations",
                        )
                    },
                    status="FAIL",
                    artifacts_sha256={},
                ),
            )
            write_model(output / "summary.json", native_summary("FAIL"))
            return native_summary("FAIL")

        with (
            self.runner_environment("10.0.0"),
            patch("kicad_tooling.verify.check_all", side_effect=failing_native),
        ):
            result = verify(self.root, "controller", depth="native", runner="local")
        self.assertEqual(result.status, "FAIL", result.error)
        self.assertIsNotNone(result.diagnosis)
        assert result.diagnosis is not None
        self.assertIn("NATIVE_ERC", {item.code for item in result.diagnosis.findings})
        self.assertTrue((Path(result.run_directory) / "diagnosis.json").is_file())

    def test_unavailable_runner_is_an_actionable_failure_before_native_work(self) -> None:
        with (
            self.runner_environment("10.0.6"),
            patch("kicad_tooling.verify.check_all") as native,
        ):
            result = verify(self.root, "controller", depth="native", runner="auto")
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.runner, "none")
        self.assertEqual(result.portable.status if result.portable is not None else None, "PASS")
        self.assertIn("Start Docker", result.next_actions[0])
        self.assertIn("--project controller", result.next_actions[0])
        native.assert_not_called()

    def test_custom_output_cannot_escape_ignored_build(self) -> None:
        with self.assertRaisesRegex(ValueError, "ignored build"):
            verify(self.root, "controller", output=Path("projects/controller/review"))


if __name__ == "__main__":
    unittest.main()
