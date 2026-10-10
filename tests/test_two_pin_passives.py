"""Synthetic regressions for the same-net two-pin passive review rule."""

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
from kicad_tooling.hwrepo.two_pin_passives import two_pin_passives_on_same_net
from tests.design_lint_fixtures import (
    custom_decoupling_capacitor_role_map,
    custom_ic_decoupling_capacitor_fixture,
)

pytestmark = [
    pytest.mark.component_lint,
    pytest.mark.design_lint,
]


def passive_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {
        "R1": "Device:R",
        "C1": "Device:C_Polarized",
        "L1": "Device:L",
    }
    components = {
        "R1": ComponentContract(value="10k", footprint="Synthetic:R_0603"),
        "C1": ComponentContract(value="10uF", footprint="Synthetic:C_0603"),
        "L1": ComponentContract(value="10uH", footprint="Synthetic:L_0603"),
    }
    pin_numbers = {
        reference: ("1", "2") for reference in symbols if reference not in omit_inventory
    }
    nets: dict[str, tuple[str, ...]] = {}
    for reference in symbols:
        if reference in dnp or reference in omit_inventory:
            continue
        first = f"{reference}.1"
        second = f"{reference}.2"
        if same_net:
            nets[f"SHORT_{reference}"] = (first, second)
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
        project_id="synthetic-two-pin-passives",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


def custom_capacitor_same_net_fixture(*, dnp: bool = False) -> NetlistContract:
    """Place the exact mapped custom capacitor pins on one synthetic net."""
    source = custom_ic_decoupling_capacitor_fixture(dnp_capacitor=dnp)
    capacitor_pins = {"c1.1", "c1.2"}
    nets = {
        name: remaining
        for name, pins in source.nets.items()
        if (remaining := tuple(pin for pin in pins if pin.casefold() not in capacitor_pins))
    }
    nets["BYPASSED_CAP"] = ("C1.1", "C1.2")
    return source.model_copy(update={"nets": nets})


def test_detects_resistor_capacitor_and_inductor_on_their_same_net() -> None:
    observed = passive_netlist()
    candidates = two_pin_passives_on_same_net(observed)
    assert [(item.reference, item.kind, item.value) for item in candidates] == [
        ("C1", "capacitor", "10uF"),
        ("L1", "inductor", "10uH"),
        ("R1", "resistor", "10k"),
    ]

    report = lint_report(observed)
    findings = [
        item for item in report.findings if item.rule_id == "component.two_pin_passive_same_net"
    ]
    assert report.status == "REVIEW"
    assert len(findings) == 3
    resistor = next(item for item in findings if item.subject.startswith("R1 "))
    assert resistor.mode == "review"
    assert resistor.evidence["net"] == ("SHORT_R1",)
    assert resistor.evidence["pin_assignments"] == ("R1.1 -> SHORT_R1", "R1.2 -> SHORT_R1")
    assert "does not establish that the topology is wrong" in resistor.message


def test_distinct_pin_nets_are_the_no_finding_control() -> None:
    report = lint_report(passive_netlist(same_net=False))
    assert "component.two_pin_passive_same_net" not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


def test_custom_capacitor_requires_exact_role_map_for_same_net_review() -> None:
    observed = custom_capacitor_same_net_fixture()
    rule_id = "component.two_pin_passive_same_net"
    unclassified = lint_report(observed)
    assert rule_id not in {item.rule_id for item in unclassified.findings}

    role_map = custom_decoupling_capacitor_role_map()
    mapped = lint_report(observed, DesignLintPolicy(component_role_map=role_map))
    finding = next(item for item in mapped.findings if item.rule_id == rule_id)
    assert mapped.status == "REVIEW"
    assert finding.evidence["symbol"] == ("Vendor:CAP123",)
    assert finding.evidence["net"] == ("BYPASSED_CAP",)
    assert finding.evidence["pin_assignments"] == (
        "C1.1 -> BYPASSED_CAP",
        "C1.2 -> BYPASSED_CAP",
    )
    assert finding.evidence["classified_role"] == ("capacitor",)
    assert finding.evidence["role_part_id"] == ("synthetic-decoupling-capacitor",)
    assert finding.evidence["role_basis"] == (role_map.entries[0].basis,)
    assert len(finding.evidence["role_binding_sha256"][0]) == 64

    candidates = two_pin_passives_on_same_net(observed, role_map)
    assert [(item.reference, item.kind, item.role_binding) for item in candidates] == [
        ("C1", "capacitor", role_map.entries[0])
    ]


def test_mapped_custom_capacitor_distinct_net_and_dnp_controls_stay_quiet() -> None:
    role_map = custom_decoupling_capacitor_role_map()
    rule_id = "component.two_pin_passive_same_net"
    control = lint_report(
        custom_ic_decoupling_capacitor_fixture(),
        DesignLintPolicy(component_role_map=role_map),
    )
    dnp = lint_report(
        custom_capacitor_same_net_fixture(dnp=True),
        DesignLintPolicy(component_role_map=role_map),
    )
    assert rule_id not in {item.rule_id for item in control.findings}
    assert rule_id not in {item.rule_id for item in dnp.findings}


def test_same_net_passive_findings_are_order_stable_and_each_split_clears_one() -> None:
    source = passive_netlist()
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
    rule_id = "component.two_pin_passive_same_net"
    original_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in original.findings
        if item.rule_id == rule_id
    }
    reordered_findings = {
        item.subject: (item.fingerprint, item.evidence)
        for item in reordered.findings
        if item.rule_id == rule_id
    }
    assert len(original_findings) == 3
    assert reordered_findings == original_findings

    for subject, original_finding in original_findings.items():
        reference = subject.split(" ", maxsplit=1)[0]
        pin_numbers = source.component_pin_numbers[reference]
        split_nets = dict(source.nets)
        del split_nets[f"SHORT_{reference}"]
        split_nets[f"{reference}_A"] = (f"{reference}.{pin_numbers[0]}",)
        split_nets[f"{reference}_B"] = (f"{reference}.{pin_numbers[1]}",)
        split = source.model_copy(update={"nets": split_nets})
        split_report = lint_report(split)
        remaining_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in split_report.findings
            if item.rule_id == rule_id
        }
        expected = dict(original_findings)
        del expected[subject]
        assert remaining_findings == expected, original_finding


def test_skips_dnp_incomplete_ambiguous_and_unsupported_symbols() -> None:
    observed = passive_netlist(
        dnp=("R1",),
        omit_inventory=("C1",),
        ambiguous=("L1",),
        symbols={
            "R1": "Device:R",
            "C1": "Device:C",
            "L1": "Device:L",
            "Q1": "Device:R_POT",
            "U1": "Synthetic:TwoPinPassive",
        },
    )
    observed = observed.model_copy(
        update={
            "components": {
                **observed.components,
                "Q1": ComponentContract(value="10k", footprint="Synthetic:Pot"),
                "U1": ComponentContract(value="Custom", footprint="Synthetic:Custom"),
            },
            "nets": {
                **observed.nets,
                "POT_NODE": ("Q1.1", "Q1.2", "Q1.3"),
                "CUSTOM_NODE": ("U1.1", "U1.2"),
            },
            "component_pin_numbers": {
                **observed.component_pin_numbers,
                "Q1": ("1", "2", "3"),
                "U1": ("1", "2"),
            },
        }
    )
    assert not two_pin_passives_on_same_net(observed)


def test_unassigned_pins_and_missing_component_identity_are_skipped() -> None:
    incomplete = NetlistContract(
        components={"R1": ComponentContract(value="10k", footprint="Synthetic:R")},
        nets={"SHARED": ("R1.1",)},
        component_symbols={"R1": "Device:R", "R2": "Device:R"},
        component_pin_numbers={"R1": ("1", "2"), "R2": ("1", "2")},
    )
    assert not two_pin_passives_on_same_net(incomplete)


def test_override_exact_ignore_and_stale_fingerprint_lifecycle() -> None:
    original = lint_report(passive_netlist())
    finding = next(
        item
        for item in original.findings
        if item.rule_id == "component.two_pin_passive_same_net" and item.subject.startswith("R1 ")
    )
    blocked = lint_report(
        passive_netlist(),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="component.two_pin_passive_same_net",
                    mode="block",
                    reason="Synthetic release policy requires disposition of shorted passives",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = lint_report(
        passive_netlist(),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="component.two_pin_passive_same_net",
                    mode="off",
                    reason="Synthetic design review accepts the explicit same-net jumper",
                ),
            )
        ),
    )
    disabled_resistor = next(
        item
        for item in disabled.findings
        if item.rule_id == "component.two_pin_passive_same_net" and item.subject.startswith("R1 ")
    )
    assert disabled.status == "PASS"
    assert disabled_resistor.disposition == "RULE_OFF"

    ignored = lint_report(
        passive_netlist(),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic fixture accepts this reviewed same-net jumper",
                ),
            )
        ),
    )
    ignored_resistor = next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    )
    assert ignored.status == "REVIEW"
    assert ignored_resistor.disposition == "IGNORED"

    renamed = passive_netlist().model_copy(
        update={
            "nets": {
                "SHORTED_R1": ("R1.1", "R1.2"),
                **{
                    key: value for key, value in passive_netlist().nets.items() if key != "SHORT_R1"
                },
            }
        }
    )
    stale = lint_report(
        renamed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Stale fingerprint control",
                ),
            )
        ),
    )
    changed_finding = next(
        item
        for item in stale.findings
        if item.rule_id == finding.rule_id and item.subject.startswith("R1 ")
    )
    assert changed_finding.fingerprint != finding.fingerprint
    assert changed_finding.disposition == "OPEN"
