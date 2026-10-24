"""Project-authored CAN termination maps for multi-channel resistor arrays."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.can_termination_contract import can_termination_checks
from kicad_tooling.hwrepo.can_termination_models import (
    CanTerminationAnalysis,
    CanTerminationBusRequirement,
    CanTerminationEndpointRequirement,
    CanTerminationResistorArrayChannelRequirement,
    CanTerminationResistorArrayRequirement,
)
from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.electrical_analysis_contract_models import ElectricalAnalysisContract
from kicad_tooling.hwrepo.models import ComponentContract, ElectricalCheck, NetlistContract

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _array_requirement(
    channels: tuple[CanTerminationResistorArrayChannelRequirement, ...] | None = None,
) -> CanTerminationAnalysis:
    mapped_channels = channels or (
        CanTerminationResistorArrayChannelRequirement(
            id="high-leg",
            first_pin="RN1.1",
            second_pin="RN1.2",
            first_net="CAN_H",
            second_net="CAN_TERM_MID",
        ),
        CanTerminationResistorArrayChannelRequirement(
            id="low-leg",
            first_pin="RN1.3",
            second_pin="RN1.4",
            first_net="CAN_L",
            second_net="CAN_TERM_MID",
        ),
    )
    return CanTerminationAnalysis(
        basis="Synthetic split network reviewed against its part pin map",
        buses=(
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Synthetic CAN controller interface",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=("U1.1",),
                low_pins=("U1.2",),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="local",
                        basis="Synthetic split termination at the declared endpoint",
                        topology="split",
                        midpoint_net="CAN_TERM_MID",
                        resistor_arrays=(
                            CanTerminationResistorArrayRequirement(
                                reference="RN1",
                                expected_symbol="Synthetic:ResistorArray",
                                expected_footprint="Synthetic:RA4",
                                expected_value="2x60R",
                                expected_part_id="SYNTHETIC-CAN-60R2",
                                basis="Synthetic reviewed symbol and package pin map",
                                channels=mapped_channels,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _array_netlist() -> NetlistContract:
    return NetlistContract(
        components={
            "U1": ComponentContract(value="CAN transceiver", footprint="Synthetic:SOIC8"),
            "RN1": ComponentContract(
                value="2x60R",
                footprint="Synthetic:RA4",
                part_id="SYNTHETIC-CAN-60R2",
            ),
        },
        nets={
            "CAN_H": ("U1.1", "RN1.1"),
            "CAN_L": ("U1.2", "RN1.3"),
            "CAN_TERM_MID": ("RN1.2", "RN1.4"),
        },
        component_symbols={
            "U1": "Synthetic:CanTransceiver",
            "RN1": "Synthetic:ResistorArray",
        },
        pin_functions={
            "U1.1": "CANH",
            "U1.2": "CANL",
            "RN1.1": "high-leg-a",
            "RN1.2": "high-leg-b",
            "RN1.3": "low-leg-a",
            "RN1.4": "low-leg-b",
        },
        component_pin_numbers={"U1": ("1", "2"), "RN1": ("1", "2", "3", "4")},
    )


def _direct_array_requirement() -> CanTerminationAnalysis:
    return CanTerminationAnalysis(
        basis="Synthetic direct array termination reviewed against its part pin map",
        buses=(
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Synthetic CAN controller interface",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=("U1.1",),
                low_pins=("U1.2",),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="local",
                        basis="Synthetic direct termination at the declared endpoint",
                        topology="direct",
                        resistor_arrays=(
                            CanTerminationResistorArrayRequirement(
                                reference="RN1",
                                expected_symbol="Synthetic:ResistorArray",
                                expected_footprint="Synthetic:RA4",
                                expected_value="2x60R",
                                expected_part_id="SYNTHETIC-CAN-60R2",
                                basis="Synthetic reviewed symbol and package pin map",
                                channels=(
                                    CanTerminationResistorArrayChannelRequirement(
                                        id="direct-leg",
                                        first_pin="RN1.1",
                                        second_pin="RN1.2",
                                        first_net="CAN_H",
                                        second_net="CAN_L",
                                    ),
                                ),
                                unmapped_pin_reasons={
                                    "RN1.3": "Unused spare array pin in this direct option",
                                    "RN1.4": "Unused spare array pin in this direct option",
                                },
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _local_check(observed: NetlistContract) -> ElectricalCheck:
    checks = {item.id: item for item in can_termination_checks(_array_requirement(), observed)}
    return checks["can-termination/fieldbus/local"]


def test_mapped_split_array_passes_and_does_not_claim_measured_resistance() -> None:
    check = _local_check(_array_netlist())

    assert check.status == "PASS"
    assert check.observed is None
    assert "RN1.high-leg maps CAN_H/CAN_TERM_MID" in check.detail
    assert "RN1.low-leg maps CAN_L/CAN_TERM_MID" in check.detail
    assert "resistance is not measured" in check.detail


def test_project_array_contract_fixture_parses() -> None:
    fixture = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/can-resistor-array-native/electrical.json"
    )
    contract = read_model(fixture, ElectricalAnalysisContract)

    assert isinstance(contract.can_termination, CanTerminationAnalysis)
    channels = contract.can_termination.buses[0].endpoints[0].resistor_arrays[0].channels
    assert tuple(item.id for item in channels) == ("high-leg", "low-leg")


def test_direct_array_path_is_not_reported_as_an_unlisted_direct_resistor() -> None:
    observed = _array_netlist().model_copy(
        update={
            "nets": {
                "CAN_H": ("U1.1", "RN1.1"),
                "CAN_L": ("U1.2", "RN1.2"),
            },
            "component_pin_numbers": {"U1": ("1", "2"), "RN1": ("1", "2", "3", "4")},
        }
    )
    checks = {
        item.id: item for item in can_termination_checks(_direct_array_requirement(), observed)
    }

    assert checks["can-termination/fieldbus/local"].status == "PASS"
    assert checks["can-termination/fieldbus/unlisted-direct"].status == "PASS"


def test_mapped_split_array_pin_net_fault_is_localized() -> None:
    observed = _array_netlist().model_copy(
        update={
            "nets": {
                "CAN_H": ("U1.1",),
                "CAN_L": ("U1.2", "RN1.3"),
                "CAN_TERM_MID": ("RN1.2", "RN1.4"),
                "OTHER": ("RN1.1",),
            }
        }
    )

    check = _local_check(observed)
    assert check.status == "FAIL"
    assert "RN1 channel high-leg" in check.detail
    assert "expected one pin on CAN_H and one on CAN_TERM_MID" in check.detail


@pytest.mark.parametrize(
    ("fault", "detail"),
    (
        ("missing", "RN1 is absent"),
        ("footprint", "footprint is Synthetic:WRONG"),
        ("value", "value is 2x62R"),
        ("part-id", "PART_ID is WRONG"),
        ("symbol", "symbol is Synthetic:WrongArray"),
        ("dnp", "RN1 is DNP"),
        ("missing-inventory", "no native symbol pin inventory"),
        ("extra-inventory", "unreviewed symbol pins"),
    ),
)
def test_array_identity_and_complete_pin_inventory_faults_fail(
    fault: str,
    detail: str,
) -> None:
    observed = _array_netlist()
    if fault == "missing":
        components = dict(observed.components)
        components.pop("RN1")
        observed = observed.model_copy(update={"components": components})
    elif fault == "footprint":
        observed = observed.model_copy(
            update={
                "components": {
                    **observed.components,
                    "RN1": ComponentContract(
                        value="2x60R",
                        footprint="Synthetic:WRONG",
                        part_id="SYNTHETIC-CAN-60R2",
                    ),
                }
            }
        )
    elif fault == "value":
        observed = observed.model_copy(
            update={
                "components": {
                    **observed.components,
                    "RN1": ComponentContract(
                        value="2x62R",
                        footprint="Synthetic:RA4",
                        part_id="SYNTHETIC-CAN-60R2",
                    ),
                }
            }
        )
    elif fault == "part-id":
        observed = observed.model_copy(
            update={
                "components": {
                    **observed.components,
                    "RN1": ComponentContract(
                        value="2x60R", footprint="Synthetic:RA4", part_id="WRONG"
                    ),
                }
            }
        )
    elif fault == "symbol":
        observed = observed.model_copy(
            update={
                "component_symbols": {
                    **observed.component_symbols,
                    "RN1": "Synthetic:WrongArray",
                }
            }
        )
    elif fault == "dnp":
        observed = observed.model_copy(update={"dnp_components": ("RN1",)})
    elif fault == "missing-inventory":
        pins = dict(observed.component_pin_numbers)
        pins.pop("RN1")
        observed = observed.model_copy(update={"component_pin_numbers": pins})
    elif fault == "extra-inventory":
        observed = observed.model_copy(
            update={
                "component_pin_numbers": {
                    **observed.component_pin_numbers,
                    "RN1": ("1", "2", "3", "4", "5"),
                }
            }
        )
    else:
        raise AssertionError(f"Unhandled array fault: {fault}")

    check = _local_check(observed)

    assert check.status == "FAIL"
    assert detail in check.detail


def test_passive_array_channel_pin_reversal_is_valid() -> None:
    observed = _array_netlist().model_copy(
        update={
            "nets": {
                "CAN_H": ("U1.1", "RN1.2"),
                "CAN_L": ("U1.2", "RN1.3"),
                "CAN_TERM_MID": ("RN1.1", "RN1.4"),
            }
        }
    )

    assert _local_check(observed).status == "PASS"


def test_common_midpoint_pin_can_be_shared_only_on_one_net() -> None:
    shared_midpoint = (
        CanTerminationResistorArrayChannelRequirement(
            id="high-leg",
            first_pin="RN1.1",
            second_pin="RN1.2",
            first_net="CAN_H",
            second_net="CAN_TERM_MID",
        ),
        CanTerminationResistorArrayChannelRequirement(
            id="low-leg",
            first_pin="RN1.3",
            second_pin="RN1.2",
            first_net="CAN_L",
            second_net="CAN_TERM_MID",
        ),
    )
    assert _array_requirement(shared_midpoint).buses[0].endpoints[0].resistor_arrays[0]

    conflicting_midpoint = (
        *shared_midpoint[:-1],
        shared_midpoint[-1].model_copy(update={"second_net": "OTHER"}),
    )
    with pytest.raises(ValueError, match="shared CAN resistor-array pin"):
        _array_requirement(conflicting_midpoint)


def test_split_topology_requires_two_total_resistor_channels() -> None:
    one_channel = (
        CanTerminationResistorArrayChannelRequirement(
            id="high-leg",
            first_pin="RN1.1",
            second_pin="RN1.2",
            first_net="CAN_H",
            second_net="CAN_TERM_MID",
        ),
    )

    with pytest.raises(ValueError, match="two resistor paths"):
        _array_requirement(one_channel)
