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
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbVariantPopulationCoverage,
    PcbVariantPopulationEvidence,
)
from kicad_tooling.hwrepo.pcb_component_population import (
    PcbVariantPopulationSource,
    compare_schematic_pcb_population,
)
from tests.design_lint_fixtures.pcb_component_inventory import (
    coach,
    complete_report,
    netlist,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE_ID = "pcb.schematic_pcb_dnp_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"
IMAGE = "registry.example/kicad:10.0.5@sha256:" + "f" * 64


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


@pytest.mark.parametrize(
    ("schematic_dnp", "board_dnp"),
    ((False, True), (True, False)),
    ids=("board-variant-only-dnp", "schematic-variant-only-dnp"),
)
def test_named_variant_population_mismatch_uses_paired_source_evidence(
    schematic_dnp: bool,
    board_dnp: bool,
) -> None:
    base_netlist = netlist(components={"U1": FOOTPRINT})
    base_board = snapshot("U1", footprint_by_reference={"U1": FOOTPRINT})
    variant_netlist = netlist(
        components={"U1": FOOTPRINT},
        dnp=("U1",) if schematic_dnp else (),
    )
    variant_source = PcbVariantPopulationSource(
        variant="Assembly A",
        netlist=variant_netlist,
        board_references=("U1",),
        fitted_board_references=() if board_dnp else ("U1",),
    )

    (mismatch,) = compare_schematic_pcb_population(
        base_netlist,
        base_board,
        variants=(variant_source,),
    )

    assert (mismatch.reference, mismatch.variant) == ("U1", "Assembly A")
    assert (mismatch.schematic_dnp, mismatch.board_dnp) == (schematic_dnp, board_dnp)


def test_named_variant_population_controls_and_inconsistent_exports() -> None:
    variant_source = PcbVariantPopulationSource(
        variant="Assembly A",
        netlist=netlist(components={"U1": FOOTPRINT}),
        board_references=("U1",),
        fitted_board_references=("U1",),
    )
    base_netlist = netlist(components={"U1": FOOTPRINT})
    base_board = snapshot("U1", footprint_by_reference={"U1": FOOTPRINT})

    assert (
        compare_schematic_pcb_population(
            base_netlist,
            base_board,
            variants=(variant_source,),
        )
        == ()
    )
    with pytest.raises(ValueError, match="missing reference"):
        compare_schematic_pcb_population(
            base_netlist,
            base_board,
            variants=(
                variant_source.__class__(
                    variant="Assembly A",
                    netlist=variant_source.netlist,
                    board_references=(),
                    fitted_board_references=("U1",),
                ),
            ),
        )
    with pytest.raises(ValueError, match="unique case-insensitively"):
        compare_schematic_pcb_population(
            base_netlist,
            base_board,
            variants=(variant_source, variant_source),
        )


def test_variant_population_findings_carry_variant_exports_and_policy_modes() -> None:
    base_netlist = netlist(components={"U1": FOOTPRINT})
    base_board = snapshot("U1", footprint_by_reference={"U1": FOOTPRINT})
    mismatch = compare_schematic_pcb_population(
        base_netlist,
        base_board,
        variants=(
            PcbVariantPopulationSource(
                variant="Assembly A",
                netlist=netlist(components={"U1": FOOTPRINT}),
                board_references=("U1",),
                fitted_board_references=(),
            ),
        ),
    )
    variant_evidence = PcbVariantPopulationEvidence(
        variant="Assembly A",
        netlist_path="build/design-lint/variant/variant.netlist.xml",
        netlist_sha256="1" * 64,
        netlist_command_path="build/design-lint/variant/netlist.command.json",
        netlist_command_sha256="2" * 64,
        board_all_positions_path="build/design-lint/variant/board-all.csv",
        board_all_positions_sha256="3" * 64,
        board_all_command_path="build/design-lint/variant/board-all.command.json",
        board_all_command_sha256="4" * 64,
        board_fitted_positions_path="build/design-lint/variant/board-fitted.csv",
        board_fitted_positions_sha256="5" * 64,
        board_fitted_command_path="build/design-lint/variant/board-fitted.command.json",
        board_fitted_command_sha256="6" * 64,
    )
    variant_coverage = PcbVariantPopulationCoverage(
        status="COMPLETE",
        project_path="projects/synthetic/controller.kicad_pro",
        project_sha256="7" * 64,
        schematic_path="projects/synthetic/controller.kicad_sch",
        schematic_sha256="8" * 64,
        board_path="projects/synthetic/controller.kicad_pcb",
        board_sha256="9" * 64,
        kicad_version="10.0.5",
        image=IMAGE,
        board_variant_probe_path="build/design-lint/variant/native_pcb_variant_probe.py",
        board_variant_probe_sha256="a" * 64,
        board_variant_request_path="build/design-lint/variant/board-variant-request.json",
        board_variant_request_sha256="b" * 64,
        board_variant_command_path="build/design-lint/variant/board-variant-probe.command.json",
        board_variant_command_sha256="c" * 64,
        evidence=(variant_evidence,),
    )
    coverage = complete_report(base_netlist, base_board).model_copy(
        update={"population_mismatches": mismatch, "variant_population": variant_coverage}
    )

    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(coverage) if item.rule_id == RULE_ID
    )
    assert candidate.subject.endswith("in Assembly A")
    assert candidate.evidence["variant"] == ("Assembly A",)
    assert candidate.evidence["variant_project_sha256"] == ("7" * 64,)
    assert candidate.evidence["variant_board_sha256"] == ("9" * 64,)
    assert candidate.evidence["variant_netlist_sha256"] == ("1" * 64,)
    assert candidate.evidence["variant_board_all_positions_sha256"] == ("3" * 64,)
    review = evaluate(
        "synthetic-component-inventory",
        coach(base_netlist),
        DesignLintPolicy(),
        pcb_component_inventory_coverage=coverage,
    )
    assert review.status == "REVIEW"
    block = evaluate(
        "synthetic-component-inventory",
        coach(base_netlist),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="release check"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert block.status == "FAIL"
    off = evaluate(
        "synthetic-component-inventory",
        coach(base_netlist),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="variant not used"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert off.status == "PASS"


def test_named_variant_export_gap_is_reviewable_and_can_be_blocking() -> None:
    observed = netlist(components={"U1": FOOTPRINT})
    board = snapshot("U1", footprint_by_reference={"U1": FOOTPRINT})
    coverage = complete_report(observed, board).model_copy(
        update={
            "variant_population": PcbVariantPopulationCoverage(
                status="BLOCKED",
                project_path="projects/synthetic/controller.kicad_pro",
                project_sha256="a" * 64,
                board_path="projects/synthetic/controller.kicad_pcb",
                board_sha256="b" * 64,
                kicad_version="10.0.5",
                image=IMAGE,
                issue="PCB source does not contain the declared named variant",
            )
        }
    )

    review = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        DesignLintPolicy(),
        pcb_component_inventory_coverage=coverage,
    )
    assert review.status == "REVIEW"
    assert any(
        item.subject == "named variant DNP comparison unavailable" for item in review.findings
    )
    blocked = evaluate(
        "synthetic-component-inventory",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="release check"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert blocked.status == "FAIL"
