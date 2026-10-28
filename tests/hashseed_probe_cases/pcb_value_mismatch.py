"""Source-bound schematic/PCB value reports for hash-seed tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from tests.design_lint_fixtures.pcb_component_inventory import (
    netlist,
    snapshot,
    source_bound_component_inventory,
)
from tests.json_types import JsonObject

RULE_ID = "pcb.schematic_pcb_value_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"


def value_report(*, schematic_value: str, board_value: str) -> JsonObject:
    """Serialize one source-side value mismatch or a matching fitted control."""
    source_netlist = netlist(
        components={"R1": FOOTPRINT},
        values={"R1": schematic_value},
    )
    board = snapshot(
        "R1",
        schema_version="13",
        footprint_by_reference={"R1": FOOTPRINT},
        value_by_reference={"R1": board_value},
    )
    evidence = source_bound_component_inventory(
        source_netlist,
        board,
        project_id="synthetic-pcb-value",
        board_source=f"synthetic-pcb-value-board:{board_value}".encode(),
        mode="off",
        value_mode="review",
    )
    report = evaluate(
        "synthetic-pcb-value",
        evidence.coach,
        DesignLintPolicy(),
        pcb_component_inventory_coverage=evidence.coverage,
    )
    return {
        "board_sha256": evidence.board_sha256,
        "snapshot_sha256": evidence.snapshot_sha256,
        "netlist_sha256": evidence.netlist_sha256,
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> JsonObject:
    """Return a board-only mismatch, schematic-only mismatch, and control."""
    return {
        "pcb_value_board_only_mismatch": value_report(
            schematic_value="10k",
            board_value="10K",
        ),
        "pcb_value_schematic_only_mismatch": value_report(
            schematic_value="22k",
            board_value="10k",
        ),
        "pcb_value_matching_control": value_report(
            schematic_value="10k",
            board_value="10k",
        ),
    }
