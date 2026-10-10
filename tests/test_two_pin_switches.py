"""Synthetic regressions for the exact two-pin SPST switch review rule."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.two_pin_switches import two_pin_switches_on_same_net

pytestmark = [
    pytest.mark.component_lint,
    pytest.mark.design_lint,
]


RULE_ID = "component.two_pin_switch_same_net"


def test_native_schematic_sources_match_reviewed_hashes() -> None:
    fixture_root = Path(__file__).parents[1] / "tests/fixtures/design_lint/two-pin-switches"
    expected = {
        "same-net-spst.kicad_sch": "1ddb2e72f4759c3edddd0f1c7077090c911fa3cbd36d48ef5a0850d6146c25b4",
        "distinct-nets-spst.kicad_sch": "2f9e43e716fe6bc89645734768ced5ff5491ba8b62330aa1c544db236d31e147",
    }
    actual = {
        name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest() for name in expected
    }
    assert actual == expected


def switch_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    unassigned: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"SW1": "Switch:SW_SPST"}
    components = {
        reference: ComponentContract(value="Synthetic SPST", footprint="Synthetic:SPST_THT")
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
        first, second = f"{reference}.1", f"{reference}.2"
        if reference in unassigned:
            nets[f"PARTIAL_{reference}"] = (first,)
            continue
        pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
        if same_net:
            nets[f"BYPASSED_{reference}"] = pins
        else:
            nets[f"{reference}_INPUT"] = (first,)
            nets[f"{reference}_OUTPUT"] = (second,)
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
) -> DesignLintReport:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-switches",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


def test_detects_exact_spst_switch_bypassed_by_one_net() -> None:
    observed = switch_netlist()
    candidates = two_pin_switches_on_same_net(observed)
    assert [(item.reference, item.kind, item.value) for item in candidates] == [
        ("SW1", "switch", "Synthetic SPST")
    ]

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Switch:SW_SPST",)
    assert finding.evidence["component_kind"] == ("switch",)
    assert finding.evidence["net"] == ("BYPASSED_SW1",)
    assert finding.evidence["pin_assignments"] == (
        "SW1.1 -> BYPASSED_SW1",
        "SW1.2 -> BYPASSED_SW1",
    )
    assert "does not establish that the topology is wrong" in finding.message


def test_distinct_pin_nets_are_the_no_finding_control() -> None:
    report = lint_report(switch_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.parametrize(
    "observed",
    (
        switch_netlist(dnp=("SW1",)),
        switch_netlist(omit_inventory=("SW1",)),
        switch_netlist(ambiguous=("SW1",)),
        switch_netlist(multi_pin=("SW1",)),
        switch_netlist(unassigned=("SW1",)),
        switch_netlist(symbols={"SW1": "Switch:SW_SPDT"}),
        switch_netlist(symbols={"SW1": "Switch:SW_SPST_LED"}),
        switch_netlist(symbols={"SW1": "Switch:SW_SPST_Temperature"}),
        switch_netlist(symbols={"SW1": "Vendor:SW_SPST"}),
        switch_netlist(symbols={"SW1": "Device:R"}),
    ),
)
def test_skips_dnp_incomplete_ambiguous_and_unsupported_symbols(
    observed: NetlistContract,
) -> None:
    assert two_pin_switches_on_same_net(observed) == ()
    assert RULE_ID not in {item.rule_id for item in lint_report(observed).findings}


def test_rule_policy_and_exact_ignore_are_project_configurable() -> None:
    observed = switch_netlist()
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires review of bypassed switches",
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
                    reason="Synthetic fixture disables the switch prompt",
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
                    reason="Synthetic project review accepts this explicit bypass",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_order_is_stable_and_splitting_the_switch_clears_the_finding() -> None:
    source = switch_netlist()
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

    split_source = source.model_copy(
        update={
            "nets": {
                "SW1_INPUT": ("SW1.1",),
                "SW1_OUTPUT": ("SW1.2",),
            }
        }
    )
    assert RULE_ID not in {item.rule_id for item in lint_report(split_source).findings}
