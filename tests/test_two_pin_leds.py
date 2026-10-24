"""Synthetic regressions for the same-net two-pin LED review rule."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.component_role_models import ComponentRoleMap
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
from kicad_tooling.hwrepo.two_pin_leds import two_pin_led_same_net_candidates
from tests.design_lint_fixtures.component_roles import custom_led_role_map

pytestmark = [pytest.mark.component_lint, pytest.mark.design_lint]

RULE_ID = "component.two_pin_led_same_net"


def led_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    open_pins: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"LED1": "Device:LED"}
    components = {
        reference: ComponentContract(value="Synthetic indicator", footprint="Synthetic:LED_0603")
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
            nets[f"LED_NODE_{reference}"] = (first,)
            continue
        if same_net:
            pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
            nets[f"LED_NODE_{reference}"] = pins
        else:
            nets[f"LED_A_{reference}"] = (first,)
            nets[f"LED_K_{reference}"] = (second,)
            if reference in multi_pin:
                nets[f"LED_EXTRA_{reference}"] = (f"{reference}.3",)
        if reference in ambiguous:
            nets[f"ALSO_{reference}"] = (second,)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def custom_led_netlist(*, same_net: bool = True) -> NetlistContract:
    """Return one custom LED with the exact signature declared in its role map."""
    observed = led_netlist(same_net=same_net, symbols={"LED1": "Training:LED_5mm"})
    return observed.model_copy(
        update={
            "components": {
                "LED1": ComponentContract(
                    value="Training status LED",
                    footprint="Training:LED_0603",
                    part_id="training-led",
                )
            },
            "pin_functions": {"LED1.1": "A", "LED1.2": "K"},
            "pin_electrical_types": {"LED1.1": "passive", "LED1.2": "passive"},
        }
    )


def lint_report(
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> object:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-leds",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_supported_led_is_reviewed_without_claiming_drive() -> None:
    observed = led_netlist()
    observations = two_pin_components_on_same_net(observed)
    assert [(item.reference, item.kind, item.net) for item in observations] == [
        ("LED1", "led", "LED_NODE_LED1")
    ]

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "LED1: both LED terminals share LED_NODE_LED1"
    assert finding.evidence["symbol"] == ("Device:LED",)
    assert finding.evidence["pin_assignments"] == (
        "LED1.1 -> LED_NODE_LED1",
        "LED1.2 -> LED_NODE_LED1",
    )
    assert "does not establish LED behavior" in finding.message
    assert not {
        item.rule_id
        for item in report.findings
        if item.rule_id
        in {
            "component.led_directly_across_supply_and_return",
            "component.led_directly_driven_from_output",
        }
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_led_terminal_nets_are_the_no_finding_control() -> None:
    report = lint_report(led_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_mapped_custom_led_same_net_is_reviewed_with_role_evidence() -> None:
    observed = custom_led_netlist()
    role_map = custom_led_role_map()

    candidates = two_pin_components_on_same_net(observed, role_map)
    assert [(item.reference, item.kind, item.net) for item in candidates] == [
        ("LED1", "led", "LED_NODE_LED1")
    ]
    assert candidates[0].role_binding == role_map.entries[0]

    report = lint_report(observed, DesignLintPolicy(component_role_map=role_map))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert finding.evidence["symbol"] == ("Training:LED_5mm",)
    assert finding.evidence["classified_role"] == ("led",)
    assert finding.evidence["role_part_id"] == ("training-led",)
    assert finding.evidence["role_footprint"] == ("Training:LED_0603",)
    assert finding.evidence["role_pin_inventory"] == ("1=A/passive", "2=K/passive")
    assert finding.evidence["role_basis"] == ("Synthetic reviewed library symbol declaration",)
    assert len(finding.evidence["role_binding_sha256"][0]) == 64


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_mapped_custom_led_on_separate_nets_is_the_valid_control() -> None:
    report = lint_report(
        custom_led_netlist(same_net=False),
        DesignLintPolicy(component_role_map=custom_led_role_map()),
    )
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_custom_led_with_stale_pin_signature_is_not_classified() -> None:
    observed = custom_led_netlist().model_copy(
        update={"pin_functions": {"LED1.1": "K", "LED1.2": "A"}}
    )
    report = lint_report(observed, DesignLintPolicy(component_role_map=custom_led_role_map()))
    assert report.status == "BLOCKED"
    assert any(
        "pin number, function, and electrical-type inventory" in issue for issue in report.issues
    )
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_custom_led_role_fingerprint_is_order_stable_and_basis_bound() -> None:
    observed = custom_led_netlist()
    role_map = custom_led_role_map()

    def finding_for(selected_map: ComponentRoleMap):
        report = lint_report(observed, DesignLintPolicy(component_role_map=selected_map))
        return next(item for item in report.findings if item.rule_id == RULE_ID)

    original = finding_for(role_map)
    reversed_pins = ComponentRoleMap(
        entries=(
            role_map.entries[0].model_copy(
                update={"pins": tuple(reversed(role_map.entries[0].pins))}
            ),
        )
    )
    reordered = finding_for(reversed_pins)
    revised_basis = finding_for(custom_led_role_map("Updated reviewed LED identity basis"))

    assert original.fingerprint == reordered.fingerprint
    assert original.evidence == reordered.evidence
    assert original.fingerprint != revised_basis.fingerprint


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_skips_dnp_incomplete_ambiguous_multi_pin_and_unconfirmed_symbols() -> None:
    observed = led_netlist(
        dnp=("LED_DNP",),
        omit_inventory=("LED_MISSING",),
        ambiguous=("LED_AMBIGUOUS",),
        open_pins=("LED_OPEN",),
        multi_pin=("LED_MULTIPIN",),
        symbols={
            "LED_DNP": "Device:LED",
            "LED_MISSING": "Device:LED",
            "LED_AMBIGUOUS": "Device:LED",
            "LED_OPEN": "Device:LED",
            "LED_MULTIPIN": "Device:LED",
            "LED_ALT": "Device:LED_ALT",
            "LED_CUSTOM": "Vendor:StatusLED",
        },
    )
    assert two_pin_led_same_net_candidates(two_pin_components_on_same_net(observed)) == ()
    report = lint_report(observed)
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_and_exact_fingerprint_ignore_are_configurable() -> None:
    observed = led_netlist()
    finding = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project policy requires a disposition for tied LED terminals",
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
                    reason="Synthetic project configuration disables this review prompt",
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
                    reason="Synthetic reviewer accepts this explicit LED bypass",
                ),
            )
        ),
    )
    assert next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    ).disposition == ("IGNORED")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_order_is_stable_and_splitting_the_led_clears_its_finding() -> None:
    source = led_netlist()
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

    split = lint_report(led_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in split.findings}
