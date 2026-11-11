"""Synthetic regressions for schematic/PCB component value consistency."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from kicad_tooling.hwrepo.design_lint_pcb_value_candidate_evidence import (
    PcbBlockedValueComparisonCandidate,
    PcbValueMismatchCandidate,
    project_blocked_value_comparison_evidence,
    project_pcb_value_mismatch_evidence,
)
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.pcb_component_inventory import (
    evaluate_native_component_inventory_coverage,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbVariantPopulationCoverage,
    PcbVariantPopulationEvidence,
)
from kicad_tooling.hwrepo.pcb_component_population import PcbVariantPopulationSource
from kicad_tooling.hwrepo.pcb_component_values import compare_schematic_pcb_values
from tests.design_lint_fixtures.pcb_component_inventory import (
    BOARD_SHA256,
    NETLIST_SHA256,
    PROBE_SHA256,
    SNAPSHOT_SHA256,
    coach,
    complete_report,
    netlist,
    snapshot,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]
RULE_ID = "pcb.schematic_pcb_value_mismatch"
FOOTPRINT = "Synthetic:Probe_Module"


def test_value_difference_is_reviewable_configurable_and_source_bound() -> None:
    observed = netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"})
    coverage = complete_report(
        observed,
        snapshot(
            "R1",
            schema_version="13",
            footprint_by_reference={"R1": FOOTPRINT},
            value_by_reference={"R1": "10K"},
        ),
        value_mode="review",
    )

    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(coverage) if item.rule_id == RULE_ID
    )
    assert isinstance(candidate, PcbValueMismatchCandidate)
    assert candidate.source_evidence.observation.reference == "R1"
    assert candidate.source_evidence.receipt.snapshot_schema == "13"
    assert (
        candidate.evidence
        == project_pcb_value_mismatch_evidence(candidate.source_evidence).evidence
    )
    assert candidate.subject == "R1: schematic and PCB value fields differ"
    assert candidate.evidence["schematic_value"] == ("10k",)
    assert candidate.evidence["board_value"] == ("10K",)
    assert candidate.evidence["netlist_sha256"] == ("a" * 64,)
    assert candidate.evidence["board_sha256"] == ("b" * 64,)
    assert candidate.evidence["snapshot_sha256"] == ("c" * 64,)
    assert candidate.evidence["snapshot_schema"] == ("13",)

    reviewed = evaluate(
        "synthetic-component-values",
        coach(observed),
        DesignLintPolicy(),
        pcb_component_inventory_coverage=coverage,
    )
    assert reviewed.status == "REVIEW"
    assert tuple(item.rule_id for item in reviewed.findings) == (RULE_ID,)
    assert reviewed.findings[0].mode == "review"

    blocked = evaluate(
        "synthetic-component-values",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="release gate"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert blocked.status == "FAIL"
    assert blocked.findings[0].mode == "block"

    disabled = evaluate(
        "synthetic-component-values",
        coach(observed),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="reviewed format"),)
        ),
        pcb_component_inventory_coverage=coverage,
    )
    assert disabled.status == "PASS"
    assert disabled.findings[0].disposition == "RULE_OFF"

    ignored = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=fingerprint(candidate),
                reason="the board value is an approved assembly label",
            ),
        )
    )
    ignored_report = evaluate(
        "synthetic-component-values",
        coach(observed),
        ignored,
        pcb_component_inventory_coverage=coverage,
    )
    assert ignored_report.findings[0].disposition == "IGNORED"

    changed = coverage.model_copy(
        update={"snapshot_sha256": hashlib.sha256(b"changed board value").hexdigest()}
    )
    stale = evaluate(
        "synthetic-component-values",
        coach(observed),
        ignored,
        pcb_component_inventory_coverage=changed,
    )
    assert stale.findings[0].disposition == "OPEN"
    assert tuple(item.rule_id for item in stale.stale_ignores) == (RULE_ID,)


def test_schema18_supports_complete_source_bound_value_coverage() -> None:
    observed = netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"})
    coverage = complete_report(
        observed,
        snapshot(
            "R1",
            schema_version="19",
            footprint_by_reference={"R1": FOOTPRINT},
            value_by_reference={"R1": "10K"},
        ),
        value_mode="review",
    )

    assert coverage.status == "COMPLETE"
    assert coverage.snapshot_schema == "19"
    assert coverage.value_comparison_status == "COMPLETE"
    assert tuple(item.reference for item in coverage.value_mismatches) == ("R1",)


def test_matching_trimmed_values_and_noncomparable_parts_are_controls() -> None:
    observed = netlist(
        components={"R1": FOOTPRINT, "U1": FOOTPRINT, "R2": "", "U4": FOOTPRINT},
        values={"R1": " 10k ", "U1": "DNP option", "R2": "unplaced", "U4": "missing"},
        dnp=("U1",),
    )
    board = snapshot(
        "R1",
        "U1",
        "R2",
        "U3",
        schema_version="13",
        footprint_by_reference={"R1": FOOTPRINT, "U1": FOOTPRINT, "R2": FOOTPRINT},
        value_by_reference={
            "R1": "10k",
            "U1": "stale DNP label",
            "R2": "unassigned",
            "U3": "extra",
        },
        dnp_by_reference={"U1": True},
    )

    assert compare_schematic_pcb_values(observed, board) == ()
    coverage = complete_report(observed, board, value_mode="review")
    assert not any(item.rule_id == RULE_ID for item in pcb_component_inventory_candidates(coverage))


def test_value_comparison_is_order_independent_and_values_are_case_sensitive() -> None:
    first = compare_schematic_pcb_values(
        netlist(
            components={"R2": FOOTPRINT, "R1": FOOTPRINT},
            values={"R1": "10k", "R2": "1uF"},
        ),
        snapshot(
            "R2",
            "R1",
            schema_version="13",
            footprint_by_reference={"R1": FOOTPRINT, "R2": FOOTPRINT},
            value_by_reference={"R1": "10K", "R2": "1uF-old"},
        ),
    )
    reordered = compare_schematic_pcb_values(
        netlist(
            components={"R1": FOOTPRINT, "R2": FOOTPRINT},
            values={"R1": "10k", "R2": "1uF"},
        ),
        snapshot(
            "R1",
            "R2",
            schema_version="13",
            footprint_by_reference={"R2": FOOTPRINT, "R1": FOOTPRINT},
            value_by_reference={"R2": "1uF-old", "R1": "10K"},
        ),
    )

    assert tuple((item.reference, item.schematic_value, item.board_value) for item in first) == (
        ("R1", "10k", "10K"),
        ("R2", "1uF", "1uF-old"),
    )
    assert reordered == first


def test_named_variant_values_compare_same_name_fitted_sources_and_localize_findings() -> None:
    base = netlist(components={"R1": FOOTPRINT}, values={"R1": "1k"})
    board = snapshot(
        "R1",
        schema_version="13",
        footprint_by_reference={"R1": FOOTPRINT},
        value_by_reference={"R1": "1k"},
    )
    mismatch_source = PcbVariantPopulationSource(
        variant="Assembly A",
        netlist=netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"}),
        board_references=("R1",),
        fitted_board_references=("R1",),
        board_values={"R1": "10K"},
    )
    (mismatch,) = compare_schematic_pcb_values(base, board, (mismatch_source,))
    assert (mismatch.reference, mismatch.schematic_value, mismatch.board_value) == (
        "R1",
        "10k",
        "10K",
    )
    assert mismatch.variant == "Assembly A"

    control_source = replace(mismatch_source, board_values={"R1": "10k"})
    assert compare_schematic_pcb_values(base, board, (control_source,)) == ()

    dnp_source = replace(
        mismatch_source,
        netlist=netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"}, dnp=("R1",)),
    )
    assert compare_schematic_pcb_values(base, board, (dnp_source,)) == ()

    report = complete_report(base, board, value_mode="review").model_copy(
        update={
            "value_mismatches": (mismatch,),
            "variant_population": PcbVariantPopulationCoverage(
                status="COMPLETE",
                project_path="projects/synthetic/controller.kicad_pro",
                project_sha256="d" * 64,
                schematic_path="projects/synthetic/controller.kicad_sch",
                schematic_sha256="e" * 64,
                board_path="projects/synthetic/controller.kicad_pcb",
                board_sha256="f" * 64,
                kicad_version="10.0.5",
                image="ghcr.io/kicad/kicad:10.0.5@sha256:" + "a" * 64,
                board_variant_probe_path="build/variant/probe.json",
                board_variant_probe_sha256="1" * 64,
                board_variant_request_path="build/variant/request.json",
                board_variant_request_sha256="2" * 64,
                board_variant_command_path="build/variant/command.json",
                board_variant_command_sha256="3" * 64,
                evidence=(
                    PcbVariantPopulationEvidence(
                        variant="Assembly A",
                        netlist_path="build/variant/assembly-a.net",
                        netlist_sha256="4" * 64,
                        netlist_command_path="build/variant/netlist-command.json",
                        netlist_command_sha256="5" * 64,
                        board_all_positions_path="build/variant/assembly-a-all.csv",
                        board_all_positions_sha256="6" * 64,
                        board_all_command_path="build/variant/all-command.json",
                        board_all_command_sha256="7" * 64,
                        board_fitted_positions_path="build/variant/assembly-a-fitted.csv",
                        board_fitted_positions_sha256="8" * 64,
                        board_fitted_command_path="build/variant/fitted-command.json",
                        board_fitted_command_sha256="9" * 64,
                    ),
                ),
            ),
        }
    )
    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(report) if item.rule_id == RULE_ID
    )
    assert isinstance(candidate, PcbValueMismatchCandidate)
    assert candidate.source_evidence.observation.variant == "Assembly A"
    assert (
        candidate.evidence
        == project_pcb_value_mismatch_evidence(candidate.source_evidence).evidence
    )
    assert candidate.subject == "R1: schematic and PCB value fields differ in Assembly A"
    assert candidate.evidence["variant"] == ("Assembly A",)
    assert candidate.evidence["variant_project_sha256"] == ("d" * 64,)
    assert candidate.evidence["variant_netlist_sha256"] == ("4" * 64,)
    assert candidate.evidence["variant_board_all_positions_sha256"] == ("6" * 64,)
    assert candidate.evidence["variant_board_fitted_positions_sha256"] == ("8" * 64,)


def test_named_variant_value_comparison_blocks_when_export_is_incomplete() -> None:
    base = netlist(components={"R1": FOOTPRINT}, values={"R1": "1k"})
    board = snapshot(
        "R1",
        schema_version="13",
        footprint_by_reference={"R1": FOOTPRINT},
        value_by_reference={"R1": "1k"},
    )
    source = PcbVariantPopulationSource(
        variant="Assembly A",
        netlist=base,
        board_references=("R1",),
        fitted_board_references=("R1",),
    )
    with pytest.raises(ValueError, match="PCB value export is unavailable"):
        compare_schematic_pcb_values(base, board, (source,))


def test_named_variant_source_defensively_freezes_board_value_map() -> None:
    values = {"R1": "10K"}
    source = PcbVariantPopulationSource(
        variant="Assembly A",
        netlist=netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"}),
        board_references=("R1",),
        fitted_board_references=("R1",),
        board_values=values,
    )

    values["R1"] = "mutated"

    assert source.board_values is not None
    assert source.board_values == {"R1": "10K"}
    assert source.board_value_status == "AVAILABLE"
    with pytest.raises(TypeError):
        source.board_values["R1"] = "mutated"


def test_schema_12_remains_supported_for_inventory_but_blocks_value_comparison() -> None:
    observed = netlist(components={"R1": FOOTPRINT}, values={"R1": "10k"})
    board = snapshot("R1", footprint_by_reference={"R1": FOOTPRINT})
    coverage = evaluate_native_component_inventory_coverage(
        observed,
        board,
        mode="review",
        value_mode="review",
        netlist_sha256=NETLIST_SHA256,
        board_path="synthetic/controller.kicad_pcb",
        board_sha256=BOARD_SHA256,
        snapshot_path="build/design-lint/native/snapshot.json",
        snapshot_sha256=SNAPSHOT_SHA256,
        probe_sha256=PROBE_SHA256,
    )

    assert coverage.status == "COMPLETE"
    assert coverage.value_comparison_status == "BLOCKED"
    (candidate,) = tuple(
        item for item in pcb_component_inventory_candidates(coverage) if item.rule_id == RULE_ID
    )
    assert isinstance(candidate, PcbBlockedValueComparisonCandidate)
    assert candidate.source_evidence.coverage_status == "BLOCKED"
    assert (
        candidate.evidence
        == project_blocked_value_comparison_evidence(candidate.source_evidence).evidence
    )
    assert candidate.evidence["snapshot_schema"] == ("12",)
    assert "schema 13" in candidate.evidence["coverage_issue"][0]
