"""Focused USB-C VBUS capacitance and source-map contract regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.analysis_state_models import AnalysisPending
from kicad_tooling.hwrepo.bus_heuristics import usb_c_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    NetlistContract,
)
from kicad_tooling.hwrepo.usb_c_models import UsbCAnalysis
from tests.electrical_usb_c_support import usb_c_netlist, usb_c_requirement

pytestmark = [pytest.mark.interface_lint, pytest.mark.power_lint]


def test_port_side_capacitance_passes_exact_reviewed_identity_and_range() -> None:
    spec = usb_c_requirement(vbus_capacitance=True)
    checks = {item.id: item for item in usb_c_checks(spec, usb_c_netlist())}
    check_id = "usb-c/host-port/vbus-capacitance"

    assert checks[check_id].status == "PASS"
    assert checks[check_id].observed == 4_700
    assert checks[check_id].unit == "nF"
    assert "project-authored" in checks[check_id].detail


def _capacitance_faults(baseline: NetlistContract) -> tuple[tuple[str, NetlistContract, str], ...]:
    wrong_symbol = baseline.model_copy(
        update={"component_symbols": {**baseline.component_symbols, "C1": "Device:R"}}
    )
    wrong_footprint = baseline.model_copy(
        update={
            "components": {
                **baseline.components,
                "C1": ComponentContract(value="4.7uF", footprint="Synthetic:C_WRONG"),
            }
        }
    )
    wrong_pin_inventory = baseline.model_copy(
        update={"component_pin_numbers": {**baseline.component_pin_numbers, "C1": ("1", "3")}}
    )
    under_value = baseline.model_copy(
        update={
            "components": {
                **baseline.components,
                "C1": ComponentContract(value="2.2uF", footprint="Synthetic:C_0603"),
            }
        }
    )
    missing_capacitor = baseline.model_copy(
        update={
            "components": {key: value for key, value in baseline.components.items() if key != "C1"},
            "component_symbols": {
                key: value for key, value in baseline.component_symbols.items() if key != "C1"
            },
            "component_pin_numbers": {
                key: value for key, value in baseline.component_pin_numbers.items() if key != "C1"
            },
            "nets": {
                net: tuple(pin for pin in pins if not pin.startswith("C1."))
                for net, pins in baseline.nets.items()
            },
        }
    )
    extra_capacitor = baseline.model_copy(
        update={
            "components": {
                **baseline.components,
                "C2": ComponentContract(value="100nF", footprint="Synthetic:C_0603"),
            },
            "component_symbols": {**baseline.component_symbols, "C2": "Device:C"},
            "component_pin_numbers": {**baseline.component_pin_numbers, "C2": ("1", "2")},
            "nets": {
                **baseline.nets,
                "VBUS_PORT": (*baseline.nets["VBUS_PORT"], "C2.1"),
                "GND": (*baseline.nets["GND"], "C2.2"),
            },
        }
    )
    wrong_net = baseline.model_copy(
        update={
            "nets": {
                **{
                    net: tuple(pin for pin in pins if pin != "C1.1")
                    for net, pins in baseline.nets.items()
                },
                "VBUS_WRONG": ("C1.1",),
            }
        }
    )
    return (
        ("wrong symbol", wrong_symbol, "expected Device:C"),
        ("wrong footprint", wrong_footprint, "expected Synthetic:C_0603"),
        ("wrong native pins", wrong_pin_inventory, "expected ['1', '2']"),
        ("below range", under_value, "2200 nF"),
        ("missing capacitor", missing_capacitor, "C1 is absent"),
        ("extra capacitor", extra_capacitor, "Unmapped capacitor candidate C2"),
        ("wrong net", wrong_net, "C1.1 is assigned"),
        ("DNP", usb_c_netlist(dnp=("C1",)), "DNP"),
    )


@pytest.mark.parametrize("label,fault,expected", _capacitance_faults(usb_c_netlist()))
def test_port_side_capacitance_rejects_inventory_and_value_faults(
    label: str, fault: NetlistContract, expected: str
) -> None:
    checks = {
        item.id: item for item in usb_c_checks(usb_c_requirement(vbus_capacitance=True), fault)
    }

    failed = checks["usb-c/host-port/vbus-capacitance"]
    assert failed.status == "FAIL", label
    assert expected in failed.detail, label


def test_unsupported_capacitance_value_has_no_numeric_observation() -> None:
    baseline = usb_c_netlist()
    unsupported = baseline.model_copy(
        update={
            "components": {
                **baseline.components,
                "C1": ComponentContract(value="unknown", footprint="Synthetic:C_0603"),
            }
        }
    )
    checks = {
        item.id: item
        for item in usb_c_checks(usb_c_requirement(vbus_capacitance=True), unsupported)
    }
    failed = checks["usb-c/host-port/vbus-capacitance"]

    assert failed.status == "FAIL"
    assert failed.observed is None
    assert "not a supported capacitance" in failed.detail


def test_pending_and_not_applicable_capacitance_remain_distinct() -> None:
    spec = usb_c_requirement(vbus_capacitance=True)
    pending_port = spec.ports[0].model_copy(
        update={
            "vbus_capacitance": AnalysisPending(
                mode="pending", reason="Synthetic source-specific capacitance limit is pending."
            )
        }
    )
    pending = {
        item.id: item
        for item in usb_c_checks(
            spec.model_copy(update={"ports": (pending_port,)}), usb_c_netlist()
        )
    }
    not_applicable = {item.id: item for item in usb_c_checks(usb_c_requirement(), usb_c_netlist())}

    check_id = "usb-c/host-port/vbus-capacitance"
    assert pending[check_id].status == "NOT_CONFIGURED"
    assert not_applicable[check_id].status == "NOT_APPLICABLE"


def test_vbus_path_is_opt_in_and_matches_the_declared_ordered_chain() -> None:
    base_checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), usb_c_netlist())}
    assert not any("/vbus-path/" in check_id for check_id in base_checks)

    check_id = "usb-c/host-port/vbus-path/input-path"
    checks = {
        item.id: item
        for item in usb_c_checks(usb_c_requirement(vbus_path=True), usb_c_netlist(vbus_path=True))
    }
    assert checks[check_id].status == "PASS"
    assert "native symbol, footprint, pin inventory" in checks[check_id].detail


def _vbus_path_faults(baseline: NetlistContract) -> tuple[tuple[str, NetlistContract, str], ...]:
    disconnected_pin = baseline.model_copy(
        update={
            "nets": {
                net: tuple(pin for pin in pins if pin != "U3.3")
                for net, pins in baseline.nets.items()
            }
        }
    )
    wrong_symbol = baseline.model_copy(
        update={"component_symbols": {**baseline.component_symbols, "F1": "Device:DifferentPart"}}
    )
    wrong_footprint = baseline.model_copy(
        update={
            "components": {
                **baseline.components,
                "U3": ComponentContract(
                    value="Synthetic load switch", footprint="Package_DFN:Wrong"
                ),
            }
        }
    )
    missing_pin_inventory = baseline.model_copy(
        update={
            "component_pin_numbers": {
                reference: numbers
                for reference, numbers in baseline.component_pin_numbers.items()
                if reference != "F1"
            }
        }
    )
    missing_component = baseline.model_copy(
        update={
            "components": {
                reference: component
                for reference, component in baseline.components.items()
                if reference != "F1"
            }
        }
    )
    return (
        ("disconnected mapped pin", disconnected_pin, "U3.3"),
        ("wrong symbol", wrong_symbol, "expected Device:Fuse"),
        ("wrong footprint", wrong_footprint, "expected Package_DFN:DFN-6"),
        ("unfitted fuse", usb_c_netlist(vbus_path=True, dnp=("F1",)), "DNP"),
        ("missing pin inventory", missing_pin_inventory, "F1 native pin inventory is missing"),
        ("missing component", missing_component, "F1 is absent"),
    )


@pytest.mark.parametrize("label,fault,expected", _vbus_path_faults(usb_c_netlist(vbus_path=True)))
def test_vbus_path_rejects_stale_identity_inventory_and_assignment(
    label: str, fault: NetlistContract, expected: str
) -> None:
    checks = {item.id: item for item in usb_c_checks(usb_c_requirement(vbus_path=True), fault)}

    failed = checks["usb-c/host-port/vbus-path/input-path"]
    assert failed.status == "FAIL", label
    assert expected in failed.detail, label


def test_vbus_path_contract_rejects_discontinuous_or_unmapped_chains() -> None:
    raw = usb_c_requirement(vbus_path=True).model_dump(mode="python")
    path = raw["ports"][0]["vbus_path"]
    path["elements"][1]["port_side_net"] = "VBUS_WRONG"
    path["elements"][1]["pin_assignments"] = tuple(
        {**assignment, "net": "VBUS_WRONG"} if assignment["pin"] in {"U3.1", "U3.2"} else assignment
        for assignment in path["elements"][1]["pin_assignments"]
    )
    with pytest.raises(ValueError, match="ordered net chain"):
        UsbCAnalysis.model_validate(raw)

    raw = usb_c_requirement(vbus_path=True).model_dump(mode="python")
    path = raw["ports"][0]["vbus_path"]
    path["elements"][0]["pin_assignments"][0]["net"] = "VBUS_WRONG"
    with pytest.raises(ValueError, match="port-side pins must map"):
        UsbCAnalysis.model_validate(raw)

    raw = usb_c_requirement(vbus_path=True).model_dump(mode="python")
    raw["ports"][0]["vbus_path"]["board_net"] = "VBUS_WRONG"
    with pytest.raises(ValueError, match="end on the declared board-side net"):
        UsbCAnalysis.model_validate(raw)
