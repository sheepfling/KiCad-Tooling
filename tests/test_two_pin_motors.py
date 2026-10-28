"""Synthetic regressions for the same-net two-pin DC motor review rule."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

import pytest

from kicad_tooling.hwrepo.component_role_models import (
    ComponentRoleBinding,
    ComponentRoleMap,
    ComponentRolePin,
)
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
from tests.design_lint_fixtures.component_roles import custom_motor_role_map

pytestmark = [pytest.mark.component_lint, pytest.mark.design_lint]

RULE_ID = "component.two_pin_motor_same_net"
MOTOR_SYMBOL = "Motor:Motor_DC"


def motor_netlist(
    *,
    same_net: bool = True,
    dnp: tuple[str, ...] = (),
    omit_inventory: tuple[str, ...] = (),
    ambiguous: tuple[str, ...] = (),
    open_pins: tuple[str, ...] = (),
    multi_pin: tuple[str, ...] = (),
    symbols: Mapping[str, str] | None = None,
) -> NetlistContract:
    symbols = symbols or {"M1": MOTOR_SYMBOL}
    components = {
        reference: ComponentContract(value="Synthetic DC motor", footprint="Synthetic:Motor")
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
            nets[f"MOTOR_NODE_{reference}"] = (first,)
            continue
        if same_net:
            pins = (first, second, f"{reference}.3") if reference in multi_pin else (first, second)
            nets[f"MOTOR_NODE_{reference}"] = pins
        else:
            nets[f"MOTOR_A_{reference}"] = (first,)
            nets[f"MOTOR_B_{reference}"] = (second,)
            if reference in multi_pin:
                nets[f"MOTOR_EXTRA_{reference}"] = (f"{reference}.3",)
        if reference in ambiguous:
            nets[f"ALSO_{reference}"] = (second,)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
    )


def custom_motor_netlist(*, same_net: bool = True) -> NetlistContract:
    observed = motor_netlist(same_net=same_net, symbols={"M1": "Training:Motor_DC"})
    return observed.model_copy(
        update={
            "components": {
                "M1": ComponentContract(
                    value="Synthetic brushed motor",
                    footprint="Training:Motor_2pin",
                    part_id="training-motor",
                )
            },
            "pin_functions": {"M1.1": "A", "M1.2": "B"},
            "pin_electrical_types": {"M1.1": "passive", "M1.2": "passive"},
        }
    )


def lint_report(observed: NetlistContract, policy: DesignLintPolicy | None = None) -> object:
    serialized = observed.model_dump_json().encode("utf-8")
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-two-pin-motors",
        netlist_sha256=hashlib.sha256(serialized).hexdigest(),
        observed=observed,
    )
    return evaluate(coach.project_id, coach, policy or DesignLintPolicy())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_exact_dc_motor_is_reviewed_without_claiming_operation() -> None:
    observed = motor_netlist()
    observations = two_pin_components_on_same_net(observed)
    assert [(item.reference, item.kind, item.net) for item in observations] == [
        ("M1", "motor", "MOTOR_NODE_M1")
    ]

    report = lint_report(observed)
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "M1: both motor terminals share MOTOR_NODE_M1"
    assert finding.evidence["symbol"] == (MOTOR_SYMBOL,)
    assert finding.evidence["pin_assignments"] == (
        "M1.1 -> MOTOR_NODE_M1",
        "M1.2 -> MOTOR_NODE_M1",
    )
    assert "does not establish motor behavior" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_motor_terminal_nets_are_the_no_finding_control() -> None:
    report = lint_report(motor_netlist(same_net=False))
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_custom_motor_role_requires_two_passive_native_pins() -> None:
    with pytest.raises(ValueError, match="motor role requires two native passive pins"):
        ComponentRoleBinding(
            part_id="training-motor",
            symbol="Training:Motor_DC",
            footprint="Training:Motor_2pin",
            role="motor",
            pins=(
                ComponentRolePin(number="1", function="A", electrical_type="output"),
                ComponentRolePin(number="2", function="B", electrical_type="passive"),
            ),
            basis="Synthetic invalid motor pin declaration",
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_mapped_custom_motor_same_net_is_reviewed_with_role_evidence() -> None:
    observed = custom_motor_netlist()
    role_map = custom_motor_role_map()

    candidates = two_pin_components_on_same_net(observed, role_map)
    assert [(item.reference, item.kind, item.net) for item in candidates] == [
        ("M1", "motor", "MOTOR_NODE_M1")
    ]
    assert candidates[0].role_binding == role_map.entries[0]

    assert RULE_ID not in {item.rule_id for item in lint_report(observed).findings}
    report = lint_report(observed, DesignLintPolicy(component_role_map=role_map))
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert finding.evidence["symbol"] == ("Training:Motor_DC",)
    assert finding.evidence["classified_role"] == ("motor",)
    assert finding.evidence["role_part_id"] == ("training-motor",)
    assert finding.evidence["role_symbol"] == ("Training:Motor_DC",)
    assert finding.evidence["role_footprint"] == ("Training:Motor_2pin",)
    assert finding.evidence["role_pin_inventory"] == ("1=A/passive", "2=B/passive")
    assert finding.evidence["role_basis"] == ("Synthetic reviewed motor symbol declaration",)
    assert len(finding.evidence["role_binding_sha256"][0]) == 64


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_mapped_custom_motor_on_separate_nets_is_the_valid_control() -> None:
    report = lint_report(
        custom_motor_netlist(same_net=False),
        DesignLintPolicy(component_role_map=custom_motor_role_map()),
    )
    assert RULE_ID not in {item.rule_id for item in report.findings}
    assert report.status == "PASS"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_custom_motor_stale_pin_signature_blocks_classification() -> None:
    observed = custom_motor_netlist().model_copy(
        update={"pin_functions": {"M1.1": "B", "M1.2": "A"}}
    )
    report = lint_report(observed, DesignLintPolicy(component_role_map=custom_motor_role_map()))
    assert report.status == "BLOCKED"
    assert any(
        "complete native pin number, function, and electrical-type inventory" in issue
        for issue in report.issues
    )
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_custom_motor_role_fingerprint_is_order_stable_and_basis_bound() -> None:
    observed = custom_motor_netlist()
    role_map = custom_motor_role_map()

    def finding_for(selected_map: ComponentRoleMap):
        report = lint_report(observed, DesignLintPolicy(component_role_map=selected_map))
        return next(item for item in report.findings if item.rule_id == RULE_ID)

    original = finding_for(role_map)
    reversed_pins = role_map.model_copy(
        update={
            "entries": (
                role_map.entries[0].model_copy(
                    update={"pins": tuple(reversed(role_map.entries[0].pins))}
                ),
            )
        }
    )
    reordered = finding_for(reversed_pins)
    revised_basis = finding_for(custom_motor_role_map("Updated reviewed motor identity basis"))

    assert original.fingerprint == reordered.fingerprint
    assert original.evidence == reordered.evidence
    assert original.fingerprint != revised_basis.fingerprint


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_skips_dnp_incomplete_ambiguous_open_multi_pin_and_other_symbols() -> None:
    observed = motor_netlist(
        dnp=("M_DNP",),
        omit_inventory=("M_MISSING",),
        ambiguous=("M_AMBIGUOUS",),
        open_pins=("M_OPEN",),
        multi_pin=("M_MULTIPIN",),
        symbols={
            "M_DNP": MOTOR_SYMBOL,
            "M_MISSING": MOTOR_SYMBOL,
            "M_AMBIGUOUS": MOTOR_SYMBOL,
            "M_OPEN": MOTOR_SYMBOL,
            "M_MULTIPIN": MOTOR_SYMBOL,
            "M_ALT": "Motor:Motor_DC_ALT",
            "M_AC": "Motor:Motor_AC",
            "M_CUSTOM": "Vendor:Motor_DC",
        },
    )
    assert two_pin_components_on_same_net(observed) == ()
    report = lint_report(observed)
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_and_exact_fingerprint_ignore_are_project_configurable() -> None:
    observed = motor_netlist()
    finding = next(item for item in lint_report(observed).findings if item.rule_id == RULE_ID)
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project requires disposition of a same-net motor",
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
                    reason="Synthetic reviewer accepts this intentional motor bypass",
                ),
            )
        ),
    )
    assert next(
        item for item in ignored.findings if item.fingerprint == finding.fingerprint
    ).disposition == ("IGNORED")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_order_is_stable_and_splitting_one_motor_clears_only_its_finding() -> None:
    source = motor_netlist(symbols={"M1": MOTOR_SYMBOL, "M2": MOTOR_SYMBOL})
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
    nets.pop("MOTOR_NODE_M1")
    nets["MOTOR_A_M1"] = ("M1.1",)
    nets["MOTOR_B_M1"] = ("M1.2",)
    split = lint_report(source.model_copy(update={"nets": nets}))
    assert {item.subject for item in split.findings if item.rule_id == RULE_ID} == {
        "M2: both motor terminals share MOTOR_NODE_M2"
    }
