"""Synthetic regressions for exact two-pin thermistor symbol support."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
)
from kicad_tooling.hwrepo.two_pin_passives import two_pin_passives_on_same_net

pytestmark = [pytest.mark.component_lint, pytest.mark.design_lint]
RULE_ID = "component.two_pin_passive_same_net"
SUPPORTED_SYMBOLS = (
    "Device:Thermistor",
    "Device:Thermistor_NTC",
    "Device:Thermistor_PTC",
    "Device:Thermistor_US",
    "Device:Thermistor_NTC_US",
    "Device:Thermistor_PTC_US",
)


def thermistor_netlist(
    *,
    symbol: str = "Device:Thermistor_NTC",
    same_net: bool = True,
    dnp: bool = False,
) -> NetlistContract:
    if dnp:
        nets = {}
    elif same_net:
        nets = {"SHORT_TH1": ("TH1.1", "TH1.2")}
    else:
        nets = {"SENSE_A": ("TH1.1",), "SENSE_B": ("TH1.2",)}
    value = {
        "Device:Thermistor": "10k",
        "Device:Thermistor_PTC": "10k PTC",
        "Device:Thermistor_US": "10k",
        "Device:Thermistor_PTC_US": "10k PTC",
    }.get(symbol, "10k NTC")
    return NetlistContract(
        components={"TH1": ComponentContract(value=value, footprint="Synthetic:Thermistor")},
        nets=nets,
        dnp_components=("TH1",) if dnp else (),
        component_symbols={"TH1": symbol},
        component_pin_numbers={"TH1": ("1", "2")},
    )


def lint_report(observed: NetlistContract) -> object:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-thermistor",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "symbol", SUPPORTED_SYMBOLS, ids=lambda symbol: symbol.removeprefix("Device:")
)
def test_detects_exact_supported_thermistors_on_one_net(symbol: str) -> None:
    observed = thermistor_netlist(symbol=symbol)
    candidates = two_pin_passives_on_same_net(observed)
    assert [(item.reference, item.kind, item.symbol) for item in candidates] == [
        ("TH1", "thermistor", symbol)
    ]

    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert finding.evidence["symbol"] == (symbol,)
    assert finding.evidence["passive_kind"] == ("thermistor",)
    assert finding.evidence["pin_assignments"] == (
        "TH1.1 -> SHORT_TH1",
        "TH1.2 -> SHORT_TH1",
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "symbol", SUPPORTED_SYMBOLS, ids=lambda symbol: symbol.removeprefix("Device:")
)
def test_distinct_net_and_dnp_controls_stay_quiet(symbol: str) -> None:
    distinct = lint_report(thermistor_netlist(symbol=symbol, same_net=False))
    dnp = lint_report(thermistor_netlist(symbol=symbol, dnp=True))
    assert RULE_ID not in {item.rule_id for item in distinct.findings}
    assert RULE_ID not in {item.rule_id for item in dnp.findings}
    assert distinct.status == dnp.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_skips_unconfirmed_thermistor_variants_and_case_drift() -> None:
    for symbol in (
        "Device:Thermistor_NTC_3wire",
        "Device:Thermistor_NTC_4wire",
        "Device:Thermistor_PTC_3wire",
        "Device:Thermistor_PTC_4wire",
        "Device:thermistor",
        "Synthetic:Thermistor",
    ):
        assert not two_pin_passives_on_same_net(thermistor_netlist(symbol=symbol))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "symbol", SUPPORTED_SYMBOLS, ids=lambda symbol: symbol.removeprefix("Device:")
)
def test_thermistor_finding_is_order_stable_and_a_split_clears_it(symbol: str) -> None:
    source = thermistor_netlist(symbol=symbol)
    original = lint_report(source)
    reordered_source = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    reordered = lint_report(reordered_source)
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == RULE_ID
    }
    assert len(original_findings) == 1
    assert {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == RULE_ID
    } == original_findings

    split = source.model_copy(update={"nets": {"SENSE_A": ("TH1.1",), "SENSE_B": ("TH1.2",)}})
    assert RULE_ID not in {item.rule_id for item in lint_report(split).findings}
