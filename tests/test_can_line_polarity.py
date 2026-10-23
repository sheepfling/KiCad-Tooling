"""Focused CAN line pin and net-label polarity lint regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import can_netlist, coach

RULE_ID = "bus.can_line_polarity_label_mismatch"

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _reversed_can_netlist() -> NetlistContract:
    source = can_netlist("121R")
    return source.model_copy(
        update={
            "nets": {
                "CAN_HIGH": ("U1.2", "R1.1"),
                "CAN_LOW": ("U1.1", "R1.2"),
            }
        }
    )


def _polarity_findings(netlist: NetlistContract):
    return tuple(item for item in candidates(netlist) if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_crossed_can_lines_are_flagged_while_the_complete_pair_and_termination_stay_valid() -> None:
    report = evaluate("synthetic-can-polarity", coach(_reversed_can_netlist()), DesignLintPolicy())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert tuple(item.subject for item in findings) == (
        "U1.1: CANH on CAN_LOW",
        "U1.2: CAN_L on CAN_HIGH",
    )
    assert findings[0].evidence["pin_role"] == ("CANH",)
    assert findings[0].evidence["net_role"] == ("CANL",)
    assert findings[1].evidence["pin_role"] == ("CANL",)
    assert findings[1].evidence["net_role"] == ("CANH",)
    assert report.status == "REVIEW"
    assert not any(
        item.rule_id in {"bus.complementary_pair_assignment", "bus.can_missing_termination"}
        for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_recognized_names_match_and_neutral_or_unbounded_names_stay_unclassified() -> None:
    source = can_netlist("121R")
    matching_aliases = source.model_copy(
        update={"nets": {"CANH": source.nets["CAN_HIGH"], "CANL": source.nets["CAN_LOW"]}}
    )
    neutral = source.model_copy(
        update={"nets": {"NET_A": source.nets["CAN_HIGH"], "NET_B": source.nets["CAN_LOW"]}}
    )
    indexed = source.model_copy(
        update={"nets": {"CAN1_H": source.nets["CAN_HIGH"], "CAN1_L": source.nets["CAN_LOW"]}}
    )
    unknown_pin_function = source.model_copy(
        update={"pin_functions": {**source.pin_functions, "U1.1": "TXD"}}
    )

    assert not _polarity_findings(source)
    assert not _polarity_findings(matching_aliases)
    assert not _polarity_findings(neutral)
    assert not _polarity_findings(indexed)
    assert not _polarity_findings(unknown_pin_function)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_multiply_assigned_and_same_symbol_short_boundaries_are_not_duplicated() -> None:
    source = _reversed_can_netlist()
    dnp = source.model_copy(update={"dnp_components": ("U1",)})
    open_pin = can_netlist("121R").model_copy(
        update={"nets": {"CAN_HIGH": ("R1.1",), "CAN_LOW": ("U1.2", "R1.2")}}
    )
    multiply_assigned = can_netlist("121R").model_copy(
        update={
            "nets": {
                "CAN_HIGH": ("U1.1", "R1.1"),
                "CAN_LOW": ("U1.2", "R1.2"),
                "AUX": ("U1.1",),
            }
        }
    )
    shorted_pair = can_netlist("121R").model_copy(
        update={"nets": {"CAN_HIGH": ("R1.1",), "CAN_LOW": ("U1.1", "U1.2", "R1.2")}}
    )

    assert not _polarity_findings(dnp)
    assert not _polarity_findings(open_pin)
    assert not _polarity_findings(multiply_assigned)
    assert not _polarity_findings(shorted_pair)
    assert any(
        item.rule_id == "bus.complementary_pair_assignment" for item in candidates(shorted_pair)
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_block_off_and_exact_ignore_policy_are_supported() -> None:
    source = _reversed_can_netlist()
    review = evaluate("synthetic-can-polarity", coach(source), DesignLintPolicy())
    finding = next(item for item in review.findings if item.rule_id == RULE_ID)

    blocked = evaluate(
        "synthetic-can-polarity",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed map"),)
        ),
    )
    assert blocked.status == "FAIL"
    assert all(item.mode == "block" for item in blocked.findings if item.rule_id == RULE_ID)

    disabled = evaluate(
        "synthetic-can-polarity",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Intentional map"),)
        ),
    )
    assert all(
        item.disposition == "RULE_OFF" for item in disabled.findings if item.rule_id == RULE_ID
    )

    ignored = evaluate(
        "synthetic-can-polarity",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Reviewed CAN pin map",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_netlist_reordering_is_stable_and_corrected_line_assignments_clear() -> None:
    source = _reversed_can_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    expected = _polarity_findings(source)
    actual = _polarity_findings(reordered)

    assert actual == expected
    assert not _polarity_findings(can_netlist("121R"))
