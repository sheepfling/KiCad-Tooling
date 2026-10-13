"""Synthetic regressions for supported two-pin varistor topology."""

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


def varistor_netlist(
    *,
    symbol: str = "Device:Varistor",
    same_net: bool = True,
    dnp: bool = False,
) -> NetlistContract:
    if dnp:
        nets = {}
    elif same_net:
        nets = {"SHORT_RV1": ("RV1.1", "RV1.2")}
    else:
        nets = {"INPUT": ("RV1.1",), "OUTPUT": ("RV1.2",)}
    return NetlistContract(
        components={"RV1": ComponentContract(value="230V MOV", footprint="Synthetic:Varistor_RV")},
        nets=nets,
        dnp_components=("RV1",) if dnp else (),
        component_symbols={"RV1": symbol},
        component_pin_numbers={"RV1": ("1", "2")},
    )


def lint_report(observed: NetlistContract) -> object:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-varistor",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("symbol", ("Device:Varistor", "Device:Varistor_US"))
def test_detects_supported_varistor_families_on_one_net(symbol: str) -> None:
    observed = varistor_netlist(symbol=symbol)
    candidates = two_pin_passives_on_same_net(observed)
    assert [(item.reference, item.kind, item.symbol) for item in candidates] == [
        ("RV1", "varistor", symbol)
    ]

    report = lint_report(observed)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert finding.subject == "RV1 (230V MOV varistor) has both pins on one net"
    assert finding.evidence["symbol"] == (symbol,)
    assert finding.evidence["pin_assignments"] == (
        "RV1.1 -> SHORT_RV1",
        "RV1.2 -> SHORT_RV1",
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_varistor_distinct_net_and_dnp_controls_stay_quiet() -> None:
    distinct = lint_report(varistor_netlist(same_net=False))
    dnp = lint_report(varistor_netlist(dnp=True))
    assert RULE_ID not in {item.rule_id for item in distinct.findings}
    assert RULE_ID not in {item.rule_id for item in dnp.findings}
    assert distinct.status == dnp.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_skips_dnp_and_unrecognized_varistor_identities() -> None:
    assert not two_pin_passives_on_same_net(varistor_netlist(dnp=True))
    for symbol in (
        "Device:Varistor_Custom",
        "Synthetic:Varistor",
        "Device:varistor",
        "Device:Varistor_us",
    ):
        assert not two_pin_passives_on_same_net(varistor_netlist(symbol=symbol))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_varistor_finding_is_order_stable_and_a_split_clears_it() -> None:
    source = varistor_netlist()
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

    split = source.model_copy(update={"nets": {"INPUT": ("RV1.1",), "OUTPUT": ("RV1.2",)}})
    assert RULE_ID not in {item.rule_id for item in lint_report(split).findings}
