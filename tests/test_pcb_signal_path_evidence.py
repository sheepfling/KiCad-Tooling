"""Source-binding tests for synthetic mapped PCB signal-path coverage."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import pcb_drc_source_evidence as drc_evidence
from kicad_tooling.hwrepo import pcb_drc_source_scan
from kicad_tooling.hwrepo.contracts import read_model, write_model
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
from kicad_tooling.hwrepo.pcb_geometry_receipts import write_pcb_geometry_snapshot
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
        project_kind=config.kind,
        checks={
            "drc": CheckEvidence(status="PASS", returncode=0),
            "source_scope": CheckEvidence(status="PASS", source_hashes=source_hashes),
            "source_unchanged": CheckEvidence(status="PASS", source_hashes=source_hashes),
            "toolchain": CheckEvidence(
                status="PASS", observed_version=config.kicad_version, image=config.image
            ),
        },
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
    write_pcb_geometry_snapshot(snapshot_path, snapshot)
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


@pytest.mark.parametrize(
    "failure",
    ["project", "kind", "version", "image", "source_scope", "source_unchanged", "missing"],
)
def test_drc_evidence_rejects_unbound_native_summary(tmp_path: Path, failure: str) -> None:
    config, source_hashes, native, *_ = source_bound_fixture(tmp_path)
    summary_path = native / "summary.json"
    summary = read_model(summary_path, ValidationSummary)
    checks = dict(summary.checks)
    if failure == "project":
        summary = summary.model_copy(update={"project_id": "other-project"})
    elif failure == "kind":
        summary = summary.model_copy(update={"project_kind": ProjectKind.SCHEMATIC})
    elif failure in {"version", "image"}:
        field = "observed_version" if failure == "version" else "image"
        checks["toolchain"] = checks["toolchain"].model_copy(update={field: "different"})
    elif failure == "missing":
        del checks["source_unchanged"]
    else:
        checks[failure] = checks[failure].model_copy(update={"source_hashes": {}})
    write_model(summary_path, summary.model_copy(update={"checks": checks}))

    with pytest.raises(ValueError, match="Native (summary|source_)"):
        drc_evidence.source_bound_drc_evidence(tmp_path, config, source_hashes, native)


def test_failed_native_drc_can_still_supply_bound_evidence(tmp_path: Path) -> None:
    config, source_hashes, native, *_ = source_bound_fixture(tmp_path)
    summary_path = native / "summary.json"
    summary = read_model(summary_path, ValidationSummary)
    command_path = native / "drc.command.json"
    command = read_model(command_path, CommandEvidence).model_copy(update={"returncode": 5})
    write_model(command_path, command)
    checks = dict(summary.checks)
    checks["drc"] = CheckEvidence(status="FAIL", returncode=5)
    summary = summary.model_copy(
        update={
            "status": "FAIL",
            "checks": checks,
            "artifacts_sha256": {
                **summary.artifacts_sha256,
                "drc.command.json": digest(command_path),
            },
        }
    )
    write_model(summary_path, summary)

    evidence = drc_evidence.source_bound_drc_evidence(tmp_path, config, source_hashes, native)
    assert evidence.native_drc_sha256 == summary.artifacts_sha256["drc.json"]


@pytest.mark.parametrize("name", ["summary.json", "drc.json", "drc.command.json"])
@pytest.mark.parametrize("remove", [False, True])
def test_drc_evidence_rechecks_receipts_after_evaluation(
    tmp_path: Path, name: str, remove: bool
) -> None:
    config, source_hashes, native, *_ = source_bound_fixture(tmp_path)
    evidence = drc_evidence.source_bound_drc_evidence(tmp_path, config, source_hashes, native)
    target = native / name
    if remove:
        target.unlink()
    else:
        target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="changed while checking DRC"):
        drc_evidence.verify_source_bound_drc_unchanged(tmp_path, config, source_hashes, evidence)


@pytest.mark.parametrize("name", ["summary.json", "drc.json", "drc.command.json"])
def test_drc_evidence_rejects_receipt_changed_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    config, source_hashes, native, *_ = source_bound_fixture(tmp_path)
    target = native / name
    original_read_text = Path.read_text

    def changing_read(path: Path, encoding: str | None = None, errors: str | None = None) -> str:
        contents = original_read_text(path, encoding=encoding, errors=errors)
        if path == target:
            path.write_bytes(path.read_bytes() + b" ")
        return contents

    monkeypatch.setattr(Path, "read_text", changing_read)
    with pytest.raises(ValueError, match="changed while checking DRC"):
        drc_evidence.source_bound_drc_evidence(tmp_path, config, source_hashes, native)


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
        write_pcb_geometry_snapshot(snapshot_path, snapshot)
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

    assert report.status == "INCOMPLETE"
    clock = next(entry for entry in report.entries if entry.id == "clock")
    assert clock.constraints[0].status == "UNSUPPORTED"
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
    with pytest.raises(ValueError, match="snapshot differs"):
        scan_fixture(tmp_path, snapshot_hash="e" * 64)


@pytest.mark.parametrize("record", ["snapshot", "command"])
def test_signal_path_rejects_typed_record_not_matching_retained_receipt(
    tmp_path: Path, record: str
) -> None:
    (
        config,
        source_hashes,
        native,
        snapshot,
        snapshot_path,
        snapshot_hash,
        command,
        command_path,
        command_hash,
    ) = source_bound_fixture(tmp_path)
    if record == "snapshot":
        snapshot = snapshot.model_copy(update={"zones_refilled": False})
    else:
        command = command.model_copy(update={"started_utc": "different"})
    with pytest.raises(ValueError, match=f"{record} differs"):
        scan_source_bound_signal_path_map(
            tmp_path,
            config,
            path_map(),
            source_netlist(),
            source_hashes,
            native,
            snapshot,
            snapshot_path,
            snapshot_hash,
            command,
            command_path,
            command_hash,
            "review",
        )


@pytest.mark.parametrize("name", ["pcb-connectivity.json", "pcb.command.json"])
def test_signal_path_rechecks_geometry_receipts_after_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    fixture = source_bound_fixture(tmp_path)
    original = pcb_drc_source_scan.verify_source_bound_drc_unchanged

    def mutate_after_evaluation(
        root: Path,
        config: ProjectConfig,
        source_hashes: Mapping[str, str],
        evidence: drc_evidence.BoundDrcEvidence,
    ) -> None:
        original(root, config, source_hashes, evidence)
        target = fixture[2] / name
        target.write_bytes(target.read_bytes() + b" ")

    monkeypatch.setattr(
        pcb_drc_source_scan, "verify_source_bound_drc_unchanged", mutate_after_evaluation
    )
    with pytest.raises(ValueError, match="differs from source-bound evidence"):
        scan_fixture(tmp_path, fixture=fixture)
