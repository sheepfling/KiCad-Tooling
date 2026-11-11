"""Source-bound synthetic PCB fiducial rule reachability."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from kicad_tooling.hwrepo.pcb_fiducials import evaluate_pcb_fiducials
from tests.design_lint_fixtures.pcb_component_inventory import (
    coach,
    complete_report,
    netlist,
)
from tests.pcb_fiducials_support import (
    BOARD_PATH,
    BOARD_SHA256,
    FIDUCIAL_FOOTPRINT,
    NETLIST_SHA256,
    requirement_map,
    snapshot,
    source_evidence,
)


def pcb_fiducial_rule_ids() -> set[str]:
    """Emit the opt-in board-fiducial shortfall finding on source-bound evidence."""
    authored = requirement_map()
    observed = netlist(components={"U1": "Package_QFP:TQFP-48"})
    board = snapshot(
        (
            ("U1", "Package_QFP:TQFP-48", False, "F.Cu"),
            ("FID1", FIDUCIAL_FOOTPRINT, False, "F.Cu"),
            ("FID2", FIDUCIAL_FOOTPRINT, False, "B.Cu"),
            ("FID3", FIDUCIAL_FOOTPRINT, True, "F.Cu"),
            ("H1", "Synthetic:MountingHole", False, "F.Cu"),
        )
    )
    evidence = source_evidence(board)
    coverage = evaluate_pcb_fiducials(authored, "review", evidence, NETLIST_SHA256)
    inventory = complete_report(observed, evidence.snapshot).model_copy(
        update={"fiducial_coverage": coverage}
    )
    source_coach = coach(observed).model_copy(update={"source_hashes": {BOARD_PATH: BOARD_SHA256}})
    report = evaluate(
        "synthetic-component-inventory",
        source_coach,
        DesignLintPolicy(pcb_fiducial_map=authored),
        pcb_component_inventory_coverage=inventory,
    )
    return {item.rule_id for item in report.findings}
