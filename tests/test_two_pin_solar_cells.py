"""Synthetic regressions for same-net two-pin solar-cell review."""

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

RULE_ID = "component.two_pin_solar_cell_same_net"
SOLAR_CELL_SYMBOL = "Device:Solar_Cell"


def solar_cell_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    open_pins: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"BT1": SOLAR_CELL_SYMBOL}
    components = {
        reference: ComponentContract(value="Synthetic solar cell", footprint="Synthetic:Cell")
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
            nets[f"CELL_NODE_{reference}"] = (first,)
            continue
        if same_net:
            pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
            nets[f"CELL_NODE_{reference}"] = pins
        else:
            nets[f"CELL_POS_{reference}"] = (first,)
            nets[f"CELL_NEG_{reference}"] = (second,)
            if reference in multi_pin:
                nets[f"CELL_EXTRA_{reference}"] = (f"{reference}.3",)
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
        project_id="synthetic-two-pin-solar-cells",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_exact_solar_cell_is_reviewed_without_claiming_cell_behavior() -> None:
    observed = solar_cell_netlist()
    assert [
        (item.reference, item.kind, item.net) for item in two_pin_components_on_same_net(observed)
    ] == [("BT1", "solar_cell", "CELL_NODE_BT1")]

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "BT1: both solar-cell terminals share CELL_NODE_BT1"
    assert finding.evidence["symbol"] == (SOLAR_CELL_SYMBOL,)
    assert finding.evidence["pin_assignments"] == (
        "BT1.1 -> CELL_NODE_BT1",
        "BT1.2 -> CELL_NODE_BT1",
    )
    assert "does not establish cell output" in finding.message
    assert "component.two_pin_passive_same_net" not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_solar_cell_terminal_nets_are_the_no_finding_control() -> None:
    report = lint_report(solar_cell_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_skips_dnp_incomplete_ambiguous_open_multi_pin_and_other_symbols() -> None:
    observed = solar_cell_netlist(
        dnp=("BT_DNP",),
        omit_inventory=("BT_MISSING",),
        ambiguous=("BT_AMBIGUOUS",),
        open_pins=("BT_OPEN",),
        multi_pin=("BT_MULTIPIN",),
        symbols={
            "BT_DNP": SOLAR_CELL_SYMBOL,
            "BT_MISSING": SOLAR_CELL_SYMBOL,
            "BT_AMBIGUOUS": SOLAR_CELL_SYMBOL,
            "BT_OPEN": SOLAR_CELL_SYMBOL,
            "BT_MULTIPIN": SOLAR_CELL_SYMBOL,
            "BT_ALT": "Device:Solar_Cell_Module",
            "BT_CUSTOM": "Vendor:Solar_Cell",
        },
    )
    assert two_pin_components_on_same_net(observed) == ()
    assert RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_and_exact_fingerprint_ignore_are_project_configurable() -> None:
    observed = solar_cell_netlist()
    finding = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires disposition of same-net solar cells",
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
                    reason="Synthetic project does not use this review prompt",
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
                    reason="Synthetic reviewer accepts this intentional measurement short",
                ),
            )
        ),
    )
    assert next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    ).disposition == ("IGNORED")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_order_is_stable_and_splitting_one_solar_cell_clears_only_its_finding() -> None:
    source = solar_cell_netlist(symbols={"BT1": SOLAR_CELL_SYMBOL, "BT2": SOLAR_CELL_SYMBOL})
    original = lint_report(source)
    reversed_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = lint_report(reversed_source)
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == RULE_ID
    }
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == RULE_ID
    }
    assert len(original_findings) == 2
    assert reordered_findings == original_findings

    nets = dict(source.nets)
    nets.pop("CELL_NODE_BT1")
    nets["CELL_POS_BT1"] = ("BT1.1",)
    nets["CELL_NEG_BT1"] = ("BT1.2",)
    split = lint_report(source.model_copy(update={"nets": nets}))
    assert {item.subject for item in split.findings if item.rule_id == RULE_ID} == {
        "BT2: both solar-cell terminals share CELL_NODE_BT2"
    }
