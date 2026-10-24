"""Synthetic regressions for same-net two-pin battery review."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.two_pin_components import two_pin_components_on_same_net

pytestmark = [pytest.mark.component_lint, pytest.mark.design_lint]

RULE_ID = "component.two_pin_battery_same_net"


def battery_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    open_pins: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"BT1": "Device:Battery"}
    components = {
        reference: ComponentContract(value="Synthetic source", footprint="Synthetic:Battery")
        for reference in symbols
    }
    pin_numbers = {
        reference: ("1", "2", "3") if reference in multi_pin else ("1", "2")
        for reference in symbols
        if reference not in omit_inventory
    }
    nets: dict[str, tuple[str, ...]] = {}
    for reference in symbols:
        if reference in dnp or reference in omit_inventory:
            continue
        first = f"{reference}.1"
        second = f"{reference}.2"
        if reference in open_pins:
            nets[f"BATTERY_NODE_{reference}"] = (first,)
            continue
        if same_net:
            pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
            nets[f"BATTERY_NODE_{reference}"] = pins
        else:
            nets[f"BATTERY_POS_{reference}"] = (first,)
            nets[f"BATTERY_NEG_{reference}"] = (second,)
            if reference in multi_pin:
                nets[f"BATTERY_EXTRA_{reference}"] = (f"{reference}.3",)
        if reference in ambiguous:
            nets[f"ALSO_{reference}"] = (second,)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def lint_report(observed: NetlistContract, policy: DesignLintPolicy | None = None) -> object:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-batteries",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_exact_battery_is_reviewed_without_assuming_source_behavior() -> None:
    observed = battery_netlist()
    assert [
        (item.reference, item.kind, item.net) for item in two_pin_components_on_same_net(observed)
    ] == [("BT1", "battery", "BATTERY_NODE_BT1")]

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert "component.two_pin_passive_same_net" not in {item.rule_id for item in report.findings}
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "BT1: both battery terminals share BATTERY_NODE_BT1"
    assert finding.evidence["symbol"] == ("Device:Battery",)
    assert finding.evidence["pin_assignments"] == (
        "BT1.1 -> BATTERY_NODE_BT1",
        "BT1.2 -> BATTERY_NODE_BT1",
    )
    assert "does not establish source behavior" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_battery_terminal_nets_are_the_no_finding_control() -> None:
    report = lint_report(battery_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_skips_dnp_incomplete_ambiguous_open_multi_pin_and_unconfirmed_symbols() -> None:
    observed = battery_netlist(
        dnp=("BT_DNP",),
        omit_inventory=("BT_MISSING",),
        ambiguous=("BT_AMBIGUOUS",),
        open_pins=("BT_OPEN",),
        multi_pin=("BT_MULTIPIN",),
        symbols={
            "BT_DNP": "Device:Battery",
            "BT_MISSING": "Device:Battery",
            "BT_AMBIGUOUS": "Device:Battery",
            "BT_OPEN": "Device:Battery",
            "BT_MULTIPIN": "Device:Battery",
            "BT_CELL": "Device:Battery_Cell",
            "BT_CUSTOM": "Vendor:Battery",
        },
    )
    assert two_pin_components_on_same_net(observed) == ()
    report = lint_report(observed)
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_and_exact_fingerprint_ignore_are_configurable() -> None:
    observed = battery_netlist()
    finding = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires a disposition for tied battery terminals",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

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
    assert disabled.status == "PASS"
    assert next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition == (
        "RULE_OFF"
    )

    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic reviewer accepts this explicit bypass",
                ),
            )
        ),
    )
    assert next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    ).disposition == ("IGNORED")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_order_is_stable_and_splitting_the_battery_clears_its_finding() -> None:
    observed = battery_netlist(symbols={"BT2": "Device:Battery", "BT1": "Device:Battery"})
    forward = lint_report(observed)
    reordered = NetlistContract(
        components=dict(reversed(tuple(observed.components.items()))),
        nets=dict(reversed(tuple(observed.nets.items()))),
        dnp_components=observed.dnp_components,
        component_symbols=dict(reversed(tuple(observed.component_symbols.items()))),
        component_pin_numbers=dict(reversed(tuple(observed.component_pin_numbers.items()))),
    )
    reverse = lint_report(reordered)
    forward_findings = [item for item in forward.findings if item.rule_id == RULE_ID]
    reverse_findings = [item for item in reverse.findings if item.rule_id == RULE_ID]
    assert [(item.subject, item.fingerprint) for item in forward_findings] == [
        (item.subject, item.fingerprint) for item in reverse_findings
    ]
    repaired = lint_report(battery_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in repaired.findings}
