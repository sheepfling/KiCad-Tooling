"""Observed netlists help review an independent contract without authoring it."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contract_coach import (
    AutoNetlistRunner,
    ContainerNetlistRunner,
    capture,
    docker_prefix,
    inspect_summary,
    receipt_directory,
    save_receipt,
    text_report,
)
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    CommandEvidence,
    ProjectKind,
    ProjectManifest,
    ProjectTestContract,
    SchematicValidationContract,
    ValidationSummary,
)
from kicad_tooling.hwrepo.scaffold import new_project
from kicad_tooling.validate import hashes
from tests.support import reference_root

NETLIST = """<export>
  <components>
    <comp ref="R1"><value>1k</value><footprint>Pilot:R_Test</footprint></comp>
    <comp ref="R3"><value>3k</value><footprint>Pilot:R_Test</footprint></comp>
  </components>
  <nets>
    <net name="PILOT_A"><node ref="R1" pin="1"/><node ref="R3" pin="1"/></net>
    <net name="PILOT_C"><node ref="R1" pin="2"/><node ref="R3" pin="2"/></net>
  </nets>
</export>
"""


def command(stdout: str = "", returncode: int = 0) -> CommandEvidence:
    return CommandEvidence(
        argv=("synthetic-kicad-cli",), started_utc="2026-09-24T00:00:00+00:00",
        returncode=returncode, stdout=stdout,
    )


def fake_executable(path: Path, source: str) -> Path:
    """Make a runnable fake CLI on POSIX and Windows hosts."""
    if sys.platform == "win32":
        script = path.with_suffix(".py")
        script.write_text(source, encoding="utf-8")
        launcher = path.with_suffix(".cmd")
        launcher.write_text(
            f'@echo off\n"{sys.executable}" "%~dp0{script.name}" %*\n',
            encoding="utf-8",
        )
        return launcher
    path.write_text(f"#!{sys.executable}\n{source}", encoding="utf-8")
    path.chmod(0o755)
    return path


class FakeRunner:
    def __init__(self, version: str = "10.0.5") -> None:
        self.observed_version = version
        self.exported = False

    def version(self, root: Path, config: object) -> CommandEvidence:
        _ = root, config
        return command(self.observed_version + "\n")

    def export(self, root: Path, config: object, output: Path) -> CommandEvidence:
        _ = root, config
        self.exported = True
        output.write_text(NETLIST, encoding="utf-8")
        return command()


class ContractCoachTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="contract-coach-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "source"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        self.project_id = "controller"
        self.config = load_config(self.root, f"examples/projects/{self.project_id}/project.json")
        self.native = self.root / "build/native/controller"
        self.native.mkdir(parents=True)
        (self.native / "netlist.xml").write_text(NETLIST, encoding="utf-8")
        write_model(self.native / "netlist.command.json", command())
        current = hashes(self.root, self.config.source_roots)
        self.summary = ValidationSummary(
            timestamp_utc="2026-09-24T00:00:00+00:00", checked_commit="LOCAL_UNBOUND",
            project_id=self.project_id, project_kind=ProjectKind.PCB,
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes=current),
                "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
                "toolchain": CheckEvidence(
                    status="PASS", observed_version=self.config.kicad_version,
                    image=self.config.image,
                ),
                "netlist": CheckEvidence(status="FAIL", returncode=0,
                                         error="Independent contract differs"),
            },
            status="FAIL",
            artifacts_sha256={
                "netlist.xml": digest(self.native / "netlist.xml"),
                "netlist.command.json": digest(self.native / "netlist.command.json"),
            },
        )
        write_model(self.native / "summary.json", self.summary)

    def test_failed_contract_check_still_yields_bound_unreviewed_inventory(self) -> None:
        contract = self.root / "examples/projects/controller/tests/contract.json"
        before = contract.read_bytes()
        report = inspect_summary(self.root, self.project_id, self.native / "summary.json")
        self.assertEqual(report.status, "READY_FOR_REVIEW", report.issues)
        self.assertEqual(report.review_state, "UNREVIEWED")
        self.assertFalse(report.electrical_coverage)
        self.assertEqual(report.native_summary, str(self.native / "summary.json"))
        self.assertEqual(report.native_status, "FAIL")
        self.assertEqual({component.identifier for component in report.differences
                          if component.kind == "component"}, {"R2", "R3"})
        self.assertIn("UNREVIEWED component R3", text_report(report, "full"))
        self.assertEqual(contract.read_bytes(), before)

    def test_tampered_wrong_project_and_stale_source_are_blocked(self) -> None:
        netlist = self.native / "netlist.xml"
        netlist.write_text(NETLIST + "\n", encoding="utf-8")
        report = inspect_summary(self.root, self.project_id, self.native)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("artifact hash", report.issues[0])
        self.assertIsNone(report.observed)
        netlist.write_text(NETLIST, encoding="utf-8")

        write_model(self.native / "summary.json", self.summary.model_copy(
            update={"project_id": "passive-signal-reference"},
        ))
        self.assertIn("another project", inspect_summary(
            self.root, self.project_id, self.native,
        ).issues[0])
        write_model(self.native / "summary.json", self.summary)

        source = self.root / "examples/projects/controller/kicad/controller.kicad_sch"
        source.write_bytes(source.read_bytes() + b"\n")
        self.assertIn("source", inspect_summary(
            self.root, self.project_id, self.native,
        ).issues[0])

    def test_native_summary_is_blocked_after_catalogued_toolchain_changes(self) -> None:
        catalog = self.root / "catalog/toolchains.json"
        original = json.loads(catalog.read_text(encoding="utf-8"))
        for field, replacement in (
            ("kicad_version", "10.0.1"),
            ("image", "ghcr.io/kicad/kicad@sha256:" + "a" * 64),
        ):
            with self.subTest(field=field):
                altered = json.loads(json.dumps(original))
                for record in altered["toolchains"]:
                    if record["id"] == self.config.toolchain_id:
                        record[field] = replacement
                catalog.write_text(json.dumps(altered), encoding="utf-8")
                report = inspect_summary(self.root, self.project_id, self.native)
                self.assertEqual(report.status, "BLOCKED")
                self.assertIn("toolchain version or image", report.issues[0])
                self.assertIsNone(report.observed)
        catalog.write_text(json.dumps(original), encoding="utf-8")

    def test_native_summary_requires_a_passing_toolchain_record(self) -> None:
        for evidence in (None, CheckEvidence(
            status="FAIL", observed_version=self.config.kicad_version,
            image=self.config.image,
        )):
            with self.subTest(evidence=evidence):
                checks = dict(self.summary.checks)
                if evidence is None:
                    del checks["toolchain"]
                else:
                    checks["toolchain"] = evidence
                write_model(self.native / "summary.json", self.summary.model_copy(
                    update={"checks": checks},
                ))
                report = inspect_summary(self.root, self.project_id, self.native)
                self.assertEqual(report.status, "BLOCKED")
                self.assertIn("toolchain version or image", report.issues[0])

    def test_command_evidence_must_be_hashed_and_successful(self) -> None:
        command_path = self.native / "netlist.command.json"
        command_path.write_text("{}", encoding="utf-8")
        report = inspect_summary(self.root, self.project_id, self.native)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("command evidence", report.issues[0])

    def test_capture_exports_before_an_empty_contract_is_authored(self) -> None:
        project_id = "passive-signal-reference"
        config = load_config(self.root, f"examples/projects/{project_id}/project.json")
        manifest_path = self.root / f"examples/projects/{project_id}/project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        contract_path = manifest_path.parent / manifest.checks
        contract = read_model(contract_path, ProjectTestContract)
        assert isinstance(contract.validation, SchematicValidationContract)
        self.assertEqual(contract.validation.components, {})
        original = contract_path.read_bytes()
        runner = FakeRunner(config.kicad_version)
        output = receipt_directory(self.root, project_id, None)
        report = capture(self.root, project_id, output, runner)
        save_receipt(output, report)
        self.assertEqual(report.status, "READY_FOR_REVIEW", report.issues)
        self.assertTrue(runner.exported)
        self.assertEqual(report.review_state, "UNREVIEWED")
        self.assertTrue(report.differences)
        self.assertTrue(all(item.difference == "observed_only" for item in report.differences))
        self.assertEqual(contract_path.read_bytes(), original)
        self.assertTrue((output / "netlist.xml").is_file())
        self.assertTrue((output / "version.command.json").is_file())
        self.assertTrue((output / "report.json").is_file())
        self.assertTrue((output / "report.txt").is_file())

    def test_capture_rejects_wrong_toolchain_and_unignored_receipt(self) -> None:
        output = receipt_directory(self.root, self.project_id, None)
        runner = FakeRunner("9.0.0")
        report = capture(self.root, self.project_id, output, runner)
        self.assertEqual(report.status, "BLOCKED")
        self.assertFalse(runner.exported)
        self.assertIn("Exact KiCad", report.issues[0])
        with self.assertRaisesRegex(ValueError, "ignored build"):
            receipt_directory(self.root, self.project_id, Path("projects/controller/docs/receipt"))

    def test_capture_rejects_source_changed_during_export(self) -> None:
        source = self.root / "examples/projects/controller/kicad/controller.kicad_sch"

        class MutatingRunner(FakeRunner):
            def export(self, root: Path, config: object, output: Path) -> CommandEvidence:
                exported = super().export(root, config, output)
                source.write_bytes(source.read_bytes() + b"\n")
                return exported

        output = receipt_directory(self.root, self.project_id, None)
        report = capture(self.root, self.project_id, output, MutatingRunner(self.config.kicad_version))
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("changed during netlist capture", report.issues[0])
        self.assertIsNone(report.observed)

    def test_pcb_only_is_never_presented_as_electrical_coverage(self) -> None:
        self.assertEqual(new_project(
            self.root, "layout-only", ProjectKind.PCB_ONLY, "kicad-10.0.5",
        ).status, "PASS")
        report = inspect_summary(self.root, "layout-only", self.native)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("PCB-only", report.issues[0])
        self.assertFalse(report.electrical_coverage)

    def test_cli_json_and_short_text_keep_observations_explicit(self) -> None:
        base = (
            sys.executable, "-I", "-B", "-m", "kicad_tooling.contract_coach", "--root", str(self.root),
            "--project-id", self.project_id, "--native-summary", str(self.native),
        )
        machine = subprocess.run(
            (*base, "--format", "json"), cwd=self.root, capture_output=True,
            text=True, check=False,
        )
        self.assertEqual(machine.returncode, 0, machine.stderr)
        structured = json.loads(machine.stdout)
        self.assertEqual(structured["review_state"], "UNREVIEWED")
        self.assertEqual(structured["observed"]["components"]["R3"]["value"], "3k")
        human = subprocess.run(
            (*base, "--format", "text"), cwd=self.root, capture_output=True,
            text=True, check=False,
        )
        self.assertEqual(human.returncode, 0, human.stderr)
        self.assertIn("Observed: 2 components, 2 nets", human.stdout)
        self.assertIn("UNREVIEWED", human.stdout)

        receipt = self.root / "build/contract-coach/inspect-001"
        retained = subprocess.run(
            (*base, "--output", str(receipt), "--format", "json"),
            cwd=self.root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(retained.returncode, 0, retained.stderr)
        self.assertTrue((receipt / "report.json").is_file())
        self.assertEqual(json.loads(retained.stdout)["receipt_dir"], str(receipt))

    def test_cli_capture_missing_executable_is_blocked_with_receipt(self) -> None:
        result = subprocess.run(
            (
                sys.executable, "-I", "-B", "-m", "kicad_tooling.contract_coach", "--root", str(self.root),
                "--project-id", self.project_id, "--capture", "--runner", "local",
                "--cli", "missing-kicad-cli-test",
                "--format", "json",
            ),
            cwd=self.root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(Path(report["receipt_dir"], "report.json").is_file())

    def test_container_runner_uses_pinned_image_and_read_only_source(self) -> None:
        output = receipt_directory(self.root, self.project_id, None) / "netlist.xml"
        calls: list[tuple[str, ...]] = []

        def fake_command(_root: Path, argv: tuple[str, ...], timeout: int = 180) -> CommandEvidence:
            self.assertEqual(timeout, 600)
            calls.append(argv)
            return command(self.config.kicad_version + "\n")

        with patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_command):
            runner = ContainerNetlistRunner()
            runner.version(self.root, self.config)
            runner.export(self.root, self.config, output)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][-2:], (self.config.image, "version"))
        self.assertIn("@sha256:", calls[0][-2])
        self.assertIn(("-v", f"{self.root}:/work:ro"), tuple(zip(calls[1], calls[1][1:])))
        self.assertIn(("-v", f"{output.parent}:/output:rw"),
                      tuple(zip(calls[1], calls[1][1:])))
        self.assertEqual(calls[1][calls[1].index("--output") + 1], "/output/netlist.xml")
        self.assertEqual(calls[1][-1], "/work/examples/projects/controller/kicad/controller.kicad_sch")

    def test_windows_container_resolves_docker_command_extension(self) -> None:
        with (
            patch("kicad_tooling.hwrepo.contract_coach.sys.platform", "win32"),
            patch("kicad_tooling.hwrepo.contract_coach.shutil.which", return_value="C:/bin/docker.cmd"),
        ):
            self.assertEqual(docker_prefix()[0], "C:/bin/docker.cmd")

    def test_auto_falls_back_to_container_and_records_both_version_probes(self) -> None:
        def fake_command(_root: Path, argv: tuple[str, ...], timeout: int = 180) -> CommandEvidence:
            if Path(argv[0]).stem == "docker":
                return command(self.config.kicad_version + "\n")
            return command("9.0.0\n")

        with patch("kicad_tooling.hwrepo.contract_coach.run_command", side_effect=fake_command):
            runner = AutoNetlistRunner("wrong-local-kicad")
            result = runner.version(self.root, self.config)
        self.assertEqual(result.stdout.strip(), self.config.kicad_version)
        self.assertEqual(runner.selected_runner, "container")
        self.assertEqual(set(runner.probes), {"local_version", "container_version"})
        self.assertEqual(runner.probes["local_version"].stdout.strip(), "9.0.0")

    def test_auto_fallback_capture_retains_both_probes_in_ignored_receipt(self) -> None:
        class FakeContainer(ContainerNetlistRunner):
            def version(self, root: Path, config: object) -> CommandEvidence:
                _ = root, config
                return command(self_version + "\n")

            def export(self, root: Path, config: object, output: Path) -> CommandEvidence:
                _ = root, config
                output.write_text(NETLIST, encoding="utf-8")
                return command()

        self_version = self.config.kicad_version
        runner = AutoNetlistRunner("missing-kicad-cli-auto-test")
        runner.container = FakeContainer()
        output = receipt_directory(self.root, self.project_id, None)
        report = capture(self.root, self.project_id, output, runner)
        self.assertEqual(report.status, "READY_FOR_REVIEW", report.issues)
        self.assertEqual(report.selected_runner, "container")
        self.assertEqual(set(report.commands),
                         {"local_version", "container_version", "version", "netlist"})
        self.assertIsNotNone(report.commands["local_version"].error)
        self.assertTrue((output / "local_version.command.json").is_file())
        self.assertTrue((output / "container_version.command.json").is_file())

    def test_container_capture_cli_keeps_unreviewed_receipt_and_contract_unchanged(self) -> None:
        executable_dir = self.root / "build/bin"
        executable_dir.mkdir(parents=True)
        fake_executable(executable_dir / "docker",
            "import pathlib, sys\n"
            "args = sys.argv[1:]\n"
            "if args[-1] == 'version':\n"
            f"    print({self.config.kicad_version!r})\n"
            "elif 'sch' in args:\n"
            "    mounts = [args[i + 1] for i, value in enumerate(args[:-1]) if value == '-v']\n"
            "    output = pathlib.Path(next(value.split(':/output:rw')[0] for value in mounts "
            "if value.endswith(':/output:rw')))\n"
            f"    (output / 'netlist.xml').write_text({NETLIST!r}, encoding='utf-8')\n"
            "else:\n"
            "    raise SystemExit(2)\n",
        )
        contract_path = self.root / "examples/projects/controller/tests/contract.json"
        before = contract_path.read_bytes()
        result = subprocess.run(
            (
                sys.executable, "-I", "-B", "-m", "kicad_tooling.contract_coach", "--root", str(self.root),
                "--project-id", self.project_id, "--capture", "--runner", "container",
                "--format", "json",
            ),
            cwd=self.root, capture_output=True, text=True, check=False,
            env={**os.environ, "PATH": f"{executable_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["selected_runner"], "container")
        self.assertEqual(report["status"], "READY_FOR_REVIEW")
        self.assertEqual(report["review_state"], "UNREVIEWED")
        self.assertFalse(report["electrical_coverage"])
        self.assertIn("@sha256:", " ".join(report["commands"]["netlist"]["argv"]))
        self.assertTrue(Path(report["receipt_dir"], "netlist.xml").is_file())
        self.assertEqual(contract_path.read_bytes(), before)

    def test_container_capture_refuses_mutable_catalogued_image(self) -> None:
        catalog = self.root / "catalog/toolchains.json"
        data = json.loads(catalog.read_text(encoding="utf-8"))
        for record in data["toolchains"]:
            if record["id"] == self.config.toolchain_id:
                record["image"] = "ghcr.io/kicad/kicad:mutable"
        catalog.write_text(json.dumps(data), encoding="utf-8")
        output = receipt_directory(self.root, self.project_id, None)
        with patch("kicad_tooling.hwrepo.contract_coach.run_command") as run:
            report = capture(self.root, self.project_id, output, ContainerNetlistRunner())
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("digest-pinned", report.issues[0])
        run.assert_not_called()

    def test_cli_capture_runs_local_adapter_and_retains_command_evidence(self) -> None:
        executable = fake_executable(self.root / "build/fake-kicad-cli",
            "import pathlib, sys\n"
            "if sys.argv[1:] == ['version']:\n"
            f"    print({self.config.kicad_version!r})\n"
            "else:\n"
            "    assert sys.argv[1:5] == ['sch', 'export', 'netlist', '--format']\n"
            "    output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
            f"    output.write_text({NETLIST!r}, encoding='utf-8')\n",
        )
        contract_path = self.root / "examples/projects/controller/tests/contract.json"
        before = contract_path.read_bytes()
        result = subprocess.run(
            (
                sys.executable, "-I", "-B", "-m", "kicad_tooling.contract_coach", "--root", str(self.root),
                "--project-id", self.project_id, "--capture", "--cli", str(executable),
                "--format", "json",
            ),
            cwd=self.root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "READY_FOR_REVIEW")
        self.assertEqual(report["review_state"], "UNREVIEWED")
        self.assertEqual(report["commands"]["netlist"]["returncode"], 0)
        self.assertTrue(Path(report["receipt_dir"], "netlist.command.json").is_file())
        self.assertEqual(contract_path.read_bytes(), before)

    def test_explicit_relative_cli_is_resolved_from_callers_cwd(self) -> None:
        caller = self.root.parent / "caller"
        executable_dir = caller / "bin"
        executable_dir.mkdir(parents=True)
        executable = fake_executable(executable_dir / "fake-kicad-cli",
            "import pathlib, sys\n"
            "if sys.argv[1:] == ['version']:\n"
            f"    print({self.config.kicad_version!r})\n"
            "else:\n"
            "    output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
            f"    output.write_text({NETLIST!r}, encoding='utf-8')\n"
        )
        environment = {
            **os.environ,
        }
        result = subprocess.run(
            (
                sys.executable, "-I", "-B", "-m", "kicad_tooling.contract_coach", "--root", str(self.root),
                "--project-id", self.project_id, "--capture", "--runner", "local",
                "--cli", f"./bin/{executable.name}", "--format", "json",
            ),
            cwd=caller, capture_output=True, text=True, check=False, env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "READY_FOR_REVIEW")
        self.assertEqual(report["commands"]["version"]["argv"][0], str(executable.resolve()))
        self.assertEqual(report["commands"]["netlist"]["argv"][0], str(executable.resolve()))
