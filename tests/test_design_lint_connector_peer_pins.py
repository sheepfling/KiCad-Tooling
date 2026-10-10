"""Focused synthetic regressions for the connector peer pins lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach, peer_connector_pin_assignments

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
]


def test_exact_symbol_peer_pin_outlier_localizes_missing_generic_contact() -> None:
    source = peer_connector_pin_assignments()
    report = evaluate("synthetic-peer-pin-gap", coach(source), DesignLintPolicy())
    findings = [
        item for item in report.findings if item.rule_id == "connector.peer_pin_assignment_outlier"
    ]

    assert len(findings) == 1
    assert report.status == "REVIEW"
    finding = findings[0]
    assert finding.subject == "Synthetic:PeripheralPort pin 2"
    assert finding.evidence["J1.2"] == ("RETURN",)
    assert finding.evidence["J2.2"] == ("RETURN",)
    assert finding.evidence["J3.2"] == ()
    assert finding.evidence["outlier_pins"] == ("J3.2",)
    assert "do not prove that their nets must be common" in finding.message

    blocked = evaluate(
        "synthetic-peer-pin-gap",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.peer_pin_assignment_outlier",
                    mode="block",
                    reason="Synthetic project requires disposition of sibling pin gaps",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"
    assert blocked.findings[0].mode == "block"

    ignored = evaluate(
        "synthetic-peer-pin-gap",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id="connector.peer_pin_assignment_outlier",
                    fingerprint=finding.fingerprint,
                    reason="Synthetic review accepts the unconnected optional contact",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert ignored.findings[0].disposition == "IGNORED"

    disabled = evaluate(
        "synthetic-peer-pin-gap",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.peer_pin_assignment_outlier",
                    mode="off",
                    reason="Synthetic project reviewed the generic connector inventory",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    assert disabled.findings[0].disposition == "RULE_OFF"

    minority_net = evaluate(
        "synthetic-peer-pin-minority",
        coach(peer_connector_pin_assignments(("RETURN", "RETURN", "ISOLATED"))),
        DesignLintPolicy(),
    )
    minority = next(
        item
        for item in minority_net.findings
        if item.rule_id == "connector.peer_pin_assignment_outlier"
    )
    assert minority.evidence["outlier_pins"] == ("J3.2",)
    assert "connector.peer_pin_assignment_divergence" not in {
        item.rule_id for item in minority_net.findings
    }


def test_two_peer_open_generic_contact_prompts_and_supports_exact_ignore() -> None:
    source = peer_connector_pin_assignments(("+5V", None)).model_copy(
        update={
            "nets": {"+5V": ("J1.1",), "GND": ("J1.2", "J2.2")},
            "pin_functions": {
                "J1.1": "Pin_1",
                "J2.1": "Pin_1",
                "J1.2": "GND",
                "J2.2": "GND",
            },
        }
    )
    report = evaluate("synthetic-two-peer-open-power-contact", coach(source), DesignLintPolicy())
    findings = [
        item for item in report.findings if item.rule_id == "connector.peer_pin_assignment_outlier"
    ]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "Synthetic:PeripheralPort pin 1"
    assert finding.evidence["J1.1"] == ("+5V",)
    assert finding.evidence["J2.1"] == ()
    assert finding.evidence["outlier_pins"] == ("J2.1",)
    assert "do not prove that their nets must be common" in finding.message

    tied_control = source.model_copy(
        update={"nets": {"+5V": ("J1.1", "J2.1"), "GND": ("J1.2", "J2.2")}}
    )
    control_report = evaluate(
        "synthetic-two-peer-common-power-contact", coach(tied_control), DesignLintPolicy()
    )
    assert control_report.status == "PASS"
    assert "connector.peer_pin_assignment_outlier" not in {
        item.rule_id for item in control_report.findings
    }

    ignored = evaluate(
        "synthetic-two-peer-open-power-contact",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id="connector.peer_pin_assignment_outlier",
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project reviewed this optional contact as intentionally open",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert ignored.findings[0].disposition == "IGNORED"


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            peer_connector_pin_assignments(("RETURN", "RETURN", "RETURN")), id="consistent"
        ),
        pytest.param(
            peer_connector_pin_assignments(("PORT_A", "PORT_B", "PORT_C")), id="independent"
        ),
        pytest.param(peer_connector_pin_assignments(dnp=("J3",)), id="dnp-peer"),
    ],
)
def test_exact_symbol_peer_pin_controls_exclude_consistent_independent_and_dnp_cases(
    source: NetlistContract,
) -> None:
    report = evaluate("synthetic-peer-pin-control", coach(source), DesignLintPolicy())

    assert "connector.peer_pin_assignment_outlier" not in {item.rule_id for item in report.findings}


def test_exact_symbol_peer_pin_named_functions_are_handled_by_named_rule() -> None:
    named = peer_connector_pin_assignments().model_copy(
        update={
            "pin_functions": {
                "J1.2": "GND",
                "J2.2": "GND",
                "J3.2": "GND",
            }
        }
    )
    report = evaluate("synthetic-peer-pin-named-control", coach(named), DesignLintPolicy())

    assert "connector.peer_pin_assignment_outlier" not in {item.rule_id for item in report.findings}


def test_generic_connector_outlier_order_is_stable_and_completion_clears_it() -> None:
    source = peer_connector_pin_assignments()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    original_report = evaluate("synthetic-peer-pin-gap", coach(source), DesignLintPolicy())
    reordered_report = evaluate("synthetic-peer-pin-gap", coach(reordered), DesignLintPolicy())
    original_finding = next(
        item
        for item in original_report.findings
        if item.rule_id == "connector.peer_pin_assignment_outlier"
    )
    reordered_finding = next(
        item
        for item in reordered_report.findings
        if item.rule_id == "connector.peer_pin_assignment_outlier"
    )

    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        original_finding.fingerprint,
        original_finding.evidence,
    )

    completed = evaluate(
        "synthetic-peer-pin-complete",
        coach(peer_connector_pin_assignments(("RETURN", "RETURN", "RETURN"))),
        DesignLintPolicy(),
    )
    assert "connector.peer_pin_assignment_outlier" not in {
        item.rule_id for item in completed.findings
    }


def test_exact_symbol_peer_pin_divergence_reviews_conflicting_generic_assignments() -> None:
    source = peer_connector_pin_assignments(("PORT_A", "PORT_B"))
    report = evaluate("synthetic-peer-pin-divergence", coach(source), DesignLintPolicy())
    findings = [
        item
        for item in report.findings
        if item.rule_id == "connector.peer_pin_assignment_divergence"
    ]

    assert len(findings) == 1
    assert report.status == "REVIEW"
    finding = findings[0]
    assert finding.subject == "Synthetic:PeripheralPort pin 2"
    assert finding.evidence["J1.2"] == ("PORT_A",)
    assert finding.evidence["J2.2"] == ("PORT_B",)
    assert finding.evidence["missing_pin_function_pins"] == ("J1.2", "J2.2")
    assert "does not establish a required connection" in finding.message

    blocked = evaluate(
        "synthetic-peer-pin-divergence",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.peer_pin_assignment_divergence",
                    mode="block",
                    reason="Synthetic project requires review of generic peer pin maps",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    ignored = evaluate(
        "synthetic-peer-pin-divergence",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic peer contacts are intentionally independent",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert ignored.findings[0].disposition == "IGNORED"

    disabled = evaluate(
        "synthetic-peer-pin-divergence",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="connector.peer_pin_assignment_divergence",
                    mode="off",
                    reason="Synthetic project reviewed these peer contacts elsewhere",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    assert disabled.findings[0].disposition == "RULE_OFF"


def test_generic_pin_function_placeholder_divergence_remains_reviewable() -> None:
    source = peer_connector_pin_assignments(("PORT_A", "PORT_B")).model_copy(
        update={"pin_functions": {"J1.2": "Pin_2", "J2.2": "Pin_2"}}
    )
    report = evaluate(
        "synthetic-generic-pin-placeholder-divergence", coach(source), DesignLintPolicy()
    )

    assert {item.rule_id for item in report.findings} == {
        "connector.peer_pin_assignment_divergence"
    }
    finding = report.findings[0]
    assert finding.evidence["missing_pin_function_pins"] == ("J1.2", "J2.2")
    assert "generic Pin_N placeholder is treated as unknown" in finding.message


def test_generic_pin_function_placeholder_outlier_uses_unique_majority() -> None:
    source = peer_connector_pin_assignments(("PORT_A", "PORT_A", "PORT_B")).model_copy(
        update={
            "pin_functions": {
                "J1.2": "Pin_2",
                "J2.2": "Pin_2",
                "J3.2": "Pin_2",
            }
        }
    )
    report = evaluate(
        "synthetic-generic-pin-placeholder-outlier", coach(source), DesignLintPolicy()
    )

    assert {item.rule_id for item in report.findings} == {"connector.peer_pin_assignment_outlier"}
    assert report.findings[0].evidence["outlier_pins"] == ("J3.2",)


def test_generic_pin_function_placeholder_common_assignment_is_a_control() -> None:
    source = peer_connector_pin_assignments(("PORT_A", "PORT_A", "PORT_A")).model_copy(
        update={
            "pin_functions": {
                "J1.2": "Pin_2",
                "J2.2": "Pin_2",
                "J3.2": "Pin_2",
            }
        }
    )
    report = evaluate(
        "synthetic-generic-pin-placeholder-control", coach(source), DesignLintPolicy()
    )

    assert not report.findings


def test_peer_pin_divergence_order_is_stable_and_agreement_clears_it() -> None:
    source = peer_connector_pin_assignments(("PORT_A", "PORT_B"))
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    original_report = evaluate("synthetic-peer-pin-divergence", coach(source), DesignLintPolicy())
    reordered_report = evaluate(
        "synthetic-peer-pin-divergence", coach(reordered), DesignLintPolicy()
    )
    original_finding = next(
        item
        for item in original_report.findings
        if item.rule_id == "connector.peer_pin_assignment_divergence"
    )
    reordered_finding = next(
        item
        for item in reordered_report.findings
        if item.rule_id == "connector.peer_pin_assignment_divergence"
    )

    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        original_finding.fingerprint,
        original_finding.evidence,
    )

    agreed = evaluate(
        "synthetic-peer-pin-agreed",
        coach(peer_connector_pin_assignments(("PORT_A", "PORT_A"))),
        DesignLintPolicy(),
    )
    assert "connector.peer_pin_assignment_divergence" not in {
        item.rule_id for item in agreed.findings
    }


def test_peer_pin_tie_uses_divergence_without_arbitrary_outlier() -> None:
    source = peer_connector_pin_assignments(("PORT_A", "PORT_A", "PORT_B", "PORT_B"))
    report = evaluate("synthetic-peer-pin-tie", coach(source), DesignLintPolicy())
    rule_ids = {item.rule_id for item in report.findings}

    assert "connector.peer_pin_assignment_outlier" not in rule_ids
    assert "connector.peer_pin_assignment_divergence" in rule_ids
    finding = next(
        item
        for item in report.findings
        if item.rule_id == "connector.peer_pin_assignment_divergence"
    )
    assert finding.evidence["J1.2"] == ("PORT_A",)
    assert finding.evidence["J2.2"] == ("PORT_A",)
    assert finding.evidence["J3.2"] == ("PORT_B",)
    assert finding.evidence["J4.2"] == ("PORT_B",)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(peer_connector_pin_assignments(("PORT_A", "PORT_A")), id="agreement"),
        pytest.param(
            peer_connector_pin_assignments(("PORT_A", "PORT_B"), dnp=("J2",)), id="dnp-peer"
        ),
    ],
)
def test_peer_pin_divergence_requires_conflict_and_fitted_peers(source: NetlistContract) -> None:
    report = evaluate("synthetic-peer-pin-divergence-control", coach(source), DesignLintPolicy())

    assert "connector.peer_pin_assignment_divergence" not in {
        item.rule_id for item in report.findings
    }


def test_peer_pin_divergence_requires_missing_function_metadata() -> None:
    named = peer_connector_pin_assignments(("PORT_A", "PORT_B")).model_copy(
        update={"pin_functions": {"J1.2": "GND", "J2.2": "GND"}}
    )
    named_report = evaluate("synthetic-peer-pin-named-divergence", coach(named), DesignLintPolicy())
    assert "connector.peer_pin_assignment_divergence" not in {
        item.rule_id for item in named_report.findings
    }

    partially_named = peer_connector_pin_assignments(("PORT_A", "PORT_B", "PORT_C")).model_copy(
        update={"pin_functions": {"J1.2": "GND", "J2.2": "GND"}}
    )
    partial_report = evaluate(
        "synthetic-peer-pin-partial-metadata",
        coach(partially_named),
        DesignLintPolicy(),
    )
    assert "connector.peer_pin_assignment_divergence" not in {
        item.rule_id for item in partial_report.findings
    }
    assert "connector.repeated_pin_function" in {item.rule_id for item in partial_report.findings}
