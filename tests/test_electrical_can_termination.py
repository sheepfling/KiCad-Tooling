"""CAN direct, split, and externally owned termination contract tests."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.bus_heuristics import can_termination_checks
from kicad_tooling.hwrepo.models import (
    CanTerminationAnalysis,
    CanTerminationBusRequirement,
    CanTerminationEndpointRequirement,
    CanTerminationMidpointCapacitorRequirement,
    CanTerminationResistorRequirement,
    ComponentContract,
    ElectricalCheck,
    NetlistContract,
)
from tests.electrical_can_support import (
    can_split_termination_requirement,
    can_termination_netlist,
    can_termination_requirement,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

CanTerminationFault = Literal[
    "missing",
    "wrong-value",
    "dnp",
    "wrong-symbol",
    "wrong-net",
    "missing-inventory",
]


def _checks(
    requirement: CanTerminationAnalysis,
    observed: NetlistContract,
) -> dict[str, ElectricalCheck]:
    return {item.id: item for item in can_termination_checks(requirement, observed)}


def _split_requirement(*, with_midpoint_capacitor: bool = False) -> CanTerminationAnalysis:
    data = can_split_termination_requirement().model_dump(mode="python")
    bus = data["buses"][0]
    bus["high_pins"] = ("U1.1",)
    bus["low_pins"] = ("U1.2",)
    endpoint = bus["endpoints"][0]
    if not with_midpoint_capacitor:
        endpoint.pop("midpoint_capacitor")
    else:
        endpoint["midpoint_capacitor"]["expected_symbol"] = "Device:C"
    return CanTerminationAnalysis.model_validate(data)


def _external_termination_requirement() -> CanTerminationAnalysis:
    return CanTerminationAnalysis(
        basis="Synthetic bus is externally terminated in this assembly",
        buses=(
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Synthetic external termination declaration",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=("U1.1",),
                low_pins=("U1.2",),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="remote",
                        basis="Remote equipment owns this bus-end terminator",
                        topology="external",
                        expected_dnp_resistors=("R9",),
                    ),
                ),
            ),
        ),
    )


def _split_capacitor_fault(fault: CanTerminationFault) -> NetlistContract:
    paths = {
        "R4": ("60R", "CAN_H", "CAN_TERM_MID"),
        "R5": ("60R", "CAN_L", "CAN_TERM_MID"),
    }
    capacitor = ("C1", "100pF", "CAN_TERM_MID", "GND")
    if fault == "missing":
        return can_termination_netlist(paths)
    if fault == "wrong-value":
        return can_termination_netlist(
            paths, midpoint_capacitor=("C1", "120pF", "CAN_TERM_MID", "GND")
        )
    if fault == "dnp":
        return can_termination_netlist(paths, dnp=("C1",), midpoint_capacitor=capacitor)

    observed = can_termination_netlist(paths, midpoint_capacitor=capacitor)
    if fault == "wrong-symbol":
        return observed.model_copy(
            update={
                "component_symbols": {**observed.component_symbols, "C1": "Device:R"},
                "components": {
                    **observed.components,
                    "C1": ComponentContract(value="100pF", footprint="Synthetic:WRONG"),
                },
            }
        )
    if fault == "wrong-net":
        return observed.model_copy(
            update={"nets": {**observed.nets, "GND": (), "OTHER": ("C1.2",)}}
        )
    if fault == "missing-inventory":
        return observed.model_copy(
            update={
                "component_pin_numbers": {
                    reference: numbers
                    for reference, numbers in observed.component_pin_numbers.items()
                    if reference != "C1"
                }
            }
        )
    raise AssertionError(f"Unhandled synthetic fault: {fault}")


def test_direct_can_endpoints_and_signal_pins_pass_the_control() -> None:
    checks = _checks(can_termination_requirement(), can_termination_netlist())

    assert checks["can-termination/fieldbus/local-a"].status == "PASS"
    assert checks["can-termination/fieldbus/local-b"].status == "PASS"
    assert checks["can-termination/fieldbus/unlisted-direct"].status == "PASS"
    assert checks["can-termination/fieldbus/signal-pins"].status == "PASS"


def test_can_signal_pin_faults_are_localized() -> None:
    misassigned_pins = can_termination_netlist().model_copy(
        update={
            "nets": {
                "CAN_H": ("R1.1", "R2.1"),
                "CAN_L": ("U1.2", "R1.2", "R2.2"),
                "OTHER": ("U1.1",),
            }
        }
    )
    misassigned_check = _checks(can_termination_requirement(), misassigned_pins)[
        "can-termination/fieldbus/signal-pins"
    ]
    assert misassigned_check.status == "FAIL"
    assert "U1.1 is assigned to OTHER" in misassigned_check.detail

    stale_check = _checks(can_termination_requirement(high_pin="U9.7"), can_termination_netlist())[
        "can-termination/fieldbus/signal-pins"
    ]
    assert stale_check.status == "FAIL"
    assert "U9.7 is absent" in stale_check.detail


def test_direct_termination_inclusive_resistance_boundaries_pass() -> None:
    observed = can_termination_netlist(
        {"R1": ("108R", "CAN_H", "CAN_L"), "R2": ("132R", "CAN_H", "CAN_L")}
    )

    checks = _checks(can_termination_requirement(), observed)
    assert checks["can-termination/fieldbus/local-a"].status == "PASS"
    assert checks["can-termination/fieldbus/local-b"].status == "PASS"


def test_missing_dnp_and_out_of_range_direct_terminators_fail() -> None:
    requirement = can_termination_requirement()

    missing = _checks(requirement, can_termination_netlist(paths={}))
    assert missing["can-termination/fieldbus/local-a"].status == "FAIL"
    assert missing["can-termination/fieldbus/local-b"].status == "FAIL"

    one_missing = _checks(
        requirement,
        can_termination_netlist(paths={"R1": ("120R", "CAN_H", "CAN_L")}),
    )["can-termination/fieldbus/local-b"]
    assert one_missing.status == "FAIL"
    assert "R2 is absent" in one_missing.detail

    dnp = _checks(requirement, can_termination_netlist(dnp=("R1",)))[
        "can-termination/fieldbus/local-a"
    ]
    assert dnp.status == "FAIL"
    assert "R1 is DNP" in dnp.detail

    low_value = _checks(
        requirement,
        can_termination_netlist(
            {"R1": ("100R", "CAN_H", "CAN_L"), "R2": ("120R", "CAN_H", "CAN_L")}
        ),
    )
    assert low_value["can-termination/fieldbus/local-a"].status == "FAIL"


def test_unlisted_direct_terminator_is_reported() -> None:
    observed = can_termination_netlist(
        {
            "R1": ("120R", "CAN_H", "CAN_L"),
            "R2": ("120R", "CAN_H", "CAN_L"),
            "R3": ("60R", "CAN_H", "CAN_L"),
        }
    )

    check = _checks(can_termination_requirement(), observed)[
        "can-termination/fieldbus/unlisted-direct"
    ]
    assert check.status == "FAIL"
    assert "R3=60Ω" in check.detail


def test_split_termination_requires_both_legs_to_meet_at_one_midpoint() -> None:
    requirement = _split_requirement()
    paths = {
        "R4": ("60R", "CAN_H", "CAN_TERM_MID"),
        "R5": ("60R", "CAN_L", "CAN_TERM_MID"),
    }
    checks = _checks(requirement, can_termination_netlist(paths))

    assert checks["can-termination/fieldbus/local"].status == "PASS"
    assert checks["can-termination/fieldbus/local"].observed == 120
    assert "can-termination/fieldbus/local/midpoint-capacitor" not in checks

    crossed = can_termination_netlist(
        {
            "R4": ("60R", "CAN_H", "CAN_TERM_MID"),
            "R5": ("60R", "CAN_L", "CAN_H"),
        }
    )
    assert _checks(requirement, crossed)["can-termination/fieldbus/local"].status == "FAIL"


@pytest.mark.parametrize("value", ("90pF", "110pF"))
def test_split_midpoint_capacitor_inclusive_value_boundaries_pass(value: str) -> None:
    requirement = _split_requirement(with_midpoint_capacitor=True)
    observed = can_termination_netlist(
        {"R4": ("60R", "CAN_H", "CAN_TERM_MID"), "R5": ("60R", "CAN_L", "CAN_TERM_MID")},
        midpoint_capacitor=("C1", value, "CAN_TERM_MID", "GND"),
    )

    check = _checks(requirement, observed)["can-termination/fieldbus/local/midpoint-capacitor"]
    assert check.status == "PASS"


@pytest.mark.parametrize(
    ("fault", "detail"),
    (
        ("missing", "C1 is absent"),
        ("wrong-value", "outside 90–110pF"),
        ("dnp", "C1 is DNP"),
        ("wrong-symbol", "symbol is Device:R"),
        ("wrong-net", "C1.2 is assigned to OTHER"),
        ("missing-inventory", "C1 native pin inventory is missing"),
    ),
)
def test_split_midpoint_capacitor_faults_fail_with_exact_evidence(
    fault: CanTerminationFault, detail: str
) -> None:
    requirement = _split_requirement(with_midpoint_capacitor=True)
    check = _checks(requirement, _split_capacitor_fault(fault))[
        "can-termination/fieldbus/local/midpoint-capacitor"
    ]

    assert check.status == "FAIL"
    assert detail in check.detail


def test_external_termination_remains_not_applicable_and_checks_dnp_option() -> None:
    requirement = _external_termination_requirement()
    observed = can_termination_netlist({"R9": ("120R", "CAN_H", "CAN_L")}, dnp=("R9",))
    checks = _checks(requirement, observed)

    assert checks["can-termination/fieldbus/remote/external-evidence"].status == "NOT_APPLICABLE"
    assert checks["can-termination/fieldbus/remote/dnp-options"].status == "PASS"

    misassigned = observed.model_copy(
        update={
            "nets": {
                "CAN_H": ("U1.1", "R9.1"),
                "CAN_L": ("U1.2",),
                "OTHER": ("R9.2",),
            }
        }
    )
    assert (
        _checks(requirement, misassigned)["can-termination/fieldbus/remote/dnp-options"].status
        == "FAIL"
    )

    missing_bus_pin = observed.model_copy(
        update={
            "nets": {
                "CAN_H": ("R9.1",),
                "CAN_L": ("U1.2", "R9.2"),
                "OTHER": ("U1.1",),
            }
        }
    )
    missing_checks = _checks(requirement, missing_bus_pin)
    assert missing_checks["can-termination/fieldbus/signal-pins"].status == "FAIL"
    assert missing_checks["can-termination/fieldbus/remote/external-evidence"].status == (
        "NOT_APPLICABLE"
    )

    fitted = can_termination_netlist({"R9": ("120R", "CAN_H", "CAN_L")})
    fitted_checks = _checks(requirement, fitted)
    assert fitted_checks["can-termination/fieldbus/remote/dnp-options"].status == "FAIL"
    assert fitted_checks["can-termination/fieldbus/unlisted-direct"].status == "FAIL"


def test_invalid_can_termination_shapes_are_rejected() -> None:
    with pytest.raises(ValueError, match="Direct CAN termination needs one resistor"):
        CanTerminationEndpointRequirement(
            id="missing-part",
            basis="Invalid synthetic direct requirement",
            topology="direct",
        )

    with pytest.raises(ValueError, match="Only split CAN termination"):
        CanTerminationEndpointRequirement(
            id="direct-with-cap",
            basis="Invalid synthetic direct requirement",
            topology="direct",
            resistors=(
                CanTerminationResistorRequirement(
                    reference="R1",
                    first_net="CAN_H",
                    second_net="CAN_L",
                    minimum_ohms=108,
                    maximum_ohms=132,
                ),
            ),
            midpoint_capacitor=CanTerminationMidpointCapacitorRequirement(
                reference="C1",
                expected_symbol="Device:C",
                expected_footprint="Synthetic:CAP",
                midpoint_pin="C1.1",
                reference_pin="C1.2",
                reference_net="GND",
                minimum_nominal_capacitance_pf=90,
                maximum_nominal_capacitance_pf=110,
            ),
        )

    with pytest.raises(ValueError, match="each bus net to one midpoint"):
        CanTerminationBusRequirement(
            id="fieldbus",
            basis="Invalid synthetic split requirement",
            high_net="CAN_H",
            low_net="CAN_L",
            high_pins=("U1.1",),
            low_pins=("U1.2",),
            endpoints=(
                CanTerminationEndpointRequirement(
                    id="local",
                    basis="Two legs are required",
                    topology="split",
                    midpoint_net="CAN_TERM_MID",
                    resistors=(
                        CanTerminationResistorRequirement(
                            reference="R4",
                            first_net="CAN_H",
                            second_net="CAN_TERM_MID",
                            minimum_ohms=54,
                            maximum_ohms=66,
                        ),
                        CanTerminationResistorRequirement(
                            reference="R5",
                            first_net="CAN_L",
                            second_net="CAN_H",
                            minimum_ohms=54,
                            maximum_ohms=66,
                        ),
                    ),
                ),
            ),
        )
