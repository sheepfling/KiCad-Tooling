"""Focused pytest coverage for authored I2C pull-up contracts."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.i2c_pullup_contract import i2c_pullup_checks
from kicad_tooling.hwrepo.i2c_pullup_models import (
    I2cPullupAnalysis,
    I2cPullupBusRequirement,
    I2cPullupElectricalWindow,
    I2cPullupInputVoltageLimit,
    I2cPullupLineRequirement,
    I2cPullupSeriesPathRequirement,
    I2cPullupVoltageCompatibilityRequirement,
)
from kicad_tooling.hwrepo.models import ComponentContract, ElectricalCheck, NetlistContract
from tests.electrical_i2c_support import (
    i2c_pullup_array_netlist,
    i2c_pullup_array_requirement,
    i2c_pullup_netlist,
    i2c_pullup_requirement,
    i2c_pullup_voltage_requirement,
    i2c_pullup_window_requirement,
    i2c_series_pullup_netlist,
    i2c_series_pullup_requirement,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _checks(
    specification: I2cPullupAnalysis, observed: NetlistContract
) -> dict[str, ElectricalCheck]:
    return {item.id: item for item in i2c_pullup_checks(specification, observed)}


def test_direct_pullups_check_exact_rail_and_parallel_resistance() -> None:
    checks = _checks(i2c_pullup_requirement(), i2c_pullup_netlist())
    assert checks["i2c-pullup/control/sda"].status == "PASS"
    assert checks["i2c-pullup/control/sda"].observed == 2_350
    assert checks["i2c-pullup/control/scl"].status == "PASS"
    assert checks["i2c-pullup/control/scl"].observed == 4_700

    low = _checks(i2c_pullup_requirement(), i2c_pullup_netlist(sda_values=("1k", "1k")))
    assert low["i2c-pullup/control/sda"].status == "FAIL"
    assert low["i2c-pullup/control/sda"].observed == 500
    assert "R1=1000Ω, R2=1000Ω" in low["i2c-pullup/control/sda"].detail

    wrong_rail = _checks(i2c_pullup_requirement(), i2c_pullup_netlist(scl_rail="+5V"))
    assert wrong_rail["i2c-pullup/control/scl"].status == "FAIL"
    assert "unexpected direct pull-ups to +5V" in wrong_rail["i2c-pullup/control/scl"].detail


def test_electrical_window_checks_authored_sink_current_and_rise_time_bounds() -> None:
    passing = _checks(i2c_pullup_window_requirement(), i2c_series_pullup_netlist())
    minimum_id = "i2c-pullup/series-bus/sda/electrical-window/minimum-sink-resistance"
    maximum_id = "i2c-pullup/series-bus/sda/electrical-window/maximum-rise-resistance"
    assert passing[minimum_id].status == "PASS"
    assert passing[minimum_id].observed == 4_000
    assert "966.667Ω" in passing[minimum_id].detail
    assert passing[maximum_id].status == "PASS"
    assert passing[maximum_id].observed == 5_000
    assert "7081.32Ω" in passing[maximum_id].detail

    boundary = _checks(
        i2c_pullup_window_requirement(
            minimum_ohms=1_000,
            maximum_ohms=5_000,
            maximum_pullup_voltage_v=3.4,
            maximum_bus_capacitance_pf=100.0,
            maximum_rise_time_ns=423.65,
        ),
        i2c_series_pullup_netlist(),
    )
    assert boundary[minimum_id].status == "PASS"
    assert boundary[maximum_id].status == "PASS"

    outside_both_bounds = _checks(
        i2c_pullup_window_requirement(
            minimum_ohms=900,
            maximum_ohms=3_600,
            maximum_bus_capacitance_pf=100.0,
        ),
        i2c_series_pullup_netlist(),
    )
    assert outside_both_bounds[minimum_id].status == "FAIL"
    assert outside_both_bounds[maximum_id].status == "FAIL"


def test_infeasible_electrical_window_is_explicit_for_both_lines() -> None:
    checks = _checks(
        i2c_pullup_window_requirement(
            maximum_pullup_voltage_v=5.0,
            minimum_sink_current_ma=1.0,
            maximum_bus_capacitance_pf=300.0,
            maximum_rise_time_ns=100.0,
        ),
        i2c_series_pullup_netlist(),
    )
    for line in ("sda", "scl"):
        related = [
            item
            for item in checks.values()
            if item.id.startswith(f"i2c-pullup/series-bus/{line}/electrical-window/")
        ]
        assert len(related) == 2
        assert all(item.status == "FAIL" for item in related)
        assert all("derived resistor window is empty" in item.detail for item in related)

    valid_window = i2c_pullup_window_requirement().buses[0].sda.electrical_window
    assert valid_window is not None
    invalid_window = valid_window.model_dump()
    invalid_window["maximum_pullup_voltage_v"] = valid_window.maximum_low_level_voltage_v
    with pytest.raises(ValueError, match="must exceed"):
        I2cPullupElectricalWindow.model_validate(invalid_window)


def test_voltage_compatibility_uses_authored_limits_and_exact_native_pins() -> None:
    observed = i2c_series_pullup_netlist()
    specification = i2c_pullup_voltage_requirement()
    sda_id = "i2c-pullup/series-bus/sda/voltage-compatibility"
    scl_id = "i2c-pullup/series-bus/scl/voltage-compatibility"
    checks = _checks(specification, observed)
    assert checks[sda_id].status == "PASS"
    assert checks[sda_id].observed == 3.3
    assert checks[scl_id].status == "PASS"
    assert "exact native symbol, footprint, pin inventory" in checks[sda_id].detail

    excessive_rail = _checks(i2c_pullup_voltage_requirement(maximum_input_voltage_v=3.2), observed)
    assert excessive_rail[sda_id].status == "FAIL"
    assert "maximum 3.3 V exceeds U1.1 maximum bus voltage 3.2 V" in excessive_rail[sda_id].detail
    assert "Synthetic target datasheet maximum input voltage" in excessive_rail[sda_id].detail

    wrong_nets = {
        net: tuple(pin for pin in pins if pin != "U1.1") for net, pins in observed.nets.items()
    }
    wrong_nets["WRONG_SDA"] = ("U1.1",)
    wrong_net = observed.model_copy(update={"nets": wrong_nets})
    wrong_net_checks = _checks(specification, wrong_net)
    assert wrong_net_checks[sda_id].status == "FAIL"
    assert "U1.1 is assigned to WRONG_SDA; expected only I2C_SDA" in wrong_net_checks[sda_id].detail

    wrong_identity = observed.model_copy(
        update={"component_symbols": {**observed.component_symbols, "U1": "Synthetic:Other"}}
    )
    identity_checks = _checks(specification, wrong_identity)
    assert identity_checks[sda_id].status == "FAIL"
    assert "U1 symbol is Synthetic:Other" in identity_checks[sda_id].detail

    missing_pin = observed.model_copy(
        update={"component_pin_numbers": {**observed.component_pin_numbers, "U1": ("2",)}}
    )
    inventory_checks = _checks(specification, missing_pin)
    assert inventory_checks[sda_id].status == "FAIL"
    assert "U1.1 is absent from the native pin inventory" in inventory_checks[sda_id].detail

    dnp_target = observed.model_copy(update={"dnp_components": ("U1",)})
    dnp_checks = _checks(specification, dnp_target)
    assert dnp_checks[sda_id].status == "FAIL"
    assert "U1 is DNP" in dnp_checks[sda_id].detail

    unconfigured_ids = {
        item.id for item in i2c_pullup_checks(i2c_series_pullup_requirement(), observed)
    }
    assert sda_id not in unconfigured_ids


def test_voltage_compatibility_contract_rejects_duplicate_input_pins() -> None:
    limit = I2cPullupInputVoltageLimit(
        pin="U1.1",
        expected_symbol="Synthetic:I2cTarget",
        expected_footprint="Synthetic:SOIC8",
        limit_kind="absolute_maximum",
        maximum_bus_voltage_v=3.3,
        limit_basis="Synthetic datasheet",
    )
    with pytest.raises(ValueError, match="input pins must be unique"):
        I2cPullupVoltageCompatibilityRequirement(
            input_scope_basis="Synthetic reviewed endpoint inventory",
            maximum_rail_voltage_v=3.3,
            rail_basis="Synthetic rail range",
            input_limits=(limit, limit),
        )


def test_series_path_checks_exact_chain_and_parallel_direct_paths() -> None:
    specification = i2c_series_pullup_requirement()
    observed = i2c_series_pullup_netlist()
    checks = _checks(specification, observed)
    chain_id = "i2c-pullup/series-bus/sda/series/sda-chain"
    assert checks[chain_id].status == "PASS"
    assert checks[chain_id].observed == 4_700
    assert checks["i2c-pullup/series-bus/sda"].status == "PASS"
    assert checks["i2c-pullup/series-bus/sda"].observed == 4_700
    assert checks["i2c-pullup/series-bus/scl"].status == "PASS"

    parallel_data = specification.model_dump()
    parallel_data["buses"][0]["sda"]["minimum_ohms"] = 2_300
    parallel_data["buses"][0]["sda"]["maximum_ohms"] = 2_500
    parallel_specification = I2cPullupAnalysis.model_validate(parallel_data)
    parallel_observed = observed.model_copy(
        update={
            "components": {
                **observed.components,
                "R13": ComponentContract(value="4.7k", footprint="Synthetic:R"),
            },
            "component_symbols": {**observed.component_symbols, "R13": "Device:R"},
            "pin_functions": {**observed.pin_functions, "R13.1": "1", "R13.2": "2"},
            "component_pin_numbers": {**observed.component_pin_numbers, "R13": ("1", "2")},
            "nets": {
                **observed.nets,
                "I2C_SDA": (*observed.nets["I2C_SDA"], "R13.1"),
                "+3V3": (*observed.nets["+3V3"], "R13.2"),
            },
        }
    )
    parallel_checks = _checks(parallel_specification, parallel_observed)
    assert parallel_checks[chain_id].status == "PASS"
    assert parallel_checks["i2c-pullup/series-bus/sda"].status == "PASS"
    assert parallel_checks["i2c-pullup/series-bus/sda"].observed == 2_350


@pytest.mark.parametrize(
    ("faulty_netlist", "expected_detail"),
    (
        pytest.param(
            i2c_series_pullup_netlist(first_value="2k"),
            "R10 is 2000Ω, outside 900–1100Ω",
            id="wrong-resistance",
        ),
        pytest.param(
            i2c_series_pullup_netlist(first_symbol="Device:C"),
            "R10 symbol is Device:C",
            id="wrong-symbol",
        ),
        pytest.param(
            i2c_series_pullup_netlist(second_footprint="Synthetic:WRONG"),
            "R11 footprint is Synthetic:WRONG",
            id="wrong-footprint",
        ),
        pytest.param(
            i2c_series_pullup_netlist(dnp=("R10",)),
            "R10 is DNP",
            id="dnp-resistor",
        ),
        pytest.param(
            i2c_series_pullup_netlist(extra_junction_pin=True),
            "series junction I2C_SDA_CHAIN",
            id="branched-junction",
        ),
    ),
)
def test_series_path_faults_are_localized(
    faulty_netlist: NetlistContract, expected_detail: str
) -> None:
    checks = _checks(i2c_series_pullup_requirement(), faulty_netlist)
    chain_id = "i2c-pullup/series-bus/sda/series/sda-chain"
    assert checks[chain_id].status == "FAIL"
    assert expected_detail in checks[chain_id].detail
    assert checks["i2c-pullup/series-bus/sda"].status == "FAIL"


def test_series_path_requires_complete_native_pin_inventory() -> None:
    observed = i2c_series_pullup_netlist()
    missing_inventory = observed.model_copy(
        update={
            "component_pin_numbers": {
                ref: numbers
                for ref, numbers in observed.component_pin_numbers.items()
                if ref != "R11"
            }
        }
    )
    checks = _checks(i2c_series_pullup_requirement(), missing_inventory)
    chain_id = "i2c-pullup/series-bus/sda/series/sda-chain"
    assert checks[chain_id].status == "FAIL"
    assert "R11 native pin inventory is missing" in checks[chain_id].detail


def test_series_path_contract_rejects_incomplete_and_unbound_maps() -> None:
    path_data = i2c_series_pullup_requirement().series_paths[0].model_dump()
    path_data["resistors"][1]["from_net"] = "WRONG_MIDPOINT"
    with pytest.raises(ValueError, match="ordered path"):
        I2cPullupSeriesPathRequirement.model_validate(path_data)

    requirement_data = i2c_series_pullup_requirement().model_dump()
    requirement_data["buses"][0]["sda"]["net"] = "ANOTHER_SDA"
    with pytest.raises(ValueError, match="match a configured signal/rail pair"):
        I2cPullupAnalysis.model_validate(requirement_data)


def test_direct_pullups_exclude_dnp_parts_and_unmapped_resistor_arrays() -> None:
    dnp_checks = _checks(i2c_pullup_requirement(), i2c_pullup_netlist(dnp=("R2",)))
    assert dnp_checks["i2c-pullup/control/sda"].status == "FAIL"
    assert dnp_checks["i2c-pullup/control/sda"].observed == 4_700
    assert "R2" not in dnp_checks["i2c-pullup/control/sda"].detail

    array_checks = _checks(
        i2c_pullup_requirement(),
        i2c_pullup_netlist(sda_values=("4.7k",), array_reference="R1"),
    )
    assert array_checks["i2c-pullup/control/sda"].status == "FAIL"
    assert array_checks["i2c-pullup/control/sda"].observed is None


def test_resistor_array_requires_a_complete_explicit_channel_map() -> None:
    specification = i2c_pullup_array_requirement()
    valid = _checks(specification, i2c_pullup_array_netlist())
    assert valid["i2c-pullup/array-bus/sda"].status == "PASS"
    assert valid["i2c-pullup/array-bus/scl"].status == "PASS"
    assert valid["i2c-pullup/array-bus/sda"].observed == 4_700
    assert "RN1.sda=4700Ω" in valid["i2c-pullup/array-bus/sda"].detail

    extra_pin = i2c_pullup_array_netlist(extra_pin=True)
    incomplete = _checks(specification, extra_pin)
    assert incomplete["i2c-pullup/array-bus/sda"].status == "FAIL"
    assert (
        "unreviewed symbol pins outside the array map"
        in incomplete["i2c-pullup/array-bus/sda"].detail
    )

    reviewed_unused_pin = i2c_pullup_array_requirement(
        unmapped_pin_reasons={"RN1.5": "Synthetic channel is not used by this board"}
    )
    covered = _checks(reviewed_unused_pin, extra_pin)
    assert covered["i2c-pullup/array-bus/sda"].status == "PASS"


def test_resistor_array_part_identity_is_an_explicit_project_gate() -> None:
    specification = i2c_pullup_array_requirement()
    array = specification.arrays[0]
    legacy = specification.model_copy(
        update={"arrays": (array.model_copy(update={"expected_part_id": None}),)}
    )
    changed_part = i2c_pullup_array_netlist(part_id="SYNTHETIC-ARRAY-10K")

    strict_checks = _checks(specification, changed_part)
    assert strict_checks["i2c-pullup/array-bus/sda"].status == "FAIL"
    assert "PART_ID is SYNTHETIC-ARRAY-10K; expected SYNTHETIC-ARRAY-47K" in (
        strict_checks["i2c-pullup/array-bus/sda"].detail
    )

    legacy_checks = _checks(legacy, changed_part)
    assert legacy_checks["i2c-pullup/array-bus/sda"].status == "PASS"


@pytest.mark.parametrize(
    ("faulty_netlist", "expected_detail"),
    (
        pytest.param(
            i2c_pullup_array_netlist(value="4x10k"),
            "value is 4x10k",
            id="wrong-value",
        ),
        pytest.param(
            i2c_pullup_array_netlist(symbol="Synthetic:OtherArray"),
            "symbol is Synthetic:OtherArray",
            id="wrong-symbol",
        ),
        pytest.param(
            i2c_pullup_array_netlist(footprint="Synthetic:RA8"),
            "footprint is Synthetic:RA8",
            id="wrong-footprint",
        ),
        pytest.param(
            i2c_pullup_array_netlist(part_id="SYNTHETIC-ARRAY-10K"),
            "PART_ID is SYNTHETIC-ARRAY-10K",
            id="wrong-part-id",
        ),
        pytest.param(
            i2c_pullup_array_netlist(part_id=None),
            "PART_ID is missing",
            id="missing-part-id",
        ),
        pytest.param(
            i2c_pullup_array_netlist(sda_signal_net="WRONG_SDA"),
            "expected one pin on I2C_SDA and one on +3V3",
            id="wrong-net",
        ),
        pytest.param(
            i2c_pullup_array_netlist(dnp=("RN1",)),
            "RN1 is DNP",
            id="dnp-array",
        ),
    ),
)
def test_resistor_array_faults_are_reported(
    faulty_netlist: NetlistContract, expected_detail: str
) -> None:
    checks = _checks(i2c_pullup_array_requirement(), faulty_netlist)
    assert checks["i2c-pullup/array-bus/sda"].status == "FAIL"
    assert expected_detail in checks["i2c-pullup/array-bus/sda"].detail


def test_i2c_requirement_rejects_ambiguous_signal_and_range_definitions() -> None:
    with pytest.raises(ValueError, match="distinct signal nets"):
        I2cPullupBusRequirement(
            id="same-line",
            basis="Synthetic invalid contract",
            sda=I2cPullupLineRequirement(
                net="I2C", rail="+3V3", minimum_ohms=1_000, maximum_ohms=10_000
            ),
            scl=I2cPullupLineRequirement(
                net="I2C", rail="+3V3", minimum_ohms=1_000, maximum_ohms=10_000
            ),
        )
    with pytest.raises(ValueError, match="maximum resistance is below its minimum"):
        I2cPullupLineRequirement(
            net="I2C_SDA", rail="+3V3", minimum_ohms=10_000, maximum_ohms=1_000
        )

    conflicting_voltages = i2c_pullup_window_requirement().buses[0].sda.model_dump()
    assert conflicting_voltages["voltage_compatibility"] is not None
    conflicting_voltages["voltage_compatibility"]["maximum_rail_voltage_v"] = 3.45
    with pytest.raises(ValueError, match="rail ceilings must match"):
        I2cPullupLineRequirement.model_validate(conflicting_voltages)
