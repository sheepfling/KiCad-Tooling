"""Source-bound schematic/PCB DNP reports for hash-seed tests."""

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

RULE_ID = "pcb.schematic_pcb_dnp_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"


def dnp_report(*, schematic_dnp: bool, board_dnp: bool) -> dict[str, object]:
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
    netlist_sha256 = sha256(model_json_bytes(source_netlist)).hexdigest()
    board_sha256 = sha256(f"synthetic-dnp-board:{board_dnp}".encode()).hexdigest()
    board = board.model_copy(update={"board_sha256": board_sha256})
    snapshot_sha256 = sha256(model_json_bytes(board)).hexdigest()
    coverage = evaluate_native_component_inventory_coverage(
        source_netlist,
        board,
        mode="review",
        netlist_sha256=netlist_sha256,
        board_path="projects/synthetic-dnp/board.kicad_pcb",
        board_sha256=board_sha256,
        snapshot_path="build/design-lint/synthetic-dnp.json",
        snapshot_sha256=snapshot_sha256,
        probe_sha256=board.probe_sha256,
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-dnp",
        source_hashes={},
        netlist_sha256=netlist_sha256,
        observed=source_netlist,
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


def report_cases() -> dict[str, object]:
    """Return both mismatch directions and a matching fitted control."""
    return {
        "pcb_dnp_board_only_mismatch": dnp_report(schematic_dnp=False, board_dnp=True),
        "pcb_dnp_schematic_only_mismatch": dnp_report(schematic_dnp=True, board_dnp=False),
        "pcb_dnp_fitted_control": dnp_report(schematic_dnp=False, board_dnp=False),
    }
