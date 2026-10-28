"""Synthetic regressions for same-net two-pin thermocouple review."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

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

RULE_ID = "component.two_pin_thermocouple_same_net"
THERMOCOUPLE_SYMBOLS = (
    "Device:Thermocouple",
    "Device:Thermocouple_Alt",
    "Device:Thermocouple_Block",
)


def thermocouple_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    open_pins: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    symbols: Mapping[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or dict(zip(("TC1", "TC2", "TC3"), THERMOCOUPLE_SYMBOLS, strict=True))
    components = {
        reference: ComponentContract(
            value="Synthetic thermocouple", footprint="Synthetic:Thermocouple"
        )
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
            nets[f"TC_OPEN_{reference}"] = (first,)
            continue
        if same_net:
            pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
            nets[f"TC_TIED_{reference}"] = pins
        else:
            nets[f"TC_PLUS_{reference}"] = (first,)
            nets[f"TC_MINUS_{reference}"] = (second,)
            if reference in multi_pin:
                nets[f"TC_EXTRA_{reference}"] = (f"{reference}.3",)
        if reference in ambiguous:
            nets[f"TC_ALSO_{reference}"] = (second,)
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
        project_id="synthetic-two-pin-thermocouples",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_exact_thermocouples_are_reviewed_without_claiming_sensor_operation() -> None:
    observed = thermocouple_netlist()
    candidates = two_pin_components_on_same_net(observed)
    assert [(item.reference, item.kind, item.net) for item in candidates] == [
        ("TC1", "thermocouple", "TC_TIED_TC1"),
        ("TC2", "thermocouple", "TC_TIED_TC2"),
        ("TC3", "thermocouple", "TC_TIED_TC3"),
    ]

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 3
    first = findings[0]
    assert first.mode == "review"
    assert first.subject == "TC1: both thermocouple leads share TC_TIED_TC1"
    assert first.evidence["symbol"] == ("Device:Thermocouple",)
    assert first.evidence["pin_assignments"] == (
        "TC1.1 -> TC_TIED_TC1",
        "TC1.2 -> TC_TIED_TC1",
    )
    assert "does not establish temperature measurement" in first.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_thermocouple_lead_nets_are_the_no_finding_control() -> None:
    report = lint_report(thermocouple_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_skips_dnp_incomplete_ambiguous_open_multi_pin_and_unconfirmed_symbols() -> None:
    observed = thermocouple_netlist(
        dnp=("TC_DNP",),
        omit_inventory=("TC_MISSING",),
        ambiguous=("TC_AMBIGUOUS",),
        open_pins=("TC_OPEN",),
        multi_pin=("TC_MULTIPIN",),
        symbols={
            "TC_DNP": THERMOCOUPLE_SYMBOLS[0],
            "TC_MISSING": THERMOCOUPLE_SYMBOLS[0],
            "TC_AMBIGUOUS": THERMOCOUPLE_SYMBOLS[1],
            "TC_OPEN": THERMOCOUPLE_SYMBOLS[1],
            "TC_MULTIPIN": THERMOCOUPLE_SYMBOLS[2],
            "TC_ALT_UNCONFIRMED": "Device:Thermocouple_3Wire",
            "TC_CUSTOM": "Vendor:Thermocouple",
        },
    )
    assert two_pin_components_on_same_net(observed) == ()
    assert RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_and_exact_fingerprint_ignore_are_project_configurable() -> None:
    observed = thermocouple_netlist()
    finding = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires a disposition for tied thermocouple leads",
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
                    reason="Synthetic reviewer accepts this intentional sensor test setup",
                ),
            )
        ),
    )
    assert (
        next(
            item for item in ignored.findings if item.fingerprint == finding.fingerprint
        ).disposition
        == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_order_is_stable_and_splitting_one_sensor_clears_only_its_finding() -> None:
    source = thermocouple_netlist()
    original = lint_report(source)
    reordered = lint_report(
        source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
    )
    originals = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == RULE_ID
    }
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == RULE_ID
    }
    assert len(originals) == 3
    assert reordered_findings == originals

    nets = dict(source.nets)
    nets.pop("TC_TIED_TC1")
    nets["TC_PLUS_TC1"] = ("TC1.1",)
    nets["TC_MINUS_TC1"] = ("TC1.2",)
    split = lint_report(source.model_copy(update={"nets": nets}))
    assert {item.subject for item in split.findings if item.rule_id == RULE_ID} == {
        "TC2: both thermocouple leads share TC_TIED_TC2",
        "TC3: both thermocouple leads share TC_TIED_TC3",
    }
