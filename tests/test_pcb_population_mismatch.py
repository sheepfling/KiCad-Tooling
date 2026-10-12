"""Synthetic regressions for schematic/PCB DNP consistency review."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from kicad_tooling.hwrepo.pcb_component_population import compare_schematic_pcb_population
from tests.design_lint_fixtures.pcb_component_inventory import (
    coach,
    complete_report,
    netlist,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE_ID = "pcb.schematic_pcb_dnp_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"


@pytest.mark.parametrize(
    ("schematic_dnp", "board_dnp"),
    ((False, True), (True, False)),
    ids=("board-only-dnp", "schematic-only-dnp"),
)
def test_schematic_and_board_dnp_disagreement_is_reviewable_and_configurable(
    schematic_dnp: bool,
    board_dnp: bool,
) -> None:
    observed = netlist(
        components={"U1": FOOTPRINT},
        dnp=("U1",) if schematic_dnp else (),
    )
    coverage = complete_report(
        observed,
        snapshot(
            "U1",
            footprint_by_reference={"U1": FOOTPRINT},
            dnp_by_reference={"u1": board_dnp},
        ),
    )

    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(coverage) if item.rule_id == RULE_ID
    )
    assert candidate.subject == "U1: schematic and PCB DNP states differ"
    assert candidate.evidence["schematic_dnp"] == (str(schematic_dnp).lower(),)
    assert candidate.evidence["board_dnp"] == (str(board_dnp).lower(),)
    assert candidate.evidence["netlist_sha256"] == ("a" * 64,)
    assert candidate.evidence["board_sha256"] == ("b" * 64,)
    assert candidate.evidence["snapshot_sha256"] == ("c" * 64,)

    reviewed = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        DesignLintPolicy(),
        pcb_component_inventory_coverage=coverage,
    )
    assert reviewed.status == "REVIEW"
    assert tuple(item.rule_id for item in reviewed.findings) == (RULE_ID,)
    assert reviewed.findings[0].mode == "review"

    blocked = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="release gate"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert blocked.status == "FAIL"
    assert blocked.findings[0].mode == "block"

    disabled_report = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="not needed"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert disabled_report.status == "PASS"
    assert disabled_report.findings[0].disposition == "RULE_OFF"

    ignored = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=fingerprint(candidate),
                reason="reviewed variant-specific population",
            ),
        )
    )
    ignored_report = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        ignored,
        pcb_component_inventory_coverage=coverage,
    )
    assert ignored_report.status == "PASS"
    assert ignored_report.findings[0].disposition == "IGNORED"

    changed_evidence = coverage.model_copy(
        update={"snapshot_sha256": hashlib.sha256(b"changed board snapshot").hexdigest()}
    )
    stale_report = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        ignored,
        pcb_component_inventory_coverage=changed_evidence,
    )
    assert stale_report.findings[0].disposition == "OPEN"
    assert tuple(item.rule_id for item in stale_report.stale_ignores) == (RULE_ID,)


@pytest.mark.parametrize(
    ("schematic_dnp", "board_dnp"),
    ((False, False), (True, True)),
    ids=("both-fitted", "both-dnp"),
)
def test_matching_population_states_are_quiet_controls(
    schematic_dnp: bool,
    board_dnp: bool,
) -> None:
    observed = netlist(
        components={"U1": FOOTPRINT},
        dnp=("U1",) if schematic_dnp else (),
    )
    board = snapshot(
        "U1",
        footprint_by_reference={"U1": FOOTPRINT},
        dnp_by_reference={"U1": board_dnp},
    )

    assert compare_schematic_pcb_population(observed, board) == ()
    assert not any(
        item.rule_id == RULE_ID
        for item in pcb_component_inventory_candidates(complete_report(observed, board))
    )


def test_noncomparable_population_records_are_out_of_scope_controls() -> None:
    schematic_dnp = netlist(components={"U1": FOOTPRINT}, dnp=("U1",))
    no_board_placement = snapshot()
    no_assigned_footprint = netlist(components={"U1": ""}, dnp=("U1",))
    placed_without_schematic_peer = snapshot("U2", dnp_by_reference={"U2": True})

    assert compare_schematic_pcb_population(schematic_dnp, no_board_placement) == ()
    assert (
        compare_schematic_pcb_population(
            no_assigned_footprint,
            snapshot("U1", dnp_by_reference={"U1": False}),
        )
        == ()
    )
    assert compare_schematic_pcb_population(netlist(), placed_without_schematic_peer) == ()


def test_population_comparison_is_order_independent_and_requires_schema_12() -> None:
    first = compare_schematic_pcb_population(
        netlist(components={"U1": FOOTPRINT, "R1": FOOTPRINT}, dnp=("U1",)),
        snapshot("U1", "R1", dnp_by_reference={"U1": False, "R1": True}),
    )
    reordered = compare_schematic_pcb_population(
        netlist(components={"R1": FOOTPRINT, "U1": FOOTPRINT}, dnp=("U1",)),
        snapshot("R1", "u1", dnp_by_reference={"u1": False, "R1": True}),
    )

    assert tuple((item.reference, item.schematic_dnp, item.board_dnp) for item in first) == (
        ("R1", False, True),
        ("U1", True, False),
    )
    assert reordered == first

    with pytest.raises(ValueError, match="schema 12"):
        compare_schematic_pcb_population(
            netlist(components={"U1": FOOTPRINT}),
            snapshot("U1", schema_version="11"),
        )
