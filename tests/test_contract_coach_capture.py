"""Capture and runner behavior for source-bound contract coaching."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from kicad_tooling.hwrepo import contract_coach
from kicad_tooling.hwrepo.contract_coach import (
    AutoNetlistRunner,
    ContainerNetlistRunner,
    capture,
    docker_prefix,
    receipt_directory,
    save_receipt,
)
from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    ProjectManifest,
    ProjectTestContract,
    SchematicValidationContract,
)
from tests.contract_coach_support import (
    NETLIST,
    FakeRunner,
    command,
    fake_executable,
)

pytestmark = pytest.mark.slow


def test_capture_exports_before_an_empty_contract_is_authored(coach_workspace) -> None:
    project_id = "passive-signal-reference"
    config = load_config(coach_workspace.root, f"examples/projects/{project_id}/project.json")
    manifest_path = coach_workspace.root / f"examples/projects/{project_id}/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    contract_path = manifest_path.parent / manifest.checks
    contract = read_model(contract_path, ProjectTestContract)
    assert isinstance(contract.validation, SchematicValidationContract)
    assert contract.validation.components == {}
    original = contract_path.read_bytes()
    runner = FakeRunner(config.kicad_version)
    output = receipt_directory(coach_workspace.root, project_id, None)
    report = capture(coach_workspace.root, project_id, output, runner)
    save_receipt(output, report)
    assert report.status == "READY_FOR_REVIEW", report.issues
    assert runner.exported
    assert report.review_state == "UNREVIEWED"
    assert report.differences
    assert all(item.difference == "observed_only" for item in report.differences)
    assert contract_path.read_bytes() == original
    assert (output / "netlist.xml").is_file()
    assert (output / "version.command.json").is_file()
    assert (output / "report.json").is_file()
    assert (output / "report.txt").is_file()


def test_capture_rejects_wrong_toolchain_before_export(coach_workspace) -> None:
    output = receipt_directory(coach_workspace.root, coach_workspace.project_id, None)
    runner = FakeRunner("9.0.0")
    report = capture(coach_workspace.root, coach_workspace.project_id, output, runner)
    assert report.status == "BLOCKED"
    assert not runner.exported
    assert "Exact KiCad" in report.issues[0]


def test_receipt_rejects_output_outside_ignored_build(coach_workspace) -> None:
    with pytest.raises(ValueError, match="ignored build"):
        receipt_directory(
            coach_workspace.root,
            coach_workspace.project_id,
            Path("projects/controller/docs/receipt"),
        )


def test_capture_rejects_source_changed_during_export(coach_workspace) -> None:
    source = coach_workspace.root / "examples/projects/controller/kicad/controller.kicad_sch"

    class MutatingRunner(FakeRunner):
        def export(self, root: Path, config: object, output: Path) -> CommandEvidence:
            exported = super().export(root, config, output)
            source.write_bytes(source.read_bytes() + b"\n")
            return exported

    output = receipt_directory(coach_workspace.root, coach_workspace.project_id, None)
    report = capture(
        coach_workspace.root,
        coach_workspace.project_id,
        output,
        MutatingRunner(coach_workspace.config.kicad_version),
    )
    assert report.status == "BLOCKED"
    assert "changed during netlist capture" in report.issues[0]
    assert report.observed is None


def test_container_runner_uses_pinned_image_and_read_only_source(
    coach_workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = (
        receipt_directory(coach_workspace.root, coach_workspace.project_id, None) / "netlist.xml"
    )
    calls: list[tuple[str, ...]] = []

    def fake_command(_root: Path, argv: tuple[str, ...], timeout: int = 180) -> CommandEvidence:
        assert timeout == 600
        calls.append(argv)
        return command(coach_workspace.config.kicad_version + "\n")

    monkeypatch.setattr(contract_coach, "run_command", fake_command)
    runner = ContainerNetlistRunner()
    runner.version(coach_workspace.root, coach_workspace.config)
    runner.export(coach_workspace.root, coach_workspace.config, output)

    assert len(calls) == 2
    assert calls[0][-2:] == (coach_workspace.config.image, "version")
    assert "@sha256:" in calls[0][-2]
    assert ("-v", f"{coach_workspace.root}:/work:ro") in tuple(zip(calls[1], calls[1][1:]))
    assert ("-v", f"{output.parent}:/output:rw") in tuple(zip(calls[1], calls[1][1:]))
    assert calls[1][calls[1].index("--output") + 1] == "/output/netlist.xml"
    assert calls[1][-1] == "/work/examples/projects/controller/kicad/controller.kicad_sch"


def test_windows_container_resolves_docker_command_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(contract_coach.sys, "platform", "win32")
    monkeypatch.setattr(contract_coach.shutil, "which", lambda _: "C:/bin/docker.cmd")
    assert docker_prefix()[0] == "C:/bin/docker.cmd"


def test_auto_runner_falls_back_and_records_both_version_probes(
    coach_workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_command(_root: Path, argv: tuple[str, ...], timeout: int = 180) -> CommandEvidence:
        if Path(argv[0]).stem == "docker":
            return command(coach_workspace.config.kicad_version + "\n")
        return command("9.0.0\n")

    monkeypatch.setattr(contract_coach, "run_command", fake_command)
    runner = AutoNetlistRunner("wrong-local-kicad")
    result = runner.version(coach_workspace.root, coach_workspace.config)

    assert result.stdout.strip() == coach_workspace.config.kicad_version
    assert runner.selected_runner == "container"
    assert set(runner.probes) == {"local_version", "container_version"}
    assert runner.probes["local_version"].stdout.strip() == "9.0.0"


def test_auto_fallback_capture_retains_both_probes_in_receipt(coach_workspace) -> None:
    class FakeContainer(ContainerNetlistRunner):
        def version(self, root: Path, config: object) -> CommandEvidence:
            _ = root, config
            return command(coach_workspace.config.kicad_version + "\n")

        def export(self, root: Path, config: object, output: Path) -> CommandEvidence:
            _ = root, config
            output.write_text(NETLIST, encoding="utf-8")
            return command()

    runner = AutoNetlistRunner("missing-kicad-cli-auto-test")
    runner.container = FakeContainer()
    output = receipt_directory(coach_workspace.root, coach_workspace.project_id, None)
    report = capture(coach_workspace.root, coach_workspace.project_id, output, runner)

    assert report.status == "READY_FOR_REVIEW", report.issues
    assert report.selected_runner == "container"
    assert set(report.commands) == {
        "local_version",
        "container_version",
        "version",
        "netlist",
    }
    assert report.commands["local_version"].error is not None
    assert (output / "local_version.command.json").is_file()
    assert (output / "container_version.command.json").is_file()


def test_container_capture_cli_keeps_unreviewed_receipt_and_contract_unchanged(
    coach_workspace,
) -> None:
    executable_dir = coach_workspace.root / "build/bin"
    executable_dir.mkdir(parents=True)
    fake_executable(
        executable_dir / "docker",
        "import pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "if args[-1] == 'version':\n"
        f"    print({coach_workspace.config.kicad_version!r})\n"
        "elif 'sch' in args:\n"
        "    mounts = [args[i + 1] for i, value in enumerate(args[:-1]) if value == '-v']\n"
        "    output = pathlib.Path(next(value.split(':/output:rw')[0] for value in mounts "
        "if value.endswith(':/output:rw')))\n"
        f"    (output / 'netlist.xml').write_text({NETLIST!r}, encoding='utf-8')\n"
        "else:\n"
        "    raise SystemExit(2)\n",
    )
    contract_path = coach_workspace.root / "examples/projects/controller/tests/contract.json"
    before = contract_path.read_bytes()
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.contract_coach",
            "--root",
            str(coach_workspace.root),
            "--project-id",
            coach_workspace.project_id,
            "--capture",
            "--runner",
            "container",
            "--format",
            "json",
        ),
        cwd=coach_workspace.root,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PATH": f"{executable_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["selected_runner"] == "container"
    assert report["status"] == "READY_FOR_REVIEW"
    assert report["review_state"] == "UNREVIEWED"
    assert not report["electrical_coverage"]
    assert "@sha256:" in " ".join(report["commands"]["netlist"]["argv"])
    assert Path(report["receipt_dir"], "netlist.xml").is_file()
    assert contract_path.read_bytes() == before


def test_container_capture_refuses_mutable_catalogued_image(
    coach_workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = coach_workspace.root / "catalog/toolchains.json"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    for record in data["toolchains"]:
        if record["id"] == coach_workspace.config.toolchain_id:
            record["image"] = "ghcr.io/kicad/kicad:mutable"
    catalog.write_text(json.dumps(data), encoding="utf-8")
    output = receipt_directory(coach_workspace.root, coach_workspace.project_id, None)
    run = Mock()
    monkeypatch.setattr(contract_coach, "run_command", run)
    report = capture(
        coach_workspace.root,
        coach_workspace.project_id,
        output,
        ContainerNetlistRunner(),
    )
    assert report.status == "BLOCKED"
    assert "digest-pinned" in report.issues[0]
    run.assert_not_called()


def test_cli_capture_missing_executable_is_blocked_with_receipt(coach_workspace) -> None:
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.contract_coach",
            "--root",
            str(coach_workspace.root),
            "--project-id",
            coach_workspace.project_id,
            "--capture",
            "--runner",
            "local",
            "--cli",
            "missing-kicad-cli-test",
            "--format",
            "json",
        ),
        cwd=coach_workspace.root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "BLOCKED"
    assert Path(report["receipt_dir"], "report.json").is_file()


def test_cli_capture_runs_local_adapter_and_retains_command_evidence(coach_workspace) -> None:
    executable = fake_executable(
        coach_workspace.root / "build/fake-kicad-cli",
        "import pathlib, sys\n"
        "if sys.argv[1:] == ['version']:\n"
        f"    print({coach_workspace.config.kicad_version!r})\n"
        "else:\n"
        "    assert sys.argv[1:5] == ['sch', 'export', 'netlist', '--format']\n"
        "    output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        f"    output.write_text({NETLIST!r}, encoding='utf-8')\n",
    )
    contract_path = coach_workspace.root / "examples/projects/controller/tests/contract.json"
    before = contract_path.read_bytes()
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.contract_coach",
            "--root",
            str(coach_workspace.root),
            "--project-id",
            coach_workspace.project_id,
            "--capture",
            "--cli",
            str(executable),
            "--format",
            "json",
        ),
        cwd=coach_workspace.root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "READY_FOR_REVIEW"
    assert report["review_state"] == "UNREVIEWED"
    assert report["commands"]["netlist"]["returncode"] == 0
    assert Path(report["receipt_dir"], "netlist.command.json").is_file()
    assert contract_path.read_bytes() == before


def test_explicit_relative_cli_resolves_from_callers_working_directory(coach_workspace) -> None:
    caller = coach_workspace.root.parent / "caller"
    executable_dir = caller / "bin"
    executable_dir.mkdir(parents=True)
    executable = fake_executable(
        executable_dir / "fake-kicad-cli",
        "import pathlib, sys\n"
        "if sys.argv[1:] == ['version']:\n"
        f"    print({coach_workspace.config.kicad_version!r})\n"
        "else:\n"
        "    output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        f"    output.write_text({NETLIST!r}, encoding='utf-8')\n",
    )
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.contract_coach",
            "--root",
            str(coach_workspace.root),
            "--project-id",
            coach_workspace.project_id,
            "--capture",
            "--runner",
            "local",
            "--cli",
            f"./bin/{executable.name}",
            "--format",
            "json",
        ),
        cwd=caller,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    assert report["status"] == "READY_FOR_REVIEW"
    assert report["commands"]["version"]["argv"][0] == str(executable.resolve())
    assert report["commands"]["netlist"]["argv"][0] == str(executable.resolve())
