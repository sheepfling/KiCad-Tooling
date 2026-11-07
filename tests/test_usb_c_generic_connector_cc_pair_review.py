"""Focused regressions for generic contacts matching USB-C controller CC nets."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.contract_coach_models import ContractCoachReport
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.design_lint_usb_c_generic_connector_candidates import RULE_ID
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.usb_c_generic_connector import usb_c_generic_connector_pairs
from kicad_tooling.hwrepo.usb_c_ports import UsbCPortRosterContext
from tests.design_lint_fixtures.usb_c_generic_connector_cc_pair import (
    generic_usb_c_connector_cc_pair_netlist,
)
from tests.electrical_usb_c_support import usb_c_requirement

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _report(
    source: NetlistContract | None = None,
    *,
    roster: UsbCPortRosterContext | None = None,
    mode: str | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    observed = source if source is not None else generic_usb_c_connector_cc_pair_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-usb-c-generic-connector",
        observed=observed,
        netlist_sha256="a" * 64,
    )
    overrides = ()
    if mode is not None:
        overrides = (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic project requires an explicit connector decision",
            ),
        )
    policy = DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,))
    return evaluate(
        coach.project_id,
        coach,
        policy,
        usb_c_port_roster=roster or UsbCPortRosterContext(state="not_configured"),
    )


def _finding(report: DesignLintReport) -> DesignLintFinding:
    return next(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_connector_contacts_on_both_controller_cc_nets_request_review() -> None:
    report = _report()
    finding = _finding(report)

    assert report.status == "REVIEW"
    assert finding.subject == "J1 / U1: generic pins match USB-C CC1/CC2 nets"
    assert finding.mode == "review"
    assert finding.evidence["USB_C_CC1_controller_pin"] == ("U1.1",)
    assert finding.evidence["USB_C_CC1_net"] == ("USB_CC1",)
    assert finding.evidence["USB_C_CC1_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["USB_C_CC2_controller_pin"] == ("U1.2",)
    assert finding.evidence["USB_C_CC2_net"] == ("USB_CC2",)
    assert finding.evidence["USB_C_CC2_generic_connector_pins"] == ("J1.2",)
    assert "does not identify the connector as USB-C" in finding.message
    assert "or establish PCB copper or continuity" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_pinout_and_single_cc_contact_are_controls() -> None:
    named = generic_usb_c_connector_cc_pair_netlist(connector_functions=("CC1", "CC2", "GND"))
    single_contact = generic_usb_c_connector_cc_pair_netlist(include_cc2_contact=False)

    assert not usb_c_generic_connector_pairs(named)
    assert not usb_c_generic_connector_pairs(single_contact)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_incomplete_duplicate_and_ambiguous_endpoints_are_quiet() -> None:
    complete = generic_usb_c_connector_cc_pair_netlist()
    cases = (
        generic_usb_c_connector_cc_pair_netlist(dnp=("J1",)),
        generic_usb_c_connector_cc_pair_netlist(dnp=("U1",)),
        complete.model_copy(
            update={"component_pin_numbers": {"J1": ("1", "2"), "U1": ("1", "2", "3")}}
        ),
        complete.model_copy(
            update={"component_pin_numbers": {"J1": ("1", "1", "2", "4"), "U1": ("1", "2", "3")}}
        ),
        generic_usb_c_connector_cc_pair_netlist(controller_functions=("CC1", "CC1")),
        complete.model_copy(
            update={
                "nets": {
                    "USB_CC1": ("J1.1", "U1.1", "U1.2"),
                    "USB_CC2": ("J1.2",),
                    "USB_GND": ("J1.4", "U1.3"),
                }
            }
        ),
    )
    for source in cases:
        assert not usb_c_generic_connector_pairs(source)

    extra_controller = complete.model_copy(
        update={
            "components": {
                **complete.components,
                "U2": complete.components["U1"],
            },
            "component_symbols": {
                **complete.component_symbols,
                "U2": "Synthetic:UsbCController",
            },
            "component_pin_numbers": {
                **complete.component_pin_numbers,
                "U2": ("1", "2", "3"),
            },
            "pin_functions": {
                **complete.pin_functions,
                "U2.1": "CC1",
                "U2.2": "CC2",
                "U2.3": "VSS",
            },
            "nets": {
                **complete.nets,
                "USB_CC1": (*complete.nets["USB_CC1"], "U2.1"),
                "USB_CC2": (*complete.nets["USB_CC2"], "U2.2"),
                "USB_GND": (*complete.nets["USB_GND"], "U2.3"),
            },
        }
    )
    assert not usb_c_generic_connector_pairs(extra_controller)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_usb_c_map_resolves_prompt_and_other_connectors_remain_reviewable() -> None:
    roster = UsbCPortRosterContext(
        state="required",
        analysis=usb_c_requirement(connector="J1"),
        source_path="tests/fixtures/synthetic-usb-c-map.json",
        source_sha256="b" * 64,
    )

    assert not any(item.rule_id == RULE_ID for item in _report(roster=roster).findings)
    other = generic_usb_c_connector_cc_pair_netlist().model_copy(
        update={
            "components": {
                "J2": generic_usb_c_connector_cc_pair_netlist().components["J1"],
                "U1": generic_usb_c_connector_cc_pair_netlist().components["U1"],
            },
            "component_symbols": {
                "J2": "Synthetic:GenericConnector",
                "U1": "Synthetic:UsbCController",
            },
            "component_pin_numbers": {"J2": ("1", "2", "4"), "U1": ("1", "2", "3")},
            "pin_functions": {
                "J2.1": "Pin_1",
                "J2.2": "Pin_2",
                "J2.4": "GND",
                "U1.1": "CC1",
                "U1.2": "CC2",
                "U1.3": "VSS",
            },
            "pin_electrical_types": {
                "J2.1": "passive",
                "J2.2": "passive",
                "J2.4": "passive",
                "U1.1": "bidirectional",
                "U1.2": "bidirectional",
                "U1.3": "power_in",
            },
            "nets": {
                "USB_CC1": ("J2.1", "U1.1"),
                "USB_CC2": ("J2.2", "U1.2"),
                "USB_GND": ("J2.4", "U1.3"),
            },
        }
    )
    assert _finding(_report(other, roster=roster)).evidence["connector"] == ("J2",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_exactly_ignore_prompt() -> None:
    finding = _finding(_report())
    ignored = _finding(
        _report(
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Reviewed as an intentional test connector",
            )
        )
    )

    assert _finding(_report(mode="block")).mode == "block"
    assert _finding(_report(mode="off")).disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_evidence_is_stable_under_mapping_order() -> None:
    source = generic_usb_c_connector_cc_pair_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )

    first = _finding(_report(source))
    second = _finding(_report(reordered))
    assert (second.fingerprint, second.evidence) == (first.fingerprint, first.evidence)
