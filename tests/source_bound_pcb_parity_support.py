"""Shared synthetic native-capture adapters for PCB CLI/MCP route tests."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

import pytest

from kicad_tooling import design_lint as design_lint_cli
from kicad_tooling.hwrepo import design_lint_pcb_geometry_capture, design_lint_pcb_geometry_scan
from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.native_project_validation_models import ValidationSummary
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_return_path_capture import (
    NativePcbConnectivityCapture,
    expected_probe_sha256,
)
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import PcbTouchPadClearanceRequestSet
from kicad_tooling.hwrepo.project_models import ProjectConfig
from kicad_tooling.hwrepo.project_source_hashes import hash_project_sources

PROJECT_SETTINGS = (
    '{"board":{"design_settings":{"rule_severities":{}}},"schematic":{"variants":[]}}\n'
)
SNAPSHOT_OUTPUT_ID = UUID(int=1)


def replace_authoritative_board_source(
    root: Path,
    summary_path: Path,
    source_text: str,
) -> str:
    """Change synthetic board bytes and refresh the summary's declared source identity."""
    board_relative = "projects/controller/kicad/controller.kicad_pcb"
    board_path = root / board_relative
    board_path.write_text(source_text, encoding="utf-8")
    source_hashes = hash_project_sources(root, ("projects/controller/kicad",))
    summary = read_model(summary_path, ValidationSummary)
    checks = dict(summary.checks)
    for name in ("source_scope", "source_unchanged"):
        checks[name] = checks[name].model_copy(update={"source_hashes": source_hashes})
    write_model(summary_path, summary.model_copy(update={"checks": checks}))
    return digest(board_path)


def install_synthetic_native_pcb_capture(
    monkeypatch: pytest.MonkeyPatch,
    snapshots_by_board_sha256: Mapping[str, PcbConnectivitySnapshot],
) -> None:
    """Replace only the native process boundary; retain source and receipt checks."""

    def capture_synthetic_native_snapshot(
        root: Path,
        config: ProjectConfig,
        output: Path,
        *,
        touch_pad_clearance_requests: PcbTouchPadClearanceRequestSet | None = None,
    ) -> NativePcbConnectivityCapture:
        assert touch_pad_clearance_requests is None
        board_relative = Path(config.project).with_suffix(".kicad_pcb").as_posix()
        board_sha256 = digest(root / board_relative)
        observed = snapshots_by_board_sha256[board_sha256].model_copy(
            update={
                "board_sha256": board_sha256,
                "kicad_version": config.kicad_version,
                "image": config.image,
                "probe_sha256": expected_probe_sha256(),
            }
        )
        output.mkdir(parents=True, exist_ok=True)
        command = CommandEvidence(
            argv=(
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=64m",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "-e",
                "HOME=/tmp",
                "-v",
                f"{root}:/work:ro",
                "-v",
                f"{output}:/output:rw",
                "-w",
                "/work",
                "--entrypoint",
                "/usr/bin/python3",
                config.image,
                "-I",
                "-B",
                "/output/native_pcb_probe.py",
                f"/work/{board_relative}",
                "/output/snapshot.json",
            ),
            started_utc="synthetic fixture",
            returncode=0,
        )
        write_model(output / "native.command.json", command)
        return NativePcbConnectivityCapture(command=command, snapshot=observed)

    monkeypatch.setattr(
        design_lint_pcb_geometry_capture,
        "capture_native_pcb_connectivity_result",
        capture_synthetic_native_snapshot,
    )
    monkeypatch.setattr(design_lint_pcb_geometry_scan, "uuid4", lambda: SNAPSHOT_OUTPUT_ID)


def run_design_lint_cli_in_process(
    root: Path,
    summary_path: Path,
    *,
    baseline_report: Path | None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    """Run the real CLI adapter in-process so synthetic capture patches remain active."""
    arguments = [
        "kicad-team-design-lint",
        "--root",
        str(root),
        "--project",
        "controller",
        "--native-summary",
        summary_path.relative_to(root).as_posix(),
    ]
    if baseline_report is not None:
        arguments.extend(("--baseline-report", baseline_report.name))
    monkeypatch.setattr(sys, "argv", [*arguments, "--format", "json"])
    returncode = design_lint_cli.main()
    return returncode, capsys.readouterr().out
