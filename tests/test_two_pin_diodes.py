"""Synthetic regressions for the same-net two-pin diode review rule."""

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
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.two_pin_diodes import two_pin_diodes_on_same_net

pytestmark = [
    pytest.mark.component_lint,
    pytest.mark.design_lint,
]


RULE_ID = "component.two_pin_diode_same_net"


def diode_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    unassigned: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"D1": "Device:D", "D2": "Device:D_Schottky"}
    components = {
        reference: ComponentContract(value="1N4148", footprint="Synthetic:SOD-123")
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
        if reference in unassigned:
            nets[f"PARTIAL_{reference}"] = (first,)
            continue
        if same_net:
            pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
            nets[f"SHORT_{reference}"] = pins
        else:
            nets[f"{reference}_A"] = (first,)
            nets[f"{reference}_B"] = (second,)
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
        project_id="synthetic-two-pin-diodes",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


def test_native_schematic_sources_match_reviewed_hashes() -> None:
    fixture_root = Path(__file__).parents[1] / "tests/fixtures/design_lint/two-pin-components"
    expected = {
        "same-net-diode.kicad_sch": "c7b34973f881f5c8d8e8ac26b07c03dec70b061f66b8338d61fb085583c2aa8b",
        "distinct-nets-diode.kicad_sch": "74d19829e8dd9379a26cb6da9dd3cf10a48abce9d724661338f73ce0086bb928",
    }
    actual = {
        name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest() for name in expected
    }
    assert actual == expected


def test_detects_exact_device_diode_families_on_one_net() -> None:
    observed = diode_netlist()
    candidates = two_pin_diodes_on_same_net(observed)
    assert [(item.reference, item.kind, item.value) for item in candidates] == [
        ("D1", "diode", "1N4148"),
        ("D2", "diode", "1N4148"),
    ]

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 2
    finding = next(item for item in findings if item.subject.startswith("D1 "))
    assert finding.mode == "review"
    assert finding.evidence["symbol"] == ("Device:D",)
    assert finding.evidence["net"] == ("SHORT_D1",)
    assert finding.evidence["pin_assignments"] == (
        "D1.1 -> SHORT_D1",
        "D1.2 -> SHORT_D1",
    )
    assert "does not establish that the topology is wrong" in finding.message


def test_distinct_pin_nets_are_the_no_finding_control() -> None:
    report = lint_report(diode_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


def test_skips_dnp_incomplete_ambiguous_and_unsupported_symbols() -> None:
    observed = diode_netlist(
        dnp=("D1",),
        omit_inventory=("D2",),
        ambiguous=("D3",),
        multi_pin=("D4",),
        unassigned=("D5",),
        symbols={
            "D1": "Device:D",
            "D2": "Device:D_Zener",
            "D3": "Device:D_TVS",
            "D4": "Device:D",
            "D5": "Device:D",
            "LED1": "Device:LED",
            "X1": "Synthetic:TwoPinDiode",
        },
    )
    assert two_pin_diodes_on_same_net(observed) == ()


def test_rule_policy_and_exact_ignore_are_project_configurable() -> None:
    observed = diode_netlist()
    original = lint_report(observed)
    finding = next(item for item in original.findings if item.rule_id == RULE_ID)

    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires disposition of bypassed diodes",
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
                    reason="Synthetic configuration fixture disables this prompt",
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
                    reason="Synthetic project review accepts this explicit diode bypass",
                ),
            )
        ),
    )
    ignored_finding = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored_finding.disposition == "IGNORED"


def test_order_is_stable_and_splitting_one_component_clears_only_its_finding() -> None:
    source = diode_netlist()
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
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == RULE_ID
    }
    assert len(original_findings) == 2
    assert reordered_findings == original_findings

    unrelated_source = source.model_copy(
        update={
            "components": {
                **source.components,
                "R3": ComponentContract(value="10k", footprint="Synthetic:R_0603"),
            },
            "nets": {
                **source.nets,
                "+3V3": ("R3.1",),
                "GND": ("R3.2",),
            },
            "component_symbols": {**source.component_symbols, "R3": "Device:R"},
            "component_pin_numbers": {**source.component_pin_numbers, "R3": ("1", "2")},
        }
    )
    unrelated_report = lint_report(unrelated_source)
    unrelated_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in unrelated_report.findings
        if item.rule_id == RULE_ID
    }
    assert unrelated_report.netlist_sha256 != original.netlist_sha256
    assert unrelated_findings == original_findings

    d1_subject = next(subject for subject in original_findings if subject.startswith("D1 "))
    d2_subject = next(subject for subject in original_findings if subject.startswith("D2 "))
    d1_fingerprint = original_findings[d1_subject][0]
    ignore_policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=d1_fingerprint,
                reason="The D1 bypass is an accepted synthetic exception",
            ),
        )
    )
    for candidate_source in (source, unrelated_source):
        ignored_report = lint_report(candidate_source, ignore_policy)
        ignored_findings = {
            item.subject: item for item in ignored_report.findings if item.rule_id == RULE_ID
        }
        assert ignored_findings[d1_subject].fingerprint == d1_fingerprint
        assert ignored_findings[d1_subject].disposition == "IGNORED"
        assert ignored_findings[d2_subject].disposition == "OPEN"

    for subject in original_findings:
        reference = subject.split(" ", maxsplit=1)[0]
        split_nets = dict(source.nets)
        del split_nets[f"SHORT_{reference}"]
        split_nets[f"{reference}_A"] = (f"{reference}.1",)
        split_nets[f"{reference}_B"] = (f"{reference}.2",)
        split_report = lint_report(source.model_copy(update={"nets": split_nets}))
        remaining_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in split_report.findings
            if item.rule_id == RULE_ID
        }
        expected = dict(original_findings)
        del expected[subject]
        assert remaining_findings == expected
