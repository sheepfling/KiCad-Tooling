"""Source-bound schematic/PCB pad-net reports for hash-seed tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from tests.design_lint_fixtures.pcb_component_inventory import (
    netlist,
    snapshot,
    source_bound_component_inventory,
)

RULE_ID = "pcb.schematic_pcb_pad_net_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"


def pad_net_report(*, schematic_net: str, board_net: str) -> dict[str, object]:
    """Serialize one side-specific net mismatch or an exact assignment control."""
    source_netlist = netlist(
        components={"U1": FOOTPRINT},
        nets={schematic_net: ("U1.1",)},
        component_pin_numbers={"U1": ("1",)},
    )
    board = snapshot(
        "U1",
        schema_version="13",
        footprint_by_reference={"U1": FOOTPRINT},
        pad_net_by_reference={"U1.1": board_net},
    )
    evidence = source_bound_component_inventory(
        source_netlist,
        board,
        project_id="synthetic-pcb-pad-net",
        board_source=f"synthetic-pcb-pad-net-board:{board_net}".encode(),
        mode="off",
        pad_net_mode="review",
    )
    report = evaluate(
        "synthetic-pcb-pad-net",
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


def report_cases() -> dict[str, object]:
    """Return board-only and schematic-only mismatches with a matching control."""
    return {
        "pcb_pad_net_board_only_mismatch": pad_net_report(
            schematic_net="SIGNAL",
            board_net="BOARD_SIGNAL",
        ),
        "pcb_pad_net_schematic_only_mismatch": pad_net_report(
            schematic_net="SCHEMATIC_SIGNAL",
            board_net="SIGNAL",
        ),
        "pcb_pad_net_matching_control": pad_net_report(
            schematic_net="SIGNAL",
            board_net="SIGNAL",
        ),
    }
