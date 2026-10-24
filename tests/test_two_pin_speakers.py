"""Synthetic regressions for the same-net two-pin speaker review rule."""

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

RULE_ID = "component.two_pin_speaker_same_net"


def speaker_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    open_pins: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"LS1": "Device:Speaker"}
    components = {
        reference: ComponentContract(value="Synthetic speaker", footprint="Synthetic:Speaker")
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
            nets[f"SPEAKER_NODE_{reference}"] = (first,)
            continue
        if same_net:
            pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
            nets[f"SPEAKER_NODE_{reference}"] = pins
        else:
            nets[f"SPEAKER_PLUS_{reference}"] = (first,)
            nets[f"SPEAKER_MINUS_{reference}"] = (second,)
            if reference in multi_pin:
                nets[f"SPEAKER_EXTRA_{reference}"] = (f"{reference}.3",)
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
        project_id="synthetic-two-pin-speakers",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_exact_speaker_is_reviewed_without_claiming_operation() -> None:
    observed = speaker_netlist()
    observations = two_pin_components_on_same_net(observed)
    assert [(item.reference, item.kind, item.net) for item in observations] == [
        ("LS1", "speaker", "SPEAKER_NODE_LS1")
    ]

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "LS1: both speaker terminals share SPEAKER_NODE_LS1"
    assert finding.evidence["symbol"] == ("Device:Speaker",)
    assert finding.evidence["pin_assignments"] == (
        "LS1.1 -> SPEAKER_NODE_LS1",
        "LS1.2 -> SPEAKER_NODE_LS1",
    )
    assert "does not establish speaker behavior" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_speaker_terminal_nets_are_the_no_finding_control() -> None:
    report = lint_report(speaker_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_skips_dnp_incomplete_ambiguous_open_multi_pin_and_unconfirmed_symbols() -> None:
    observed = speaker_netlist(
        dnp=("LS_DNP",),
        omit_inventory=("LS_MISSING",),
        ambiguous=("LS_AMBIGUOUS",),
        open_pins=("LS_OPEN",),
        multi_pin=("LS_MULTIPIN",),
        symbols={
            "LS_DNP": "Device:Speaker",
            "LS_MISSING": "Device:Speaker",
            "LS_AMBIGUOUS": "Device:Speaker",
            "LS_OPEN": "Device:Speaker",
            "LS_MULTIPIN": "Device:Speaker",
            "LS_ALT": "Device:Speaker_Crystal",
            "LS_CUSTOM": "Vendor:Speaker",
        },
    )
    assert two_pin_components_on_same_net(observed) == ()
    report = lint_report(observed)
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_and_exact_fingerprint_ignore_are_configurable() -> None:
    observed = speaker_netlist()
    finding = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires a disposition for tied speaker terminals",
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
                    reason="Synthetic reviewer accepts this explicit speaker bypass",
                ),
            )
        ),
    )
    assert next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    ).disposition == ("IGNORED")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_order_is_stable_and_splitting_the_speaker_clears_its_finding() -> None:
    source = speaker_netlist()
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

    split = lint_report(speaker_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in split.findings}
