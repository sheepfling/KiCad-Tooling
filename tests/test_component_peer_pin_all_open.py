"""Opt-in all-open review for generic pins on repeated component peers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.component_peer_pin_native_support import _run_native_peer_pin_assignment_lane
from tests.component_peer_pin_support import component_peer_coverage, lint_report
from tests.design_lint_fixtures.component_peer_pin_all_open import generic_component_peer_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.generic_peer_pin_all_open"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_all_open_generic_component_peer_pin_is_opt_in_review() -> None:
    observed = generic_component_peer_netlist()
    default = lint_report(observed)
    default_finding = next(item for item in default.findings if item.rule_id == RULE_ID)
    assert default.status == "PASS"
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    default_coverage = component_peer_coverage(default, RULE_ID)
    assert default_coverage.mode == "off"
    assert default_coverage.candidate_group_count == 1
    assert default_coverage.finding_count == 1
    assert default_coverage.suppressed_candidate_count == 0

    report = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic project reviews unused repeated component pins",
                ),
            )
        ),
    )
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.evidence["unassigned_pins"] == ("U1.2", "U2.2")
    assert finding.evidence["shared_anchor_contacts"] == ("U1.1 / U2.1 -> SHARED",)
    assert finding.evidence["pin_function"] == ("Pin_2",)
    assert finding.evidence["pin_electrical_type"] == ("passive",)
    assert "do not establish that this pin must connect" in finding.message
    coverage = component_peer_coverage(report, RULE_ID)
    assert coverage.status == "EVALUATED"
    assert coverage.netlist_sha256 == report.netlist_sha256
    assert coverage.candidate_group_count == coverage.finding_count == 1
    assert coverage.suppressed_candidate_count == 0


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "target_nets",
    (("LOAD", "LOAD"), ("LOAD_A", "LOAD_B")),
    ids=("common-assignment", "separate-assignments"),
)
def test_connected_same_or_separate_pins_are_valid_controls(
    target_nets: tuple[str, str],
) -> None:
    report = lint_report(
        generic_component_peer_netlist(target_nets=target_nets),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic control enables the opt-in rule",
                ),
            )
        ),
    )
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert component_peer_coverage(report, RULE_ID).candidate_group_count == 0


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "target_type",
    ("input", "output", "bidirectional", "tri_state", "open_collector", "open_emitter"),
)
def test_supported_signal_electrical_types_are_reviewable(target_type: str) -> None:
    report = lint_report(
        generic_component_peer_netlist(target_types=(target_type, target_type)),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic case checks the supported native signal type",
                ),
            )
        ),
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["pin_electrical_type"] == (target_type,)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "pin_functions",
    ((None, None), ("1", "2")),
    ids=("absent", "numeric-only"),
)
def test_absent_or_numeric_only_function_metadata_is_still_generic(
    pin_functions: tuple[str | None, str | None],
) -> None:
    report = lint_report(
        generic_component_peer_netlist(pin_functions=pin_functions),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic case checks unknown native pin-function metadata",
                ),
            )
        ),
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["pin_function"] == (pin_functions[1] or "",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "observed",
    (
        generic_component_peer_netlist(anchor_nets=("ANCHOR_A", "ANCHOR_B")),
        generic_component_peer_netlist(anchor_nets=(None, None)),
        generic_component_peer_netlist(target_types=("power_in", "power_in")),
        generic_component_peer_netlist(target_types=("power_out", "power_out")),
        generic_component_peer_netlist(target_types=("free", "free")),
        generic_component_peer_netlist(target_types=("unspecified", "unspecified")),
        generic_component_peer_netlist(pin_functions=("ANCHOR", "RESET_B")),
        generic_component_peer_netlist(dnp=("U2",)),
        generic_component_peer_netlist(references=("J1", "J2")),
        generic_component_peer_netlist(
            symbols={"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"}
        ),
        generic_component_peer_netlist(
            symbols={"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"},
            part_ids={"U1": "SYNTHETIC-PART", "U2": "SYNTHETIC-PART"},
            footprints={"U1": "Synthetic:Module", "U2": "Synthetic:OtherModule"},
        ),
    ),
    ids=(
        "different-anchors",
        "no-anchor",
        "specific-power-type",
        "specific-power-output-type",
        "free-type",
        "unspecified-type",
        "named-target",
        "dnp-peer",
        "connector-references",
        "unmatched-symbols",
        "incomplete-part-identity",
    ),
)
def test_unanchored_or_noncomparable_peers_are_quiet(observed: NetlistContract) -> None:
    report = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic boundary test enables the opt-in rule",
                ),
            )
        ),
    )
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_cross_symbol_part_id_peers_are_reviewable_with_complete_identity() -> None:
    observed = generic_component_peer_netlist(
        symbols={"U1": "Synthetic:ModuleA", "U2": "Synthetic:ModuleB"},
        part_ids={"U1": "SYNTHETIC-MODULE-001", "U2": "synthetic-module-001"},
    )
    report = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic exact PART_ID boundary test",
                ),
            )
        ),
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["peer_group_basis"] == ("part_id",)
    assert finding.evidence["peer_group_identity"] == ("SYNTHETIC-MODULE-001",)
    assert finding.evidence["peer_group_symbols"] == ("Synthetic:ModuleA", "Synthetic:ModuleB")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_a_candidate() -> None:
    observed = generic_component_peer_netlist()
    review = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic policy test enables the heuristic",
                ),
            )
        ),
    )
    finding = next(item for item in review.findings if item.rule_id == RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires disposition of generic open peers",
                ),
            )
        ),
    )
    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project disables this review prompt",
                ),
            )
        ),
    )
    ignored = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic project reviews this heuristic",
                ),
            ),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic part documentation confirms this pin is unused",
                ),
            ),
        ),
    )
    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_stable_under_input_order_changes() -> None:
    observed = generic_component_peer_netlist()
    original = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic deterministic fixture enables the heuristic",
                ),
            )
        ),
    )
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )
    repeated = lint_report(
        reordered,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic deterministic fixture enables the heuristic",
                ),
            )
        ),
    )
    first = next(item for item in original.findings if item.rule_id == RULE_ID)
    second = next(item for item in repeated.findings if item.rule_id == RULE_ID)
    assert first.fingerprint == second.fingerprint
    assert first.evidence == second.evidence


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_component_peer_all_open_fault_and_control_on_pinned_native_versions(
    tmp_path: Path,
) -> None:
    _run_native_peer_pin_assignment_lane("generic-all-open", tmp_path)
