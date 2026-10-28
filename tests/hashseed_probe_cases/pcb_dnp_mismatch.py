"""Source-bound schematic/PCB DNP reports for hash-seed tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from tests.design_lint_fixtures.pcb_component_inventory import (
    netlist,
    snapshot,
    source_bound_component_inventory,
)
from tests.json_types import JsonObject

RULE_ID = "pcb.schematic_pcb_dnp_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"


def dnp_report(*, schematic_dnp: bool, board_dnp: bool) -> JsonObject:
    """Serialize one DNP mismatch direction or a matching fitted control."""
    source_netlist = netlist(
        components={"U1": FOOTPRINT},
        dnp=("U1",) if schematic_dnp else (),
    )
    board = snapshot(
        "U1",
        schema_version="13",
        footprint_by_reference={"U1": FOOTPRINT},
        dnp_by_reference={"U1": board_dnp},
    )
    evidence = source_bound_component_inventory(
        source_netlist,
        board,
        project_id="synthetic-dnp",
        board_source=f"synthetic-dnp-board:{board_dnp}".encode(),
        mode="review",
    )
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Review the exact schematic/PCB population mismatch",
            ),
        )
    )
    report = evaluate(
        "synthetic-dnp",
        evidence.coach,
        policy,
        pcb_component_inventory_coverage=evidence.coverage,
    )
    return {
        "board_sha256": evidence.board_sha256,
        "snapshot_sha256": evidence.snapshot_sha256,
        "netlist_sha256": evidence.netlist_sha256,
        "report": report.model_dump(mode="json"),
    }


def report_cases() -> JsonObject:
    """Return both mismatch directions and a matching fitted control."""
    return {
        "pcb_dnp_board_only_mismatch": dnp_report(schematic_dnp=False, board_dnp=True),
        "pcb_dnp_schematic_only_mismatch": dnp_report(schematic_dnp=True, board_dnp=False),
        "pcb_dnp_fitted_control": dnp_report(schematic_dnp=False, board_dnp=False),
    }
