"""Synthetic USB-C VBUS capacitor-presence review heuristic cases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.usb_c_vbus_capacitance_support import (
    usb_c_capacitance_roster,
    usb_c_vbus_netlist,
    usb_c_vbus_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.usb_c_vbus_capacitance_review"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_likely_usb_c_port_without_vbus_capacitor_prompts_for_review() -> None:
    report = usb_c_vbus_report(usb_c_vbus_netlist())

    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "J1: USB-C VBUS has no recognized return capacitor"
    assert finding.mode == "review"
    assert finding.evidence["VBUS_pin_assignments"] == ("J1.3=VBUS_PORT",)
    assert finding.evidence["return_pin_assignments"] == ("J1.4=GND",)
    assert finding.evidence["capacitor_touchpoints"] == ("none",)
    assert "do not establish a universal requirement" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fitted_exact_two_pin_capacitor_clears_candidate_and_dnp_does_not() -> None:
    control = usb_c_vbus_report(usb_c_vbus_netlist(capacitor=True))
    dnp_fault = usb_c_vbus_report(usb_c_vbus_netlist(dnp_capacitor=True))

    assert RULE_ID not in {item.rule_id for item in control.findings}
    finding = next(item for item in dnp_fault.findings if item.rule_id == RULE_ID)
    assert finding.evidence["capacitor_touchpoints"] == ("C1 (DNP)=GND/VBUS_PORT",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_capacitor_on_another_return_or_ambiguous_pin_assignment_does_not_satisfy() -> None:
    split_return = usb_c_vbus_report(
        usb_c_vbus_netlist(capacitor=True, capacitor_return_net="ISOLATED_RETURN")
    )
    ambiguous = usb_c_vbus_report(usb_c_vbus_netlist(capacitor=True, ambiguous_capacitor_pin=True))

    assert RULE_ID in {item.rule_id for item in split_return.findings}
    assert RULE_ID in {item.rule_id for item in ambiguous.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_authored_required_or_not_applicable_scope_delegates_or_suppresses() -> None:
    missing_cap = usb_c_vbus_netlist()
    required = usb_c_vbus_report(
        missing_cap,
        roster=usb_c_capacitance_roster("required"),
    )
    pending = usb_c_vbus_report(
        missing_cap,
        roster=usb_c_capacitance_roster("pending"),
    )
    not_applicable = usb_c_vbus_report(
        missing_cap,
        roster=usb_c_capacitance_roster("not_applicable"),
    )

    assert RULE_ID not in {item.rule_id for item in required.findings}
    pending_finding = next(item for item in pending.findings if item.rule_id == RULE_ID)
    assert pending_finding.evidence["VBUS_capacitance_scope"] == ("pending",)
    assert pending_finding.evidence["electrical_contract_path"] == (
        "tests/fixtures/synthetic-usb-c/electrical.json",
    )
    assert RULE_ID not in {item.rule_id for item in not_applicable.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_order_is_stable_and_project_policy_is_configurable() -> None:
    netlist = usb_c_vbus_netlist()
    regular = usb_c_vbus_report(netlist)
    reordered = usb_c_vbus_report(
        netlist.model_copy(
            update={
                "nets": dict(reversed(tuple(netlist.nets.items()))),
                "components": dict(reversed(tuple(netlist.components.items()))),
                "pin_functions": dict(reversed(tuple(netlist.pin_functions.items()))),
            }
        )
    )
    assert regular.findings == reordered.findings
    finding = next(item for item in regular.findings if item.rule_id == RULE_ID)

    blocked = usb_c_vbus_report(
        netlist,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Review USB-C VBUS"),
            )
        ),
    )
    off = usb_c_vbus_report(
        netlist,
        policy=DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Owned elsewhere"),)
        ),
    )
    ignored = usb_c_vbus_report(
        netlist,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="The port has an approved external capacitance arrangement.",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"
    assert next(item for item in off.findings if item.rule_id == RULE_ID).disposition == "RULE_OFF"
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )
