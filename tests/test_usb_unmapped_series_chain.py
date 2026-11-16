"""Review-only coverage for exact USB paths with multiple resistor stages."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.usb_data_path_support import usb_data_map
from tests.usb_peer_reference_support import lint_report, usb_peer_netlist, usb_peer_series_netlist
from tests.usb_series_chain_support import two_stage_usb_series_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.usb_unmapped_series_chain"


def _positive_two_stage_netlist() -> NetlistContract:
    source = two_stage_usb_series_netlist()
    components = {
        reference: item for reference, item in source.components.items() if reference != "R4"
    }
    symbols = {
        reference: item for reference, item in source.component_symbols.items() if reference != "R4"
    }
    pin_numbers = {
        reference: item
        for reference, item in source.component_pin_numbers.items()
        if reference != "R4"
    }
    pin_types = {
        pin: item for pin, item in source.pin_electrical_types.items() if not pin.startswith("R4.")
    }
    pin_functions = {
        pin: item for pin, item in source.pin_functions.items() if not pin.startswith("R4.")
    }
    nets = {
        name: pins for name, pins in source.nets.items() if name not in {"USB_DM_MID", "USB_DM_PHY"}
    }
    nets["USB_DM"] = ("J1.2", "R2.1")
    nets["USB_DM_PHY"] = ("R2.2", "U1.2")
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "pin_electrical_types": pin_types,
            "pin_functions": pin_functions,
            "nets": nets,
        }
    )


def _finding(report):
    return next(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_stage_usb_data_paths_request_map_coverage() -> None:
    report = lint_report(two_stage_usb_series_netlist(), path_map=None)
    finding = _finding(report)

    assert finding.mode == "review"
    assert finding.subject == "J1 / U1: unmapped USB multi-stage series chain"
    assert finding.evidence["USB_D+_path"] == (
        "R1 27R Device:R Synthetic:0603: R1.1 on USB_DP -> R1.2 on USB_DP_MID",
        "R3 33R Device:R Synthetic:0603: R3.1 on USB_DP_MID -> R3.2 on USB_DP_PHY",
    )
    assert finding.evidence["USB_D-_path"] == (
        "R2 27R Device:R Synthetic:0603: R2.1 on USB_DM -> R2.2 on USB_DM_MID",
        "R4 33R Device:R Synthetic:0603: R4.1 on USB_DM_MID -> R4.2 on USB_DM_PHY",
    )
    assert "current map schema cannot express multiple stages" in finding.message
    assert "does not establish resistor suitability" in finding.message

    mixed_report = lint_report(_positive_two_stage_netlist(), path_map=None)
    mixed = _finding(mixed_report)
    assert len(mixed.evidence["USB_D+_path"]) == 2
    assert len(mixed.evidence["USB_D-_path"]) == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_direct_and_single_resistor_paths_are_controls() -> None:
    direct = usb_peer_netlist(connector_reference_net="GND", phy_reference_net="GND")
    single_stage = usb_peer_series_netlist(connector_reference_net="GND", phy_reference_net="GND")

    assert not any(item.rule_id == RULE_ID for item in lint_report(direct, path_map=None).findings)
    assert not any(
        item.rule_id == RULE_ID for item in lint_report(single_stage, path_map=None).findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_incomplete_and_branched_chains_are_outside_scope() -> None:
    source = two_stage_usb_series_netlist()
    dnp = source.model_copy(update={"dnp_components": ("R3",)})
    incomplete = source.model_copy(
        update={"component_pin_numbers": {**source.component_pin_numbers, "R3": ("1",)}}
    )
    components = dict(source.components)
    components["R5"] = components["R1"]
    symbols = {**source.component_symbols, "R5": "Device:R"}
    pin_numbers = {**source.component_pin_numbers, "R5": ("1", "2")}
    pin_types = {
        **source.pin_electrical_types,
        "R5.1": "passive",
        "R5.2": "passive",
    }
    pin_functions = {**source.pin_functions, "R5.1": "~", "R5.2": "~"}
    branched = source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "pin_electrical_types": pin_types,
            "pin_functions": pin_functions,
            "nets": {
                **source.nets,
                "USB_DP_MID": ("R1.2", "R3.1", "R5.1"),
                "USB_DP_BRANCH": ("R5.2",),
            },
        }
    )

    for control in (dnp, incomplete, branched):
        assert not any(
            item.rule_id == RULE_ID for item in lint_report(control, path_map=None).findings
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_matching_endpoint_map_suppresses_duplicate_coverage_prompt() -> None:
    report = lint_report(two_stage_usb_series_netlist(), path_map=usb_data_map())

    assert not any(item.rule_id == RULE_ID for item in report.findings)
    assert any(item.rule_id == "bus.usb_data_path_mismatch" for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_is_configurable_and_exactly_ignorable() -> None:
    source = two_stage_usb_series_netlist()
    default = _finding(lint_report(source, path_map=None))
    blocked = _finding(
        lint_report(
            source,
            path_map=None,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="block",
                reason="This project requires USB series-path coverage",
            ),
        )
    )
    off = _finding(
        lint_report(
            source,
            path_map=None,
            override=DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="off",
                reason="Reviewed outside this project profile",
            ),
        )
    )
    ignored = _finding(
        lint_report(
            source,
            path_map=None,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=default.fingerprint,
                reason="Intentional series chain documented by the project",
            ),
        )
    )

    assert blocked.mode == "block"
    assert off.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_chain_evidence_is_stable_under_native_order_changes() -> None:
    source = two_stage_usb_series_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )

    first = _finding(lint_report(source, path_map=None))
    second = _finding(lint_report(reordered, path_map=None))

    assert (second.fingerprint, second.evidence) == (first.fingerprint, first.evidence)
