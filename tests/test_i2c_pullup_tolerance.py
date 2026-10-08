"""Project-authored worst-case tolerance checks for I2C pull-up windows."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_heuristics import i2c_pullup_checks
from kicad_tooling.hwrepo.models import ElectricalCheck, I2cPullupElectricalWindow
from tests.test_electrical import (
    i2c_pullup_netlist,
    i2c_pullup_requirement,
    i2c_pullup_window_requirement,
    i2c_series_pullup_netlist,
)

SDA_MINIMUM = "i2c-pullup/series-bus/sda/electrical-window/minimum-sink-resistance"
SDA_MAXIMUM = "i2c-pullup/series-bus/sda/electrical-window/maximum-rise-resistance"
DIRECT_SDA_MINIMUM = "i2c-pullup/control/sda/electrical-window/minimum-sink-resistance"
DIRECT_SDA_MAXIMUM = "i2c-pullup/control/sda/electrical-window/maximum-rise-resistance"
TOLERANCE_BASIS = "Synthetic worst-case datasheet resistor tolerance"


def _checks(**requirements: float) -> dict[str, ElectricalCheck]:
    specification = i2c_pullup_window_requirement(
        maximum_per_resistor_tolerance_percent=5.0,
        resistor_tolerance_basis=TOLERANCE_BASIS,
        **requirements,
    )
    return {
        check.id: check for check in i2c_pullup_checks(specification, i2c_series_pullup_netlist())
    }


def _direct_checks(**window_requirements: float) -> dict[str, ElectricalCheck]:
    specification = i2c_pullup_requirement()
    window_source = (
        i2c_pullup_window_requirement(
            maximum_per_resistor_tolerance_percent=5.0,
            resistor_tolerance_basis=TOLERANCE_BASIS,
            **window_requirements,
        )
        .buses[0]
        .sda.electrical_window
    )
    assert window_source is not None
    bus = specification.buses[0]
    specification = specification.model_copy(
        update={
            "buses": (
                bus.model_copy(
                    update={
                        "sda": bus.sda.model_copy(update={"electrical_window": window_source}),
                        "scl": bus.scl.model_copy(
                            update={
                                "minimum_ohms": 4_000,
                                "maximum_ohms": 5_000,
                            }
                        ),
                    }
                ),
            )
        }
    )
    return {check.id: check for check in i2c_pullup_checks(specification, i2c_pullup_netlist())}


def test_nominal_window_is_shrunk_by_worst_case_resistor_tolerance() -> None:
    checks = _checks()

    assert checks[SDA_MINIMUM].status == "PASS"
    assert checks[SDA_MINIMUM].observed == 3_800
    assert TOLERANCE_BASIS in checks[SDA_MINIMUM].detail
    assert "conservative minimum is 3800Ω" in checks[SDA_MINIMUM].detail
    assert checks[SDA_MAXIMUM].status == "PASS"
    assert checks[SDA_MAXIMUM].observed == 5_250
    assert "conservative maximum is 5250Ω" in checks[SDA_MAXIMUM].detail


def test_tolerance_bounds_a_parallel_direct_resistor_network() -> None:
    checks = _direct_checks()

    assert checks["i2c-pullup/control/sda"].observed == 2_350
    assert checks["i2c-pullup/control/sda"].status == "PASS"
    assert checks["i2c-pullup/control/scl"].status == "PASS"
    assert (
        checks["i2c-pullup/control/sda/electrical-window/minimum-sink-resistance"].status == "PASS"
    )
    assert (
        checks["i2c-pullup/control/sda/electrical-window/maximum-rise-resistance"].status == "PASS"
    )


@pytest.mark.parametrize(
    ("window_requirements", "expected_minimum", "expected_maximum"),
    [
        ({"minimum_sink_current_ma": 1.32}, "FAIL", "PASS"),
        (
            {"minimum_sink_current_ma": 2.0, "maximum_rise_time_ns": 108.03075},
            "PASS",
            "FAIL",
        ),
    ],
)
def test_tolerance_can_exceed_either_side_of_the_physical_window(
    window_requirements: dict[str, float],
    expected_minimum: str,
    expected_maximum: str,
) -> None:
    checks = _direct_checks(**window_requirements)

    assert checks["i2c-pullup/control/sda"].status == "PASS"
    assert checks["i2c-pullup/control/sda"].observed == 2_350
    assert checks["i2c-pullup/control/scl"].status == "PASS"
    assert checks[DIRECT_SDA_MINIMUM].status == expected_minimum
    assert checks[DIRECT_SDA_MAXIMUM].status == expected_maximum


def test_tolerance_adjusted_resistance_limits_are_inclusive() -> None:
    checks = _checks(
        minimum_ohms=1_000 / 0.95,
        maximum_ohms=5_000 / 1.05,
        maximum_pullup_voltage_v=3.4,
        maximum_bus_capacitance_pf=100.0,
        maximum_rise_time_ns=423.65,
    )

    assert checks[SDA_MINIMUM].status == "PASS"
    assert checks[SDA_MINIMUM].observed == pytest.approx(1_000)
    assert checks[SDA_MAXIMUM].status == "PASS"
    assert checks[SDA_MAXIMUM].observed == pytest.approx(5_000)


@pytest.mark.parametrize(
    "update",
    [
        {"maximum_per_resistor_tolerance_percent": 5.0},
        {"resistor_tolerance_basis": TOLERANCE_BASIS},
        {
            "maximum_per_resistor_tolerance_percent": 100.0,
            "resistor_tolerance_basis": TOLERANCE_BASIS,
        },
    ],
)
def test_tolerance_requires_a_basis_and_a_bounded_percentage(
    update: dict[str, object],
) -> None:
    window = i2c_pullup_window_requirement().buses[0].sda.electrical_window
    assert window is not None

    with pytest.raises(ValueError):
        I2cPullupElectricalWindow.model_validate({**window.model_dump(), **update})
