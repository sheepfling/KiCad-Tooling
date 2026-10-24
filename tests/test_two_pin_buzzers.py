"""Synthetic regressions for the same-net two-pin buzzer review rule."""

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
from kicad_tooling.hwrepo.two_pin_buzzers import two_pin_buzzer_same_net_candidates
from kicad_tooling.hwrepo.two_pin_components import two_pin_components_on_same_net

pytestmark = [pytest.mark.component_lint, pytest.mark.design_lint]

RULE_ID = "component.two_pin_buzzer_same_net"


def buzzer_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    open_pins: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"BZ1": "Device:Buzzer"}
    components = {
        reference: ComponentContract(value="Synthetic buzzer", footprint="Synthetic:Buzzer")
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
            nets[f"BUZZER_NODE_{reference}"] = (first,)
            continue
        if same_net:
            pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
            nets[f"BUZZER_NODE_{reference}"] = pins
        else:
            nets[f"BUZZER_PLUS_{reference}"] = (first,)
            nets[f"BUZZER_MINUS_{reference}"] = (second,)
            if reference in multi_pin:
                nets[f"BUZZER_EXTRA_{reference}"] = (f"{reference}.3",)
        if reference in ambiguous:
            nets[f"ALSO_{reference}"] = (second,)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def lint_report(
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> object:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-buzzers",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_supported_buzzer_is_reviewed_without_claiming_operation() -> None:
    observed = buzzer_netlist()
    observations = two_pin_components_on_same_net(observed)
    assert [(item.reference, item.kind, item.net) for item in observations] == [
        ("BZ1", "buzzer", "BUZZER_NODE_BZ1")
    ]

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "BZ1: both buzzer terminals share BUZZER_NODE_BZ1"
    assert finding.evidence["symbol"] == ("Device:Buzzer",)
    assert finding.evidence["pin_assignments"] == (
        "BZ1.1 -> BUZZER_NODE_BZ1",
        "BZ1.2 -> BUZZER_NODE_BZ1",
    )
    assert "does not establish buzzer behavior" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_buzzer_terminal_nets_are_the_no_finding_control() -> None:
    report = lint_report(buzzer_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_skips_dnp_incomplete_ambiguous_open_multi_pin_and_unconfirmed_symbols() -> None:
    observed = buzzer_netlist(
        dnp=("BZ_DNP",),
        omit_inventory=("BZ_MISSING",),
        ambiguous=("BZ_AMBIGUOUS",),
        open_pins=("BZ_OPEN",),
        multi_pin=("BZ_MULTIPIN",),
        symbols={
            "BZ_DNP": "Device:Buzzer",
            "BZ_MISSING": "Device:Buzzer",
            "BZ_AMBIGUOUS": "Device:Buzzer",
            "BZ_OPEN": "Device:Buzzer",
            "BZ_MULTIPIN": "Device:Buzzer",
            "BZ_ALT": "Device:Buzzer_Active",
            "BZ_CUSTOM": "Vendor:PiezoBuzzer",
        },
    )
    assert two_pin_buzzer_same_net_candidates(two_pin_components_on_same_net(observed)) == ()
    report = lint_report(observed)
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_and_exact_fingerprint_ignore_are_configurable() -> None:
    observed = buzzer_netlist()
    finding = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires a disposition for tied buzzer terminals",
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
                    reason="Synthetic reviewer accepts this explicit buzzer bypass",
                ),
            )
        ),
    )
    assert next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    ).disposition == ("IGNORED")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_order_is_stable_and_splitting_the_buzzer_clears_its_finding() -> None:
    source = buzzer_netlist()
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
    assert len(original_findings) == 1
    assert reordered_findings == original_findings

    split = lint_report(buzzer_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in split.findings}
