"""Source-bound touch-pad clearance reports for hash-seed tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import map_sha256
from kicad_tooling.hwrepo.models import ContractCoachReport, DesignLintPolicy
from kicad_tooling.hwrepo.pcb_touch_pad_clearance import touch_pad_clearance_entries
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageReport,
)
from tests.pcb_touch_pad_clearance_support import clearance_map, netlist, snapshot


def clearance_report(*, distance_nm: int) -> dict[str, object]:
    """Serialize a below-minimum fault or exact-minimum control."""
    authored = clearance_map(minimum_clearance_nm=800_000)
    source_netlist = netlist()
    observed_board = snapshot(
        distance_nm=distance_nm,
        minimum_clearance_nm=800_000,
    )
    board_sha256 = sha256(f"synthetic-touch-clearance:{distance_nm}".encode()).hexdigest()
    observed_board = observed_board.model_copy(update={"board_sha256": board_sha256})
    netlist_sha256 = sha256(model_json_bytes(source_netlist)).hexdigest()
    snapshot_sha256 = sha256(model_json_bytes(observed_board)).hexdigest()
    entries = touch_pad_clearance_entries(authored, observed_board, source_netlist)
    request_sha256 = observed_board.touch_pad_clearance_requests_sha256
    assert request_sha256 is not None
    coverage = PcbTouchPadClearanceCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode="review",
        map_sha256=map_sha256(authored),
        board_path="projects/synthetic-touch-clearance/board.kicad_pcb",
        board_sha256=board_sha256,
        snapshot_path="build/design-lint/synthetic-touch-clearance.json",
        snapshot_sha256=snapshot_sha256,
        probe_sha256=observed_board.probe_sha256,
        request_sha256=request_sha256,
        kicad_version=observed_board.kicad_version,
        image=observed_board.image,
        netlist_sha256=netlist_sha256,
        requirement_count=len(authored.requirements),
        entries=entries,
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-touch-clearance",
        source_hashes={},
        netlist_sha256=netlist_sha256,
        observed=source_netlist,
    )
    report = evaluate(
        "synthetic-touch-clearance",
        coach,
        DesignLintPolicy(pcb_touch_pad_clearance_map=authored),
        pcb_touch_pad_clearance_coverage=coverage,
    )
    return {
        "requirement_sha256": coverage.map_sha256,
        "board_sha256": coverage.board_sha256,
        "snapshot_sha256": coverage.snapshot_sha256,
        "netlist_sha256": netlist_sha256,
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> dict[str, object]:
    """Return a fault and exact-threshold control with identical requirements."""
    return {
        "pcb_touch_pad_clearance_fault": clearance_report(distance_nm=500_000),
        "pcb_touch_pad_clearance_boundary_control": clearance_report(distance_nm=800_000),
    }
