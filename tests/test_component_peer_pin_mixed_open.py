"""Opt-in review when equivalent generic component peers split open and assigned pins."""

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
from tests.design_lint_fixtures.component_peer_pin_all_open import (
    generic_component_peer_mixed_netlist,
    generic_component_peer_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.generic_peer_pin_mixed_open"


def _review_policy() -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic project reviews generic peer-pin differences",
            ),
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_peer_pin_open_on_subset_is_opt_in_review() -> None:
    observed = generic_component_peer_mixed_netlist()
    default = lint_report(observed)
    default_finding = next(item for item in default.findings if item.rule_id == RULE_ID)
    assert default.status == "PASS"
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    default_coverage = component_peer_coverage(default, RULE_ID)
    assert default_coverage.mode == "off"
    assert default_coverage.candidate_group_count == default_coverage.finding_count == 1

    report = lint_report(observed, _review_policy())
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.evidence["assigned_pins"] == ("U1.2", "U2.2")
    assert finding.evidence["unassigned_pins"] == ("U3.2",)
    assert finding.evidence["shared_assignment_net"] == ("LOAD",)
    assert finding.evidence["shared_anchor_contacts"] == ("U1.1 / U2.1 / U3.1 -> SHARED",)
    assert finding.evidence["pin_function"] == ("Pin_2",)
    assert finding.evidence["pin_electrical_type"] == ("passive",)
    assert "do not establish that the pins must connect" in finding.message
    coverage = component_peer_coverage(report, RULE_ID)
    assert coverage.status == "EVALUATED"
    assert coverage.netlist_sha256 == report.netlist_sha256
    assert coverage.finding_count == coverage.candidate_group_count == 1
    assert coverage.suppressed_candidate_count == 0


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "observed",
    (
        generic_component_peer_mixed_netlist(target_nets=("LOAD", "LOAD", "LOAD")),
        generic_component_peer_mixed_netlist(target_nets=("LOAD_A", "LOAD_B", None)),
        generic_component_peer_mixed_netlist(target_nets=("LOAD", None, None)),
        generic_component_peer_mixed_netlist(anchor_nets=("SHARED", "OTHER", "SHARED")),
        generic_component_peer_mixed_netlist(anchor_nets=(None, None, None)),
        generic_component_peer_mixed_netlist(pin_functions=("ANCHOR", "RESET_B")),
        generic_component_peer_mixed_netlist(target_types=("power_in",) * 3),
        generic_component_peer_mixed_netlist(target_types=("power_out",) * 3),
        generic_component_peer_mixed_netlist(target_types=("input",) * 3),
        generic_component_peer_mixed_netlist(target_types=("output",) * 3),
        generic_component_peer_mixed_netlist(target_types=("bidirectional",) * 3),
        generic_component_peer_mixed_netlist(target_types=("free",) * 3),
        generic_component_peer_mixed_netlist(target_types=("unspecified",) * 3),
        generic_component_peer_mixed_netlist(dnp=("U3",)),
        generic_component_peer_netlist(
            references=("U1", "U2"),
            anchor_nets=("SHARED", "SHARED"),
            target_nets=("LOAD", None),
        ),
        generic_component_peer_netlist(
            references=("J1", "J2", "J3"),
            anchor_nets=("SHARED", "SHARED", "SHARED"),
            target_nets=("LOAD", "LOAD", None),
            target_types=("passive", "passive", "passive"),
        ),
        generic_component_peer_mixed_netlist(
            symbols={
                "U1": "Synthetic:ModuleA",
                "U2": "Synthetic:ModuleB",
                "U3": "Synthetic:ModuleC",
            }
        ),
    ),
    ids=(
        "all-connected",
        "assigned-peers-disagree",
        "one-assigned-peer",
        "no-shared-anchor",
        "no-anchor",
        "named-pin-function",
        "power-input",
        "power-output",
        "typed-input-covered-elsewhere",
        "typed-output-covered-elsewhere",
        "typed-bidirectional-covered-elsewhere",
        "free-pin",
        "unspecified-pin",
        "dnp-open-peer",
        "only-two-peers",
        "connector-references",
        "unmatched-symbols",
    ),
)
def test_partial_open_candidates_require_comparable_consensus_and_anchor(
    observed: NetlistContract,
) -> None:
    report = lint_report(observed, _review_policy())
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "electrical_type", ("passive", "tri_state", "open_collector", "open_emitter")
)
def test_mixed_open_rule_supports_untyped_or_generic_component_pin_classes(
    electrical_type: str,
) -> None:
    report = lint_report(
        generic_component_peer_mixed_netlist(target_types=(electrical_type,) * 3),
        _review_policy(),
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["pin_electrical_type"] == (electrical_type,)
    assert finding.evidence["unassigned_pins"] == ("U3.2",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "target_function",
    (None, "2", "Pin_2"),
    ids=("absent", "numeric-only", "generic-placeholder"),
)
def test_mixed_open_rule_accepts_generic_or_missing_pin_functions(
    target_function: str | None,
) -> None:
    report = lint_report(
        generic_component_peer_mixed_netlist(pin_functions=("ANCHOR", target_function)),
        _review_policy(),
    )
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["pin_function"] == (target_function or "",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("electrical_type", "existing_rule"),
    (
        ("input", "component.peer_signal_input_unconnected"),
        ("output", "component.peer_signal_output_unconnected"),
        ("bidirectional", "component.peer_bidirectional_pin_unconnected"),
    ),
)
def test_directional_peer_checks_keep_their_existing_mixed_open_cases(
    electrical_type: str,
    existing_rule: str,
) -> None:
    report = lint_report(
        generic_component_peer_mixed_netlist(target_types=(electrical_type,) * 3),
        _review_policy(),
    )
    rule_ids = {item.rule_id for item in report.findings}
    assert RULE_ID not in rule_ids
    assert existing_rule in rule_ids


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_cross_symbol_part_id_peers_require_matching_identity() -> None:
    observed = generic_component_peer_mixed_netlist(
        symbols={
            "U1": "Synthetic:ModuleA",
            "U2": "Synthetic:ModuleA",
            "U3": "Synthetic:ModuleB",
        },
        part_ids={
            "U1": "SYNTHETIC-MODULE-001",
            "U2": "synthetic-module-001",
            "U3": "Synthetic-Module-001",
        },
    )
    report = lint_report(observed, _review_policy())
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert finding.evidence["peer_group_basis"] == ("part_id",)
    assert finding.evidence["peer_group_identity"] == ("SYNTHETIC-MODULE-001",)
    assert finding.evidence["peer_group_symbols"] == ("Synthetic:ModuleA", "Synthetic:ModuleB")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_cross_symbol_part_id_peer_metadata_must_match() -> None:
    symbols = {
        "U1": "Synthetic:ModuleA",
        "U2": "Synthetic:ModuleA",
        "U3": "Synthetic:ModuleB",
    }
    part_ids = {reference: "SYNTHETIC-MODULE-001" for reference in symbols}
    baseline = generic_component_peer_mixed_netlist(symbols=symbols, part_ids=part_ids)
    mismatched_function = baseline.model_copy(
        update={
            "pin_functions": {
                **baseline.pin_functions,
                "U3.2": "OUTPUT",
            }
        }
    )
    controls = (
        generic_component_peer_mixed_netlist(
            symbols=symbols,
            part_ids=part_ids,
            values={"U3": "Different module"},
        ),
        generic_component_peer_mixed_netlist(
            symbols=symbols,
            part_ids=part_ids,
            footprints={"U3": "Synthetic:DifferentFootprint"},
        ),
        mismatched_function,
        generic_component_peer_mixed_netlist(
            symbols=symbols,
            part_ids=part_ids,
            target_types=("passive", "passive", "open_collector"),
        ),
    )
    for observed in controls:
        report = lint_report(observed, _review_policy())
        assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_candidate() -> None:
    observed = generic_component_peer_mixed_netlist()
    finding = next(
        item for item in lint_report(observed, _review_policy()).findings if item.rule_id == RULE_ID
    )
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires review of generic peer pin gaps",
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
                    reason="Synthetic project disables the generic peer prompt",
                ),
            )
        ),
    )
    ignored = lint_report(
        observed,
        DesignLintPolicy(
            rules=_review_policy().rules,
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic component documentation confirms the open pin is unused",
                ),
            ),
        ),
    )
    assert blocked.status == "FAIL"
    assert disabled.status == "PASS"
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_stable_when_peer_netlist_input_order_changes() -> None:
    observed = generic_component_peer_mixed_netlist()
    original = lint_report(observed, _review_policy())
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
    repeated = lint_report(reordered, _review_policy())
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
def test_mixed_open_generic_peer_pin_fault_and_control_on_pinned_native_versions(
    tmp_path: Path,
) -> None:
    _run_native_peer_pin_assignment_lane("generic-mixed-open", tmp_path)
