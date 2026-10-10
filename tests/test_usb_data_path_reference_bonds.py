"""Bonded USB reference-path contract fault and control regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.models import UsbDataInterfaceRequirement, UsbReferencePinRequirement
from kicad_tooling.hwrepo.usb_data_paths import usb_data_path_mismatches
from tests.usb_data_path_support import (
    lint_report,
    usb_bonded_reference_map,
    usb_bonded_reference_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.connector_lint,
]


def test_exact_bonded_reference_path_is_a_valid_control() -> None:
    path_map = usb_bonded_reference_map()
    report = lint_report(usb_bonded_reference_netlist(), path_map)
    mismatches = usb_data_path_mismatches(path_map, usb_bonded_reference_netlist())

    assert mismatches == ()
    assert not any(
        item.rule_id in {"bus.usb_data_path_mismatch", "bus.usb_peer_reference_review"}
        for item in report.findings
    )
    run = next(
        item for item in report.mapped_check_runs if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert (run.status, run.requirement_count, run.finding_count) == ("EVALUATED", 1, 0)


@pytest.mark.parametrize(
    ("fault", "expected"),
    (
        ("missing", "R3 is absent"),
        ("wrong-value", "R3 value is 10R"),
        ("wrong-symbol", "R3 symbol is Synthetic:Bond"),
        ("wrong-footprint", "R3 footprint is Synthetic:0805"),
        ("active-pin", "R3.2 is not exported as a passive bond pin"),
        ("DNP", "R3 is marked DNP"),
        ("wrong-net", "R3.2 is on FLOATING_GND"),
    ),
    ids=("missing", "value", "symbol", "footprint", "active-pin", "dnp", "net"),
)
def test_bonded_reference_faults_report_exact_component_and_pin_evidence(
    fault: str, expected: str
) -> None:
    report = lint_report(usb_bonded_reference_netlist(fault=fault), usb_bonded_reference_map())
    findings = [item for item in report.findings if item.rule_id == "bus.usb_data_path_mismatch"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "usb-port-1: USB reference path"
    assert any(expected in issue for issue in finding.evidence["issues"]), finding.evidence[
        "issues"
    ]
    assert finding.evidence["reference_policy"] == ("bonded",)
    assert finding.evidence["reference_bond"] == ("R3",)
    assert finding.evidence["reference_bond_identity"] == ("Device:R; Synthetic:0603; 0R",)
    assert finding.evidence["reference_bond_side_a"] == ("R3.1 on USB_GND",)
    assert finding.evidence["reference_bond_side_b"] == ("R3.2 on BOARD_GND",)


def test_bonded_reference_fault_evidence_is_order_stable() -> None:
    observed = usb_bonded_reference_netlist(fault="wrong-net")
    reordered = observed.model_copy(
        update={
            field: dict(reversed(tuple(getattr(observed, field).items())))
            for field in (
                "components",
                "nets",
                "component_symbols",
                "component_pin_numbers",
                "pin_functions",
                "pin_electrical_types",
            )
        }
    )
    path_map = usb_bonded_reference_map()
    original = next(
        item
        for item in lint_report(observed, path_map).findings
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    reversed_input = next(
        item
        for item in lint_report(reordered, path_map).findings
        if item.rule_id == "bus.usb_data_path_mismatch"
    )
    assert (reversed_input.fingerprint, reversed_input.evidence) == (
        original.fingerprint,
        original.evidence,
    )


def test_bonded_reference_policy_requires_two_distinct_mapped_nets_and_component() -> None:
    interface = usb_bonded_reference_map().interfaces[0]

    def rebuild(**updates: object) -> UsbDataInterfaceRequirement:
        values = interface.model_dump(mode="python")
        values.update(updates)
        return UsbDataInterfaceRequirement.model_validate(values)

    with pytest.raises(ValidationError, match="needs one exact bond component"):
        rebuild(reference_bond=None)
    with pytest.raises(ValidationError, match="needs distinct endpoint nets"):
        rebuild(
            phy_reference_pins=(UsbReferencePinRequirement(pin="U1.3", net="USB_GND"),),
        )
    with pytest.raises(ValidationError, match="must join the mapped connector and PHY nets"):
        bond = interface.reference_bond.model_dump(mode="python")
        bond["side_b_net"] = "UNRELATED_GND"
        rebuild(reference_bond=bond)
    with pytest.raises(ValidationError, match="cannot reuse a data-line series resistor"):
        bond = interface.reference_bond.model_dump(mode="python")
        bond.update(
            {
                "reference": "R1",
                "side_a_pin": "R1.1",
                "side_b_pin": "R1.2",
            }
        )
        rebuild(reference_bond=bond)
