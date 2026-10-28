"""Opt-in board-only footprint review reports for hash-seed tests."""

from __future__ import annotations

from hashlib import sha256

from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import ContractCoachReport
from kicad_tooling.hwrepo.pcb_component_inventory import (
    evaluate_native_component_inventory_coverage,
)
from tests.design_lint_fixtures.pcb_component_inventory import netlist, snapshot
from tests.json_types import JsonObject

RULE_ID = "pcb.board_only_footprint"


def board_only_report(*, include_mounting_hole: bool) -> JsonObject:
    """Serialize an unmatched mounting-hole candidate or matched control."""
    source_netlist = netlist(components={"J1": "Connector:USB_B"})
    board_references = ("J1", "H_MOUNT1") if include_mounting_hole else ("J1",)
    board = snapshot(
        *board_references,
        schema_version="13",
        footprint_by_reference={
            "J1": "Connector:USB_B",
            "H_MOUNT1": "MountingHole:NPTH",
        },
    )
    netlist_sha256 = sha256(model_json_bytes(source_netlist)).hexdigest()
    board_sha256 = sha256(f"synthetic-board-only:{board_references}".encode()).hexdigest()
    board = board.model_copy(update={"board_sha256": board_sha256})
    snapshot_sha256 = sha256(model_json_bytes(board)).hexdigest()
    coverage = evaluate_native_component_inventory_coverage(
        source_netlist,
        board,
        mode="off",
        netlist_sha256=netlist_sha256,
        board_path="projects/synthetic-board-only/board.kicad_pcb",
        board_sha256=board_sha256,
        snapshot_path="build/design-lint/synthetic-board-only.json",
        snapshot_sha256=snapshot_sha256,
        probe_sha256=board.probe_sha256,
        board_only_mode="review",
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-board-only",
        source_hashes={},
        netlist_sha256=netlist_sha256,
        observed=source_netlist,
    )
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Inspect the unmatched synthetic board footprint",
            ),
        )
    )
    report = evaluate(
        "synthetic-board-only",
        coach,
        policy,
        pcb_component_inventory_coverage=coverage,
    )
    return {
        "board_sha256": board_sha256,
        "snapshot_sha256": snapshot_sha256,
        "netlist_sha256": netlist_sha256,
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> JsonObject:
    """Return a REVIEW candidate plus a matched-reference control."""
    return {
        "pcb_board_only_mounting_hole_candidate": board_only_report(include_mounting_hole=True),
        "pcb_board_only_matched_inventory_control": board_only_report(include_mounting_hole=False),
    }
