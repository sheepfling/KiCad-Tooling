"""Focused USB-C CC role and controller contract regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_heuristics import usb_c_checks
from kicad_tooling.hwrepo.electrical import pin_relationship_checks
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    PinConnectivityAnalysis,
    PinRelationshipRule,
)
from tests.electrical_usb_c_support import usb_c_netlist, usb_c_requirement

pytestmark = pytest.mark.interface_lint


def test_source_role_checks_reviewed_cc_vbus_and_protection_assignments() -> None:
    checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), usb_c_netlist())}

    assert checks
    assert all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values())
    assert checks["usb-c/host-port/cc1-attachment"].observed == 56_000


def test_source_role_rejects_unlisted_cc_resistor_and_misassigned_pins() -> None:
    baseline = usb_c_netlist()
    extra_pullup = baseline.model_copy(
        update={
            "components": {
                **baseline.components,
                "R3": ComponentContract(value="56k", footprint="Synthetic:R_0603"),
            },
            "component_symbols": {**baseline.component_symbols, "R3": "Device:R"},
            "component_pin_numbers": {**baseline.component_pin_numbers, "R3": ("1", "2")},
            "pin_functions": {**baseline.pin_functions, "R3.1": "1", "R3.2": "2"},
            "nets": {
                **baseline.nets,
                "CC1": (*baseline.nets["CC1"], "R3.1"),
                "+5V": (*baseline.nets["+5V"], "R3.2"),
            },
        }
    )
    checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), extra_pullup)}
    assert checks["usb-c/host-port/cc1-attachment"].status == "FAIL"
    assert "unlisted fitted resistors" in checks["usb-c/host-port/cc1-attachment"].detail

    wrong_cc = baseline.model_copy(
        update={
            "nets": {
                **{
                    name: tuple(pin for pin in pins if pin != "J1.5")
                    for name, pins in baseline.nets.items()
                },
                "WRONG_CC": ("J1.5",),
            }
        }
    )
    checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), wrong_cc)}
    assert checks["usb-c/host-port/connector-pins"].status == "FAIL"

    dnp = {item.id: item for item in usb_c_checks(usb_c_requirement(), usb_c_netlist(dnp=("R2",)))}
    assert dnp["usb-c/host-port/cc2-attachment"].status == "FAIL"
    assert "DNP" in dnp["usb-c/host-port/cc2-attachment"].detail

    wrong_vbus = baseline.model_copy(
        update={
            "nets": {
                **{name: pins for name, pins in baseline.nets.items() if name != "VBUS_PORT"},
                "VBUS_PORT": (),
                "VBUS_WRONG": ("J1.1",),
            }
        }
    )
    checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), wrong_vbus)}
    assert checks["usb-c/host-port/connector-pins"].status == "FAIL"
    assert "J1.1" in checks["usb-c/host-port/connector-pins"].detail


def test_source_role_checks_exact_protection_pin_and_footprint() -> None:
    baseline = usb_c_netlist()
    wrong_return = baseline.model_copy(
        update={
            "nets": {
                **{
                    name: tuple(pin for pin in pins if pin != "D1.2")
                    for name, pins in baseline.nets.items()
                },
                "WRONG_PROTECTION_RETURN": ("D1.2",),
            }
        }
    )
    checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), wrong_return)}
    assert checks["usb-c/host-port/protection/D1"].status == "FAIL"

    wrong_footprint = usb_c_netlist(footprint="Package_DFN:Wrong")
    checks = {item.id: item for item in usb_c_checks(usb_c_requirement(), wrong_footprint)}
    assert checks["usb-c/host-port/protection/D1"].status == "FAIL"


def test_dual_role_requires_the_reviewed_controller_and_cc_pin_assignments() -> None:
    spec = usb_c_requirement(role="dual_role", controller=True)
    observed = usb_c_netlist(controller=True)
    checks = {item.id: item for item in usb_c_checks(spec, observed)}
    assert all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values())
    assert checks["usb-c/host-port/controller-identity"].status == "PASS"

    wrong_controller_pin = observed.model_copy(
        update={
            "nets": {
                **{
                    name: tuple(pin for pin in pins if pin != "U2.6")
                    for name, pins in observed.nets.items()
                },
                "CC1": (*observed.nets["CC1"], "U2.6"),
            }
        }
    )
    failed = {item.id: item for item in usb_c_checks(spec, wrong_controller_pin)}
    assert failed["usb-c/host-port/cc2-attachment"].status == "FAIL"

    wrong_controller_symbol = observed.model_copy(
        update={
            "component_symbols": {
                **observed.component_symbols,
                "U2": "Synthetic:OtherController",
            }
        }
    )
    identity = {item.id: item for item in usb_c_checks(spec, wrong_controller_symbol)}
    assert identity["usb-c/host-port/controller-identity"].status == "FAIL"


def test_debug_accessory_role_stays_unverified_without_dynamic_evidence() -> None:
    checks = {
        item.id: item
        for item in usb_c_checks(usb_c_requirement(role="debug_accessory"), usb_c_netlist())
    }

    assert checks["usb-c/host-port/role-support"].status == "NOT_RUN"
    assert "not modeled" in checks["usb-c/host-port/role-support"].detail


def test_static_controller_mode_strap_uses_the_shared_pin_connectivity_contract() -> None:
    observed = usb_c_netlist(role="dual_role", controller=True)
    grounded = observed.model_copy(
        update={"nets": {**observed.nets, "GND": (*observed.nets["GND"], "U2.7")}}
    )
    requirement = PinConnectivityAnalysis(
        basis="Synthetic controller datasheet review for a static mode strap",
        rules=(
            PinRelationshipRule(
                id="controller-mode-strap",
                basis="This synthetic controller uses a ground strap for the approved mode",
                topology="common_net",
                pins=("J1.2", "U2.7"),
                net="GND",
            ),
        ),
    )
    assert pin_relationship_checks(requirement, grounded)[0].status == "PASS"

    wrong_mode = grounded.model_copy(
        update={
            "nets": {
                **{
                    net: tuple(pin for pin in pins if pin != "U2.7")
                    for net, pins in grounded.nets.items()
                },
                "+5V": (*grounded.nets.get("+5V", ()), "U2.7"),
            }
        }
    )
    failed = pin_relationship_checks(requirement, wrong_mode)[0]
    assert failed.status == "FAIL"
    assert "U2.7" in failed.detail


def test_sink_role_checks_rd_assignment_to_ground() -> None:
    spec = usb_c_requirement(role="sink")
    observed = usb_c_netlist(role="sink")
    checks = {item.id: item for item in usb_c_checks(spec, observed)}
    assert all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values())
    assert checks["usb-c/host-port/cc1-attachment"].observed == 5_100

    miswired = observed.model_copy(
        update={
            "nets": {
                **{
                    name: tuple(pin for pin in pins if pin != "R1.2")
                    for name, pins in observed.nets.items()
                },
                "+5V": ("R1.2",),
            }
        }
    )
    checks = {item.id: item for item in usb_c_checks(spec, miswired)}
    assert checks["usb-c/host-port/cc1-attachment"].status == "FAIL"
