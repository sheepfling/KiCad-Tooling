"""Synthetic schematic-to-PCB inventory reports for hash-seed checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures.pcb_component_inventory import (
    coach,
    complete_report,
    netlist,
    snapshot,
)
from tests.json_types import JsonObject


def _inventory_report(
    *, board_references: tuple[str, ...], placed_footprint: str | None
) -> JsonObject:
    observed = netlist(components={"U1": "Package_QFP:TQFP-48"})
    board = snapshot(
        *board_references,
        footprint_by_reference=({"U1": placed_footprint} if placed_footprint is not None else None),
    )
    report = evaluate(
        "synthetic-pcb-component-inventory-hash-seed",
        coach(observed),
        DesignLintPolicy(),
        pcb_component_inventory_coverage=complete_report(observed, board),
    )
    return report.model_dump(mode="json")


def report_cases() -> JsonObject:
    """Return missing, mismatched, and exact-footprint inventory cases."""
    return {
        "pcb_inventory_missing_placement_fault": _inventory_report(
            board_references=(), placed_footprint=None
        ),
        "pcb_inventory_footprint_mismatch_fault": _inventory_report(
            board_references=("U1",), placed_footprint="Package_QFP:QFN-48"
        ),
        "pcb_inventory_exact_footprint_control": _inventory_report(
            board_references=("U1",), placed_footprint="Package_QFP:TQFP-48"
        ),
    }
