"""Source-bound test-access pad and probe evidence replay regression."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest, source_state
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    PcbAccessAnalysis,
    PcbAccessProbeRequestSet,
    RequiredTestAccess,
    ValidationSummary,
)
from kicad_tooling.hwrepo.models import (
    TestAccessAnalysis as AccessAnalysis,
)
from kicad_tooling.hwrepo.models import (
    TestAccessEndpointRequirement as AccessEndpointRequirement,
)
from kicad_tooling.hwrepo.models import (
    TestAccessProbeEnvelope as AccessProbeEnvelope,
)
from kicad_tooling.hwrepo.releasing import reference
from kicad_tooling.validate import hashes, repo_path
from tests.electrical_evidence_support import (
    ElectricalEvidenceWorkspace,
)
from tests.electrical_evidence_support import (
    electrical_evidence_workspace as _electrical_evidence_workspace_fixture,  # noqa: F401
)
from tests.electrical_simulation_support import (
    ISLAND,
    NA,
    PROJECT,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.template_checkout,
]


def test_saved_pcb_access_stages_replay_source_bound_pad_evidence(
    electrical_evidence_workspace: ElectricalEvidenceWorkspace,
) -> None:
    workspace = electrical_evidence_workspace
    access = AccessAnalysis(
        basis="Synthetic service procedure requires a logic-rail measurement",
        pcb_accessibility=PcbAccessAnalysis(
            basis="Synthetic test pad must be placed and mask-open"
        ),
        decisions=(
            RequiredTestAccess(
                mode="required",
                id="logic-rail",
                basis="Synthetic factory measurement point",
                net="+3V3",
                endpoints=(
                    AccessEndpointRequirement(
                        kind="test_point",
                        reference="TP1",
                        symbol="TestPoint:TestPoint",
                        footprint="TestPoint:TestPoint_Pad_D1.0mm",
                        pin="TP1.1",
                        electrical_type="passive",
                        approach_side="front",
                        probe_envelope=AccessProbeEnvelope(
                            tip_diameter_mm=0.8,
                            clearance_mm=0.1,
                        ),
                    ),
                ),
            ),
        ),
    )
    contract_path = workspace.root / ISLAND / "tests/electrical.json"
    write_model(
        contract_path,
        workspace.contract.model_copy(update={"test_access": access, "power": NA}),
    )
    config = selected_config(workspace.root, PROJECT)
    board_path = repo_path(workspace.root, config.project).with_suffix(".kicad_pcb")
    board_path.write_text(
        '(kicad_pcb (version 20250114) (net 0 "") (net 1 "+3V3") (net 2 "OTHER") '
        '(footprint "TestPoint:TestPoint_Pad_D1.0mm" (layer "F.Cu") '
        '(property "Reference" "TP1") '
        '(pad "1" smd circle (at 0 0) (size 1 1) '
        '(layers "F.Cu" "F.Mask") (net 1 "+3V3"))) '
        '(footprint "Synthetic:Obstacle" (layer "F.Cu") (at 1 0) '
        '(property "Reference" "TP2") '
        '(pad "1" smd circle (at 0 0) (size 1 1) '
        '(layers "F.Cu" "F.Mask") (net 2 "OTHER"))))',
        encoding="utf-8",
    )
    native_path = workspace.root / workspace.native.path
    netlist_path = native_path.parent / "netlist.xml"
    netlist_path.write_text(
        '<export><components><comp ref="TP1"><value>TestPoint</value>'
        "<footprint>TestPoint:TestPoint_Pad_D1.0mm</footprint>"
        '<libsource lib="TestPoint" part="TestPoint"/>'
        '<units><unit name="A"><pins><pin num="1"/></pins></unit></units>'
        '</comp></components><libparts><libpart lib="TestPoint" part="TestPoint">'
        '<pins><pin num="1" name="TestPoint" type="passive"/></pins>'
        '</libpart></libparts><nets><net name="+3V3"><node ref="TP1" pin="1"/>'
        "</net></nets></export>",
        encoding="utf-8",
    )
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
            "user.name=Synthetic test fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Synthetic PCB test-access requirements",
        ),
        check=True,
        capture_output=True,
    )
    workspace.source = source_state(workspace.root)
    summary = read_model(native_path, ValidationSummary)
    current_hashes = hashes(workspace.root, config.source_roots)
    summary_checks = dict(summary.checks)
    for check_id in ("source_scope", "source_unchanged"):
        summary_checks[check_id] = summary_checks[check_id].model_copy(
            update={"source_hashes": current_hashes}
        )
    write_model(
        native_path,
        summary.model_copy(
            update={
                "checked_commit": workspace.source.commit,
                "source": workspace.source,
                "checks": summary_checks,
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "netlist.xml": digest(netlist_path),
                },
            }
        ),
    )
    workspace.native = reference(workspace.root, native_path)
    workspace.output = workspace.root / "build/electrical/pcb-access-replay"
    connectivity_output = workspace.output / "pcb-connectivity"

    def fake_native_probe(root: Path, argv: tuple[str, ...], timeout: int):
        assert root == workspace.root.resolve()
        assert timeout == 600
        request_path = connectivity_output / "access-probe-requests.json"
        requests = read_model(request_path, PcbAccessProbeRequestSet)
        assert len(requests.requests) == 1
        board_hash = digest(board_path)
        (connectivity_output / "snapshot.json").write_text(
            json.dumps(
                {
                    "schema_version": "4",
                    "board_sha256": board_hash,
                    "kicad_version": config.kicad_version,
                    "zones_refilled": True,
                    "pads": [
                        {
                            "pad": "TP1.1",
                            "net": "+3V3",
                            "footprint": "TestPoint:TestPoint_Pad_D1.0mm",
                            "dnp": False,
                            "connected_pads": ["TP1.1"],
                            "connected_vias": [],
                            "connected_zones": [],
                            "connected_islands": [],
                        },
                        {
                            "pad": "TP2.1",
                            "net": "OTHER",
                            "footprint": "Synthetic:Obstacle",
                            "dnp": False,
                            "connected_pads": ["TP2.1"],
                            "connected_vias": [],
                            "connected_zones": [],
                            "connected_islands": [],
                        },
                    ],
                    "vias": [],
                    "net_ties": [],
                    "zones": [],
                    "access_probe_observations": [
                        {
                            "endpoint": "TP1.1",
                            "side": "front",
                            "target_net": "+3V3",
                            "target_exposed": True,
                            "obstacle": "TP2.1",
                            "obstacle_net": "OTHER",
                            "distance_nm": 500000,
                            "target_aperture_shape": "circle",
                            "target_aperture_diameter_nm": 1000000,
                        }
                    ],
                    "access_probe_requests_sha256": digest(request_path),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return CommandEvidence(
            argv=argv,
            started_utc=datetime.now(UTC).isoformat(),
            returncode=0,
        )

    with patch(
        "kicad_tooling.hwrepo.pcb_return_path_capture.run_command",
        side_effect=fake_native_probe,
    ):
        report = analyze(
            workspace.root,
            PROJECT,
            workspace.output,
            native_summary=native_path,
            ngspice=str(workspace.simulator),
        )
    assert report.status == "PASS", report
    rows = {row.id: row for row in report.checks}
    assert rows["test-access/schematic/logic-rail"].status == "PASS"
    assert rows["test-access/pcb-accessibility/logic-rail"].status == "PASS"
    assert rows["test-access/pcb-probe-envelope/logic-rail"].status == "PASS"
    workspace.path = workspace.output / "electrical.json"
    workspace.verify()

    request_path = workspace.output / "pcb-connectivity/access-probe-requests.json"
    snapshot_path = workspace.output / "pcb-connectivity/snapshot.json"
    saved_request = request_path.read_bytes()
    saved_snapshot = snapshot_path.read_bytes()
    saved_report = workspace.path.read_bytes()

    tampered_request = json.loads(saved_request)
    tampered_request["requests"][0]["net"] = "OTHER"
    request_path.write_text(json.dumps(tampered_request), encoding="utf-8")
    tampered_report = json.loads(saved_report)
    tampered_report["artifacts_sha256"]["pcb-connectivity/access-probe-requests.json"] = digest(
        request_path
    )
    workspace.path.write_text(json.dumps(tampered_report), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="requests differ from current requirements"):
            workspace.verify()
    finally:
        request_path.write_bytes(saved_request)
        workspace.path.write_bytes(saved_report)

    for field, value, expected in (
        ("distance_nm", 499999, "Retained electrical checks fail or omit"),
        (
            "target_aperture_diameter_nm",
            999999,
            "Retained electrical checks fail or omit",
        ),
    ):
        tampered_snapshot = json.loads(saved_snapshot)
        tampered_snapshot["access_probe_observations"][0][field] = value
        snapshot_path.write_text(json.dumps(tampered_snapshot), encoding="utf-8")
        tampered_report = json.loads(saved_report)
        tampered_report["artifacts_sha256"]["pcb-connectivity/snapshot.json"] = digest(
            snapshot_path
        )
        workspace.path.write_text(json.dumps(tampered_report), encoding="utf-8")
        try:
            with pytest.raises(ValueError, match=expected):
                workspace.verify()
        finally:
            snapshot_path.write_bytes(saved_snapshot)
            workspace.path.write_bytes(saved_report)
        workspace.verify()

    board_path.write_text(board_path.read_text().replace('"F.Mask"', '"F.Paste"'))
    with pytest.raises(ValueError, match="inputs differ"):
        workspace.verify()
