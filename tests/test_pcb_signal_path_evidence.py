"""Source-binding tests for synthetic mapped PCB signal-path coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    CommandEvidence,
    ComponentIdentity,
    IgnoredChecks,
    PcbConnectivitySnapshot,
    PcbSignalPathRuleCoverageReport,
    PcbValidationContract,
    ProjectConfig,
    ProjectKind,
    ValidationSummary,
)
from kicad_tooling.hwrepo.pcb_drc_source_scan import scan_source_bound_signal_path_map
from kicad_tooling.validate import hashes
from tests.design_lint_fixtures.pcb_signal_path import (
    native_rules,
    path_map,
    pcb_snapshot,
    source_netlist,
)

SourceBoundFixture = tuple[
    ProjectConfig,
    dict[str, str],
    Path,
    PcbConnectivitySnapshot,
    Path,
    str,
    CommandEvidence,
    Path,
    str,
]


def source_bound_fixture(root: Path) -> SourceBoundFixture:
    source_root = root / "projects/signal-path"
    source_root.mkdir(parents=True)
    project = source_root / "synthetic.kicad_pro"
    board = source_root / "synthetic.kicad_pcb"
    rules = source_root / "synthetic.kicad_dru"
    project.write_text("{}\n", encoding="utf-8")
    board.write_text("(synthetic board source)\n", encoding="utf-8")
    rules.write_text(native_rules(), encoding="utf-8")
    config = ProjectConfig(
        schema_version="1",
        kind=ProjectKind.PCB,
        assurance_profile="development",
        not_for_manufacture=True,
        project_id="synthetic-signal-path",
        component_identity=ComponentIdentity(required=False, part_ids=()),
        toolchain_id="synthetic-kicad-10-0-5",
        kicad_version="10.0.5",
        image="ghcr.io/kicad/kicad:10.0.5@sha256:" + "d" * 64,
        project="projects/signal-path/synthetic.kicad_pro",
        source_roots=("projects/signal-path",),
        required_inputs=(),
        validation=PcbValidationContract(
            kind=ProjectKind.PCB,
            components={},
            nets={},
            expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
        ),
    )
    source_hashes = hashes(root, config.source_roots)

    native = root / "build/native"
    native.mkdir(parents=True)
    drc_path = native / "drc.json"
    drc_path.write_text(
        json.dumps(
            {
                "kicad_version": config.kicad_version,
                "source": board.as_posix(),
                "ignored_checks": [],
                "violations": [],
            }
        ),
        encoding="utf-8",
    )
    drc_command = CommandEvidence(
        argv=(
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--output",
            drc_path.as_posix(),
            board.as_posix(),
        ),
        started_utc="synthetic",
        returncode=0,
    )
    drc_command_path = native / "drc.command.json"
    write_model(drc_command_path, drc_command)
    summary = ValidationSummary(
        timestamp_utc="synthetic",
        checked_commit="synthetic",
        project_id=config.project_id,
        checks={"drc": CheckEvidence(status="PASS", returncode=0)},
        status="PASS",
        artifacts_sha256={
            "drc.json": digest(drc_path),
            "drc.command.json": digest(drc_command_path),
        },
    )
    write_model(native / "summary.json", summary)

    snapshot = pcb_snapshot().model_copy(
        update={
            "board_sha256": source_hashes[board.relative_to(root).as_posix()],
            "image": config.image,
        }
    )
    snapshot_path = native / "pcb-connectivity.json"
    write_model(snapshot_path, snapshot)
    pcb_command = CommandEvidence(
        argv=("python3", "native_pcb_probe.py"),
        started_utc="synthetic",
        returncode=0,
    )
    pcb_command_path = native / "pcb.command.json"
    write_model(pcb_command_path, pcb_command)
    return (
        config,
        source_hashes,
        native,
        snapshot,
        snapshot_path,
        digest(snapshot_path),
        pcb_command,
        pcb_command_path,
        digest(pcb_command_path),
    )


def scan_fixture(
    root: Path,
    *,
    fixture: SourceBoundFixture | None = None,
    snapshot: PcbConnectivitySnapshot | None = None,
    snapshot_hash: str | None = None,
) -> PcbSignalPathRuleCoverageReport:
    (
        config,
        source_hashes,
        native,
        default_snapshot,
        snapshot_path,
        default_snapshot_hash,
        pcb_command,
        pcb_command_path,
        pcb_command_hash,
    ) = source_bound_fixture(root) if fixture is None else fixture
    chosen_snapshot = snapshot or default_snapshot
    if snapshot is not None:
        write_model(snapshot_path, snapshot)
    return scan_source_bound_signal_path_map(
        root,
        config,
        path_map(),
        source_netlist(),
        source_hashes,
        native,
        chosen_snapshot,
        snapshot_path,
        snapshot_hash or (digest(snapshot_path) if snapshot is not None else default_snapshot_hash),
        pcb_command,
        pcb_command_path,
        pcb_command_hash,
        "review",
    )


def test_source_bound_signal_path_report_binds_native_inputs(tmp_path: Path) -> None:
    report = scan_fixture(tmp_path)

    assert report.status == "COMPLETE"
    assert report.mode == "review"
    assert report.board_sha256 is not None
    assert report.native_drc_sha256 is not None
    assert report.pcb_snapshot_sha256 is not None
    assert report.pcb_command_sha256 is not None
    assert [entry.id for entry in report.entries] == ["clock", "data", "serial-bundle"]


def test_source_bound_signal_path_report_keeps_disconnected_copper_incomplete(
    tmp_path: Path,
) -> None:
    fixture = source_bound_fixture(tmp_path)
    snapshot = fixture[3]
    pads = tuple(
        pad.model_copy(update={"connected_pads": (pad.pad,)})
        if pad.pad in {"J1.1", "U1.1"}
        else pad
        for pad in snapshot.pads
    )
    disconnected = snapshot.model_copy(update={"pads": pads})
    report = scan_fixture(tmp_path, fixture=fixture, snapshot=disconnected)

    clock = next(entry for entry in report.entries if entry.id == "clock")
    assert report.status == "INCOMPLETE"
    assert clock.status == "INCOMPLETE"
    assert "same native copper component" in " ".join(clock.issues)


def test_source_bound_signal_path_report_rejects_stale_snapshot_digest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="snapshot or command differs"):
        scan_fixture(tmp_path, snapshot_hash="e" * 64)
