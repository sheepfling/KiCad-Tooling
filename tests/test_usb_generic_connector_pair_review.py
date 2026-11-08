"""Review generic connector contacts sharing a recognized USB PHY data pair."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    UsbDataInterfaceRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
    UsbReferencePinRequirement,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.usb_generic_connector_pair import (
    generic_usb_connector_pair_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.usb_generic_connector_phy_pair_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    path_map: UsbDataPathMap | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    netlist: NetlistContract = observed or generic_usb_connector_pair_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-usb-generic-connector",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    return evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(
            usb_data_path_map=path_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )


def _finding(report: DesignLintReport) -> DesignLintFinding:
    return next(item for item in report.findings if item.rule_id == RULE_ID)


def _mapped_generic_usb_pair() -> UsbDataPathMap:
    return UsbDataPathMap(
        basis="Synthetic approved generic connector pinout and USB PHY assignment",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="synthetic-j2-usb-port-1",
                basis="Synthetic fixture interface contract",
                connector_reference="J2",
                expected_connector_symbol="Connector_Generic:Conn_01x04",
                expected_connector_footprint="Synthetic:Conn_01x04",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbHub",
                expected_phy_footprint="Synthetic:QFN",
                data_port_group="1",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J2.2",
                    phy_pin="U1.1",
                    connector_net="USB_DP",
                    phy_net="USB_DP",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J2.3",
                    phy_pin="U1.2",
                    connector_net="USB_DM",
                    phy_net="USB_DM",
                    topology="direct",
                ),
                connector_reference_pins=(UsbReferencePinRequirement(pin="J2.4", net="BOARD_GND"),),
                phy_reference_pins=(UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),),
                reference_policy="common_net",
            ),
        ),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_connector_pair_emits_bounded_port_review() -> None:
    finding = _finding(_report())

    assert finding.mode == "review"
    assert finding.subject == "J2 / U1: generic pins match USB data nets port 1"
    assert finding.evidence["USB_D+_generic_connector_pins"] == ("J2.2",)
    assert finding.evidence["USB_D-_generic_connector_pins"] == ("J2.3",)
    assert finding.evidence["USB_port_group"] == ("1",)
    assert "does not identify the connector as USB" in finding.message
    assert "determine how power or reference pins should be connected" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_reports_open_vbus_and_board_ground_contact() -> None:
    observed = generic_usb_connector_pair_netlist()
    changed_nets = {
        net: tuple(pin for pin in pins if pin != "J2.1") for net, pins in observed.nets.items()
    }
    changed_nets = {net: pins for net, pins in changed_nets.items() if pins}
    opened_vbus = observed.model_copy(
        update={
            "nets": changed_nets,
            "pin_functions": {**observed.pin_functions, "J2.1": "VBUS"},
        }
    )
    finding = _finding(_report(opened_vbus))

    assert finding.evidence["other_connector_contacts"] == (
        "J2.1 function=VBUS nets=unassigned",
        "J2.4 function=Pin_4 nets=BOARD_GND",
    )
    assert finding.fingerprint != _finding(_report()).fingerprint


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_explicit_connector_roles_are_outside_the_generic_pin_prompt() -> None:
    observed = generic_usb_connector_pair_netlist(connector_functions=("VBUS", "D+", "D-", "GND"))

    assert not any(item.rule_id == RULE_ID for item in _report(observed).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_pair_dnp_and_missing_pin_inventory_are_quiet() -> None:
    incomplete_pair = generic_usb_connector_pair_netlist(include_negative_contact=False)
    dnp = generic_usb_connector_pair_netlist().model_copy(update={"dnp_components": ("J2",)})
    missing_inventory = generic_usb_connector_pair_netlist().model_copy(
        update={"component_pin_numbers": {"U1": ("1", "2", "3", "4")}}
    )

    for observed in (incomplete_pair, dnp, missing_inventory):
        assert not any(item.rule_id == RULE_ID for item in _report(observed).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_endpoint_map_resolves_the_generic_connector_review() -> None:
    report = _report(path_map=_mapped_generic_usb_pair())

    assert not any(item.rule_id == RULE_ID for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    base = _finding(_report())
    blocked = _finding(
        _report(
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires every generic USB connector to be mapped",
            )
        )
    )
    off_report = _report(
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="This project has no USB interfaces",
        )
    )
    ignored = _finding(
        _report(
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=base.fingerprint,
                reason="Reviewed as a non-USB accessory connector",
            )
        )
    )

    assert blocked.mode == "block"
    assert _finding(off_report).disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_report_is_stable_when_netlist_mappings_are_reordered() -> None:
    observed = generic_usb_connector_pair_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )

    first = _finding(_report(observed))
    second = _finding(_report(reordered))
    assert (second.fingerprint, second.evidence) == (first.fingerprint, first.evidence)
