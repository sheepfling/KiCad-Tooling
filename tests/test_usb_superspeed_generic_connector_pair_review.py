"""Review generic connector contacts on recognized USB SuperSpeed pairs."""

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
    NetlistContract,
    UsbDataPathMap,
)
from kicad_tooling.hwrepo.usb_reference_pin_models import UsbReferencePinRequirement
from kicad_tooling.hwrepo.usb_superspeed_reference_models import (
    UsbSuperspeedReferencePathRequirement,
)
from tests.design_lint_fixtures.usb_superspeed_generic_connector import (
    generic_usb_superspeed_connector_pair_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.usb_superspeed_generic_connector_pair_review"


def _report(
    observed: NetlistContract | None = None,
    *,
    path_map: UsbDataPathMap | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    netlist = observed or generic_usb_superspeed_connector_pair_netlist()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-usb-superspeed-generic-connector",
        observed=netlist,
        netlist_sha256="b" * 64,
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


def _mapped_superspeed_pair(
    *,
    connector_positive_pin: str = "J1.1",
    connector_negative_pin: str = "J1.2",
    positive_net: str = "SS_TX_P",
    negative_net: str = "SS_TX_N",
) -> UsbDataPathMap:
    return UsbDataPathMap(
        basis="Synthetic reviewed connector and USB PHY pinout",
        superspeed_interfaces=(
            UsbSuperspeedReferencePathRequirement(
                id="synthetic-usb-ss-tx-to-rx",
                basis="Synthetic fixture contract",
                connector_reference="J1",
                expected_connector_symbol="Connector_Generic:Conn_01x04",
                expected_connector_footprint="Synthetic:Conn_01x04",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbSuperspeedPhy",
                expected_phy_footprint="Synthetic:QFN",
                connector_signal_family="USB SuperSpeed RX",
                phy_signal_family="USB SuperSpeed TX",
                connector_positive_pin=connector_positive_pin,
                phy_positive_pin="U1.1",
                positive_net=positive_net,
                connector_negative_pin=connector_negative_pin,
                phy_negative_pin="U1.2",
                negative_net=negative_net,
                connector_reference_pins=(UsbReferencePinRequirement(pin="J1.3", net="USB_GND"),),
                phy_reference_pins=(UsbReferencePinRequirement(pin="U1.3", net="USB_GND"),),
                reference_policy="common_net",
            ),
        ),
    )


def _finding(report: DesignLintReport) -> DesignLintFinding:
    return next(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_connector_contacts_on_exact_superspeed_pair_emit_review() -> None:
    report = _report()
    finding = _finding(report)

    assert report.status == "REVIEW"
    assert finding.mode == "review"
    assert finding.subject == "J1 / U1: generic pins match USB SuperSpeed TX pair"
    assert finding.evidence["USB_SuperSpeed_TX_positive_PHY_pin"] == ("U1.1",)
    assert finding.evidence["USB_SuperSpeed_TX_negative_PHY_pin"] == ("U1.2",)
    assert finding.evidence["USB_SuperSpeed_TX_positive_generic_connector_pins"] == ("J1.1",)
    assert finding.evidence["USB_SuperSpeed_TX_negative_generic_connector_pins"] == ("J1.2",)
    assert "does not identify the connector as USB" in finding.message
    assert "determine how power or reference pins should be connected" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_recognized_phy_receive_pair_is_also_reviewable() -> None:
    observed = generic_usb_superspeed_connector_pair_netlist(phy_family="RX")

    finding = _finding(_report(observed))

    assert finding.subject == "J1 / U1: generic pins match USB SuperSpeed RX pair"
    assert finding.evidence["USB_SuperSpeed_RX_positive_net"] == ("SS_RX_P",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_connector_roles_are_outside_the_generic_pin_prompt() -> None:
    observed = generic_usb_superspeed_connector_pair_netlist(
        connector_functions=("SSTX+", "SSTX-", "GND", "VBUS")
    )

    assert not any(item.rule_id == RULE_ID for item in _report(observed).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_pairs_dnp_and_incomplete_pin_inventories_stay_quiet() -> None:
    incomplete_pair = generic_usb_superspeed_connector_pair_netlist(include_negative_contact=False)
    dnp_connector = generic_usb_superspeed_connector_pair_netlist().model_copy(
        update={"dnp_components": ("J1",)}
    )
    dnp_phy = generic_usb_superspeed_connector_pair_netlist().model_copy(
        update={"dnp_components": ("U1",)}
    )
    missing_connector_inventory = generic_usb_superspeed_connector_pair_netlist().model_copy(
        update={"component_pin_numbers": {"U1": ("1", "2", "3", "4")}}
    )
    ambiguous_pair = generic_usb_superspeed_connector_pair_netlist().model_copy(
        update={
            "nets": {
                **generic_usb_superspeed_connector_pair_netlist().nets,
                "OTHER": ("J1.1",),
            }
        }
    )

    for observed in (
        incomplete_pair,
        dnp_connector,
        dnp_phy,
        missing_connector_inventory,
        ambiguous_pair,
    ):
        assert not any(item.rule_id == RULE_ID for item in _report(observed).findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_source_matched_map_suppresses_candidate_and_checks_exact_assignments() -> None:
    report = _report(path_map=_mapped_superspeed_pair())

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert not any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_stale_source_map_remains_a_contract_mismatch() -> None:
    report = _report(path_map=_mapped_superspeed_pair(positive_net="STALE_SS_TX_P"))

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    mismatch = next(
        item for item in report.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert mismatch.subject == "synthetic-usb-ss-tx-to-rx: USB reference path"
    assert "USB SuperSpeed positive or negative pin/net assignments differ from the map" in (
        str(mismatch.evidence)
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_override_and_exact_ignore_remain_available() -> None:
    base = _finding(_report())
    blocked = _finding(
        _report(
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires mapped USB SuperSpeed connector pins",
            )
        )
    )
    off_report = _report(
        override=DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="off",
            reason="This project has no USB SuperSpeed interfaces",
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
    assert blocked.disposition == "OPEN"
    assert _finding(off_report).disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_fingerprint_is_stable_when_netlist_mappings_are_reordered() -> None:
    observed = generic_usb_superspeed_connector_pair_netlist()
    reordered = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )

    first = _finding(_report(observed))
    second = _finding(_report(reordered))
    assert (second.fingerprint, second.evidence) == (first.fingerprint, first.evidence)
