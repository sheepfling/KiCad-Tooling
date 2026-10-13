"""Exact USB inline-protection and reference-ferrite map regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.reference_bond_models import ReferenceBondRequirement
from kicad_tooling.hwrepo.usb_data_path_models import UsbDataPathMap
from kicad_tooling.hwrepo.usb_data_paths import usb_data_path_mismatches
from kicad_tooling.hwrepo.usb_reference_pin_models import UsbReferencePinRequirement
from tests.usb_data_path_support import lint_report
from tests.usb_peer_inline_path_support import usb_inline_peer_case
from tests.usb_peer_reference_support import RULE_ID as USB_PEER_REFERENCE_RULE_ID

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def inline_ferrite_case(*, fault: str | None = None) -> tuple[NetlistContract, UsbDataPathMap]:
    """Build an exact inline USB map with an optional reference-ferrite fault."""
    observed, path_map = usb_inline_peer_case()
    interface = path_map.interfaces[0]
    bond = ReferenceBondRequirement(
        reference="FB2",
        expected_symbol="Device:FerriteBead",
        expected_footprint="Synthetic:0603",
        expected_value="600R@100MHz",
        side_a_pin="FB2.1",
        side_b_pin="FB2.2",
        side_a_net="USB_GND",
        side_b_net="BOARD_GND",
    )
    interface = interface.model_copy(
        update={
            "connector_reference_pins": (UsbReferencePinRequirement(pin="J1.4", net="USB_GND"),),
            "phy_reference_pins": (UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),),
            "reference_policy": "bonded",
            "reference_bond": bond,
        }
    )
    path_map = path_map.model_copy(update={"interfaces": (interface,)})

    components = dict(observed.components)
    symbols = dict(observed.component_symbols)
    pin_numbers = dict(observed.component_pin_numbers)
    pin_functions = dict(observed.pin_functions)
    electrical_types = dict(observed.pin_electrical_types)
    nets = dict(observed.nets)
    dnp_components = ()
    if fault != "missing":
        components["FB2"] = ComponentContract(value="600R@100MHz", footprint="Synthetic:0603")
        symbols["FB2"] = "Device:FerriteBead"
        pin_numbers["FB2"] = ("1", "2")
        pin_functions.update({"FB2.1": "~", "FB2.2": "~"})
        electrical_types.update({"FB2.1": "passive", "FB2.2": "passive"})
        nets["USB_GND"] = (*nets["USB_GND"], "FB2.1")
        if fault == "wrong-net":
            nets["FLOATING_GND"] = ("FB2.2",)
        else:
            nets["BOARD_GND"] = (*nets["BOARD_GND"], "FB2.2")
        if fault == "DNP":
            dnp_components = ("FB2",)

    observed = observed.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "pin_functions": pin_functions,
            "pin_electrical_types": electrical_types,
            "nets": nets,
            "dnp_components": dnp_components,
        }
    )
    return observed, path_map


def test_exact_inline_protection_and_reference_ferrite_map_is_a_valid_control() -> None:
    observed, path_map = inline_ferrite_case()
    report = lint_report(observed, path_map)

    assert usb_data_path_mismatches(path_map, observed) == ()
    assert "bus.usb_data_path_mismatch" not in {item.rule_id for item in report.findings}
    assert USB_PEER_REFERENCE_RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.parametrize(
    ("fault", "expected_issue"),
    (
        ("missing", "FB2 is absent or ambiguous"),
        ("wrong-net", "FB2.2 is on FLOATING_GND; expected BOARD_GND"),
        ("DNP", "FB2 is marked DNP"),
    ),
    ids=("missing-ferrite", "miswired-ferrite", "dnp-ferrite"),
)
def test_inline_reference_ferrite_faults_report_on_the_exact_map(
    fault: str, expected_issue: str
) -> None:
    observed, path_map = inline_ferrite_case(fault=fault)
    mismatches = usb_data_path_mismatches(path_map, observed)
    report = lint_report(observed, path_map)

    assert tuple(item.line for item in mismatches) == ("reference",)
    assert any(expected_issue in issue for issue in mismatches[0].issues)
    path_findings = [
        item for item in report.findings if item.rule_id == "bus.usb_data_path_mismatch"
    ]
    assert len(path_findings) == 1
    assert path_findings[0].subject == "usb-protected-port-1: USB reference path"
    assert USB_PEER_REFERENCE_RULE_ID not in {item.rule_id for item in report.findings}
