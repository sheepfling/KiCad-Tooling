"""Shared synthetic workspaces and process fixtures for contract-coach tests."""

from __future__ import annotations

import shutil
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    CommandEvidence,
    ProjectConfig,
    ProjectKind,
    ValidationSummary,
)
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
        argv=("synthetic-kicad-cli",),
        started_utc="2026-09-24T00:00:00+00:00",
        returncode=returncode,
        stdout=stdout,
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


@dataclass
class ContractCoachWorkspace:
    """Disposable copy of the public template with synthetic native evidence."""

    temporary: tempfile.TemporaryDirectory[str]
    root: Path
    project_id: str
    config: ProjectConfig
    native: Path
    summary: ValidationSummary

    def cleanup(self) -> None:
        self.temporary.cleanup()


def create_contract_coach_workspace() -> ContractCoachWorkspace:
    """Build an isolated public-template project and source-bound fake summary."""
    temporary = tempfile.TemporaryDirectory(prefix="contract-coach-")
    root = Path(temporary.name).resolve() / "source"
    shutil.copytree(reference_root(), root, ignore=shutil.ignore_patterns(".git"))
    project_id = "controller"
    config = load_config(root, f"examples/projects/{project_id}/project.json")
    native = root / "build/native/controller"
    native.mkdir(parents=True)
    (native / "netlist.xml").write_text(NETLIST, encoding="utf-8")
    write_model(native / "netlist.command.json", command())
    current = hashes(root, config.source_roots)
    summary = ValidationSummary(
        timestamp_utc="2026-09-24T00:00:00+00:00",
        checked_commit="LOCAL_UNBOUND",
        project_id=project_id,
        project_kind=ProjectKind.PCB,
        checks={
            "source_scope": CheckEvidence(status="PASS", source_hashes=current),
            "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
            "toolchain": CheckEvidence(
                status="PASS",
                observed_version=config.kicad_version,
                image=config.image,
            ),
            "netlist": CheckEvidence(
                status="FAIL", returncode=0, error="Independent contract differs"
            ),
        },
        status="FAIL",
        artifacts_sha256={
            "netlist.xml": digest(native / "netlist.xml"),
            "netlist.command.json": digest(native / "netlist.command.json"),
        },
    )
    write_model(native / "summary.json", summary)
    return ContractCoachWorkspace(temporary, root, project_id, config, native, summary)


@pytest.fixture
def coach_workspace() -> Iterator[ContractCoachWorkspace]:
    """Provide one isolated contract-coach workspace per pytest case."""
    workspace = create_contract_coach_workspace()
    try:
        yield workspace
    finally:
        workspace.cleanup()


class FakeRunner:
    """Deterministic netlist runner that writes the shared synthetic netlist."""

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
