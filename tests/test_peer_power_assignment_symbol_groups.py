"""Exact-symbol component peer power assignment regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.component_peer_power_assignment_support import RULE_ID, lint_report, peer_power_netlist

pytestmark = [pytest.mark.component_lint, pytest.mark.design_lint, pytest.mark.power_lint]


def test_exact_symbol_power_assignment_fault_and_valid_controls() -> None:
    same_symbol = {
        "U1": "Synthetic:PowerPeer",
        "U2": "Synthetic:PowerPeer",
    }
    fault = peer_power_netlist(symbols=same_symbol)

    report = lint_report(fault)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert len(findings) == 2
    assert {item.evidence["peer_role"][0] for item in findings} == {
        "ground/return",
        "supply",
    }
    return_finding = next(
        item for item in findings if item.evidence["peer_role"] == ("ground/return",)
    )
    assert return_finding.evidence["U1.2"] == ("GND",)
    assert return_finding.evidence["U2.2"] == ("AGND",)
    assert "intentionally separate" in return_finding.message

    controls = (
        peer_power_netlist(
            symbols=same_symbol,
            supply_nets=("+3V3", "+3V3"),
            return_nets=("GND", "GND"),
        ),
        peer_power_netlist(symbols=same_symbol, dnp=("U2",)),
        peer_power_netlist(symbols={"U1": "Synthetic:PowerPeer", "U2": "Synthetic:OtherPowerPeer"}),
    )
    for control in controls:
        assert RULE_ID not in {item.rule_id for item in lint_report(control).findings}

    open_return = peer_power_netlist(
        symbols=same_symbol,
        supply_nets=("+3V3", "+3V3"),
        return_nets=("GND", None),
    )
    open_findings = {item.rule_id for item in lint_report(open_return).findings}
    assert RULE_ID not in open_findings
    assert "component.unconnected_return_pin" in open_findings


def test_exact_symbol_power_assignment_obeys_policy_and_ignore_lifecycle() -> None:
    source = peer_power_netlist(
        symbols={"U1": "Synthetic:PowerPeer", "U2": "Synthetic:PowerPeer"},
        supply_nets=("+3V3", "+3V3"),
    )
    initial = lint_report(source)
    finding = next(item for item in initial.findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires reviewed peer return domains",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"
    assert blocked.findings[0].mode == "block"

    off = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic isolation control is explicitly reviewed",
                ),
            )
        ),
    )
    off_finding = next(item for item in off.findings if item.rule_id == RULE_ID)
    assert off_finding.disposition == "RULE_OFF"

    ignored_policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic return-domain isolation is intentional",
            ),
        )
    )
    ignored = lint_report(source, ignored_policy)
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"

    changed_source = source.model_copy(
        update={"nets": {"+3V3": ("U1.1", "U2.1"), "GND": ("U1.2",), "CHASSIS": ("U2.2",)}}
    )
    stale = lint_report(changed_source, ignored_policy)
    assert stale.status == "REVIEW"
    assert stale.stale_ignores == ignored_policy.ignores


def test_exact_symbol_power_assignment_is_stable_under_mapping_order() -> None:
    source = peer_power_netlist(symbols={"U1": "Synthetic:PowerPeer", "U2": "Synthetic:PowerPeer"})
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    findings = [item for item in lint_report(source).findings if item.rule_id == RULE_ID]
    reordered_findings = [
        item for item in lint_report(reordered).findings if item.rule_id == RULE_ID
    ]

    assert [(item.evidence, item.fingerprint) for item in reordered_findings] == [
        (item.evidence, item.fingerprint) for item in findings
    ]

    commoned = peer_power_netlist(
        symbols={"U1": "Synthetic:PowerPeer", "U2": "Synthetic:PowerPeer"},
        supply_nets=("+3V3", "+3V3"),
        return_nets=("GND", "GND"),
    )
    assert RULE_ID not in {item.rule_id for item in lint_report(commoned).findings}
