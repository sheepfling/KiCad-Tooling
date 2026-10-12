"""Synthetic native-capture and replay checks for PCB return evidence."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest, source_state
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    PcbConnectivitySnapshot,
    PcbPadConnectivityObservation,
    PcbReturnDomainRequirement,
    PcbReturnEndpointRequirement,
    PcbReturnPathsAnalysis,
    PcbZoneIdentity,
    PcbZoneIslandIdentity,
    PcbZoneObservation,
)
from kicad_tooling.hwrepo.pcb_return_path_capture import (
    capture_native_pcb_connectivity,
    native_pcb_command_matches,
    native_probe_source,
)
from kicad_tooling.validate import repo_path
from tests.electrical_evidence_support import (
    ElectricalEvidenceWorkspace,
)
from tests.electrical_evidence_support import (
    electrical_evidence_workspace as _electrical_evidence_workspace_fixture,  # noqa: F401
)
from tests.electrical_simulation_support import ISLAND, NA, PROJECT

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.return_path_lint,
    pytest.mark.evidence_lint,
    pytest.mark.template_checkout,
]


def test_native_pcb_return_receipt_replays_exact_pad_zone_and_probe_evidence(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    workspace = electrical_evidence_workspace
    config = selected_config(workspace.root, PROJECT)
    board_path = repo_path(workspace.root, config.project).with_suffix(".kicad_pcb")
    board_fixture = (
        Path(__file__).resolve().parents[1]
        / "kicad_tooling/hwrepo/fixtures/pcb-return-zone-connected.kicad_pcb"
    )
    board_path.write_bytes(board_fixture.read_bytes())
    requirement = PcbReturnPathsAnalysis(
        basis="Synthetic independently reviewed connector-return domain",
        domains=(
            PcbReturnDomainRequirement(
                id="serial-returns",
                basis="Synthetic DB9 pinout",
                topology="direct",
                endpoints=(
                    PcbReturnEndpointRequirement(
                        pad="J1.1", net="RETURN", footprint="Synthetic:TestPad"
                    ),
                    PcbReturnEndpointRequirement(
                        pad="J2.1", net="RETURN", footprint="Synthetic:TestPad"
                    ),
                ),
            ),
        ),
    )
    contract_path = workspace.root / ISLAND / "tests/electrical.json"
    contract = workspace.contract.model_copy(
        update={
            "pcb_return_paths": requirement,
            "grounding": NA,
            "power": NA,
            "high_frequency": NA,
            "test_access": NA,
        }
    )
    write_model(contract_path, contract)
    subprocess.run(
        (
            "git",
            "-C",
            str(workspace.root),
            "add",
            board_path.relative_to(workspace.root).as_posix(),
            contract_path.relative_to(workspace.root).as_posix(),
        ),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(workspace.root),
            "-c",
            "user.name=Synthetic fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Synthetic PCB return-path requirements",
        ),
        check=True,
        capture_output=True,
    )
    workspace.source = source_state(workspace.root)
    workspace.output = workspace.root / "build/electrical/pcb-return-paths"

    def capture(_root, selected, output):
        output.mkdir(parents=True)
        probe_copy = output / "native_pcb_probe.py"
        probe_copy.write_bytes(native_probe_source().encode("utf-8"))
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
                "-v",
                f"{_root}:/work:ro",
                "-v",
                f"{output}:/output:rw",
                "-w",
                "/work",
                "--entrypoint",
                "/usr/bin/python3",
                selected.image,
                "-I",
                "-B",
                "/output/native_pcb_probe.py",
                "/work/" + Path(selected.project).with_suffix(".kicad_pcb").as_posix(),
                "/output/snapshot.json",
            ),
            started_utc=datetime.now(UTC).isoformat(),
            returncode=0,
        )
        write_model(output / "native.command.json", command)
        zone = PcbZoneIdentity(
            uuid="00000000-0000-0000-0000-000000000001",
            layer="F.Cu",
        )
        island = PcbZoneIslandIdentity(
            uuid=zone.uuid,
            layer=zone.layer,
            island_index=0,
        )
        return command, PcbConnectivitySnapshot(
            board_sha256=digest(board_path),
            kicad_version=selected.kicad_version,
            image=selected.image,
            probe_sha256=digest(probe_copy),
            zones_refilled=True,
            pads=(
                PcbPadConnectivityObservation(
                    pad="J1.1",
                    net="RETURN",
                    footprint="Synthetic:TestPad",
                    dnp=False,
                    connected_pads=("J1.1", "J2.1"),
                    connected_zones=(zone,),
                    connected_islands=(island,),
                    connected_vias=(),
                ),
                PcbPadConnectivityObservation(
                    pad="J2.1",
                    net="RETURN",
                    footprint="Synthetic:TestPad",
                    dnp=False,
                    connected_pads=("J1.1", "J2.1"),
                    connected_zones=(zone,),
                    connected_islands=(island,),
                    connected_vias=(),
                ),
            ),
            net_ties=(),
            zones=(
                PcbZoneObservation(
                    uuid=zone.uuid,
                    layer=zone.layer,
                    name="",
                    net="RETURN",
                    filled_island_count=1,
                    unanchored_pad_island_indexes=(),
                ),
            ),
            vias=(),
        )

    with patch(
        "kicad_tooling.hwrepo.electrical_runner.capture_native_pcb_connectivity",
        side_effect=capture,
    ):
        report = analyze(workspace.root, PROJECT, workspace.output, ngspice="missing-simulator")
    assert report.status == "PASS", report.checks
    assert (
        next(
            row.status
            for row in report.checks
            if row.id == "pcb-return-paths/serial-returns/connectivity"
        )
        == "PASS"
    )
    workspace.path = workspace.output / "electrical.json"
    workspace.verify()

    snapshot_path = workspace.output / "pcb-connectivity/snapshot.json"
    saved_snapshot = snapshot_path.read_bytes()
    saved_report = workspace.path.read_bytes()
    for mutate_snapshot in (
        lambda snapshot: (
            snapshot["pads"][0].update(connected_pads=["J1.1"]),
            snapshot["pads"][1].update(connected_pads=["J2.1"]),
        ),
        lambda snapshot: (
            snapshot["zones"][0].update(filled_island_count=2),
            snapshot["zones"][0].update(unanchored_pad_island_indexes=[1]),
        ),
    ):
        tampered_snapshot = json.loads(saved_snapshot)
        mutate_snapshot(tampered_snapshot)
        snapshot_path.write_text(json.dumps(tampered_snapshot), encoding="utf-8")
        tampered_report = json.loads(saved_report)
        tampered_report["artifacts_sha256"]["pcb-connectivity/snapshot.json"] = digest(
            snapshot_path
        )
        workspace.path.write_text(json.dumps(tampered_report), encoding="utf-8")
        try:
            with pytest.raises(ValueError, match="Retained electrical checks fail or omit"):
                workspace.verify()
        finally:
            snapshot_path.write_bytes(saved_snapshot)
            workspace.path.write_bytes(saved_report)
        workspace.verify()


def test_native_pcb_capture_rejects_source_drift_during_successful_runner_call(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    workspace = electrical_evidence_workspace
    config = selected_config(workspace.root, PROJECT)
    board_path = repo_path(workspace.root, config.project).with_suffix(".kicad_pcb")
    board_fixture = (
        Path(__file__).resolve().parents[1]
        / "kicad_tooling/hwrepo/fixtures/pcb-return-alternate-layer-via.kicad_pcb"
    )
    board_path.write_bytes(board_fixture.read_bytes())
    original = board_path.read_bytes()
    original_digest = digest(board_path)
    output = workspace.root / "build/electrical/pcb-source-drift"

    def mutate_source_after_probe_started(root: Path, argv: tuple[str, ...], timeout: int):
        assert root == workspace.root.resolve()
        assert timeout == 600
        board_path.write_bytes(original + b"\n")
        (output / "snapshot.json").write_text(
            json.dumps({"board_sha256": original_digest}), encoding="utf-8"
        )
        command = CommandEvidence(
            argv=argv,
            started_utc=datetime.now(UTC).isoformat(),
            returncode=0,
        )
        assert native_pcb_command_matches(command, config)
        return command

    try:
        with (
            patch(
                "kicad_tooling.hwrepo.pcb_return_path_capture.run_command",
                side_effect=mutate_source_after_probe_started,
            ),
            pytest.raises(
                ValueError,
                match="PCB source changed while native connectivity evidence was captured",
            ),
        ):
            capture_native_pcb_connectivity(workspace.root, config, output)
    finally:
        board_path.write_bytes(original)
