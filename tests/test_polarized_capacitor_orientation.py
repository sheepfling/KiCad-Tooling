"""Deterministic review cases for reversed polarized-capacitor terminals."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.models import ContractCoachReport, DesignLintPolicy
from tests.design_lint_fixtures.polarized_capacitor import netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.polarized_capacitor_reversed_on_named_rails"
PROJECT_ID = "synthetic-polarized-capacitor-orientation"


def lint(observed, *, mode: str | None = None, ignores=()):
    rules = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic polarized-capacitor project policy",
            ),
        )
    )
    return evaluate(
        PROJECT_ID,
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=PROJECT_ID,
            observed=observed,
            netlist_sha256="a" * 64,
        ),
        DesignLintPolicy(rules=rules, ignores=tuple(ignores)),
    )


def polarity_findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "symbol",
    (
        "Device:C_Polarized",
        "Device:C_Polarized_Small",
        "Device:C_Polarized_US",
        "Device:C_Polarized_Small_US",
    ),
)
def test_supported_polarized_symbol_with_lower_positive_terminal_is_reviewed(
    symbol: str,
) -> None:
    report = lint(netlist(symbol=symbol))

    assert report.status == "REVIEW"
    assert len(polarity_findings(report)) == 1
    finding = polarity_findings(report)[0]
    assert finding.subject == "C1: polarized capacitor pin 1 is below pin 2"
    assert finding.evidence["positive_terminal_pin"] == ("C1.1",)
    assert finding.evidence["negative_terminal_pin"] == ("C1.2",)
    assert finding.evidence["positive_terminal_net"] == ("-5V",)
    assert finding.evidence["negative_terminal_net"] == ("+5V",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("positive_terminal_net", "negative_terminal_net"),
    (
        pytest.param("+3V3", "+5V", id="lower-positive-rail"),
        pytest.param("-12V", "-5V", id="more-negative-rail"),
        pytest.param("-5V", "GND", id="negative-rail-below-return"),
    ),
)
def test_numeric_and_return_reversals_have_ordered_evidence(
    positive_terminal_net: str,
    negative_terminal_net: str,
) -> None:
    report = lint(
        netlist(
            positive_terminal_net=positive_terminal_net,
            negative_terminal_net=negative_terminal_net,
        )
    )

    assert len(polarity_findings(report)) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("positive_terminal_net", "negative_terminal_net", "positive_peer", "negative_peer"),
    (
        pytest.param("+5V", "GND", None, None, id="positive-supply-to-return"),
        pytest.param("GND", "-5V", None, None, id="return-to-negative-supply"),
        pytest.param("+5V", "-5V", None, None, id="positive-to-negative-rail"),
        pytest.param("VCC", "GND", "VCC", None, id="symbolic-positive-to-return"),
        pytest.param("VCC", "VDD", "VCC", "VDD", id="unordered-positive-rails"),
        pytest.param("BATTERY", "SENSE", None, None, id="unknown-rails"),
        pytest.param("+5V", "GND", "GND", None, id="numeric-and-return-conflict"),
        pytest.param("+5V", "GND", "GND", "VCC", id="both-roles-conflict"),
    ),
)
def test_correct_unknown_or_conflicting_rail_evidence_is_not_a_finding(
    positive_terminal_net: str,
    negative_terminal_net: str,
    positive_peer: str | None,
    negative_peer: str | None,
) -> None:
    report = lint(
        netlist(
            positive_terminal_net=positive_terminal_net,
            negative_terminal_net=negative_terminal_net,
            positive_peer_function=positive_peer,
            negative_peer_function=negative_peer,
        )
    )

    assert not polarity_findings(report)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("symbol", "inventory", "dnp"),
    (
        pytest.param("Device:C", ("1", "2"), (), id="unpolarized-symbol"),
        pytest.param("Synthetic:Electrolytic", ("1", "2"), (), id="unknown-symbol"),
        pytest.param("Device:C_Polarized", ("1",), (), id="incomplete-inventory"),
        pytest.param("Device:C_Polarized", ("1", "2", "2"), (), id="duplicate-pin"),
        pytest.param("Device:C_Polarized", ("1", "2"), ("C1",), id="dnp-capacitor"),
    ),
)
def test_unsupported_identity_or_incomplete_component_is_not_a_finding(
    symbol: str,
    inventory: tuple[str, ...],
    dnp: tuple[str, ...],
) -> None:
    assert not polarity_findings(lint(netlist(symbol=symbol, inventory=inventory, dnp=dnp)))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "nets",
    (
        pytest.param({"-5V": ("U1.1",), "+5V": ("C1.2",)}, id="positive-pin-open"),
        pytest.param({"-5V": ("C1.1",), "+5V": ("U1.1",)}, id="negative-pin-open"),
        pytest.param(
            {"-5V": ("C1.1",), "+5V": ("C1.2",), "OTHER": ("C1.1",)},
            id="ambiguous-positive-pin",
        ),
        pytest.param({"-5V": ("C1.1", "C1.2")}, id="same-net"),
    ),
)
def test_missing_ambiguous_or_same_net_assignments_are_not_findings(
    nets: Mapping[str, tuple[str, ...]],
) -> None:
    assert not polarity_findings(lint(netlist().model_copy(update={"nets": nets})))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_supports_project_policy_modes_and_exact_ignore() -> None:
    source = netlist()
    finding = polarity_findings(lint(source))[0]
    blocked = lint(source, mode="block")
    disabled = lint(source, mode="off")
    ignored = lint(
        source,
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic reviewed exception",
            ),
        ),
    )

    assert blocked.status == "FAIL"
    assert len(polarity_findings(disabled)) == 1
    assert polarity_findings(disabled)[0].disposition == "RULE_OFF"
    assert ignored.status == "PASS"
    assert polarity_findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rail_assignment_correction_and_net_ordering_are_deterministic() -> None:
    fault = netlist()
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    corrected = netlist(positive_terminal_net="+5V", negative_terminal_net="-5V")
    baseline_finding = polarity_findings(lint(fault))[0]
    reordered_finding = polarity_findings(lint(reordered))[0]

    assert (baseline_finding.fingerprint, baseline_finding.evidence) == (
        reordered_finding.fingerprint,
        reordered_finding.evidence,
    )
    assert not polarity_findings(lint(corrected))
