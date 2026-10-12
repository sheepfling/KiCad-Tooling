"""CLI/MCP parity for authored component voltage and power limits."""

from __future__ import annotations

import asyncio

import pytest

from kicad_tooling.hwrepo.mosfet_stress_models import (
    MosfetOperatingState,
    MosfetVoltageInterval,
)
from tests.electrical_parity_support import parity_harness  # noqa: F401
from tests.test_component_power_ratings import (
    netlist as component_power_netlist,
)
from tests.test_component_power_ratings import (
    requirement as component_power_requirement,
)
from tests.test_component_voltage_ratings import (
    netlist as component_voltage_netlist,
)
from tests.test_component_voltage_ratings import (
    requirement as component_voltage_requirement,
)
from tests.test_mosfet_stress import multi_device_netlist, multi_device_requirement

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_component_voltage_rating_parity(parity) -> None:
    parity.configured()
    observed = component_voltage_netlist()
    parity.install_netlist_contract(
        observed,
        {"component_voltage_ratings": component_voltage_requirement()},
    )
    passed, _, pass_returncode = await parity.analyze_electrical("component-rating-pass")
    assert pass_returncode == 0
    pass_checks = {row.id: row for row in passed.checks}
    assert pass_checks["component-voltage-rating/input-capacitor/utilization"].status == "PASS"

    parity.install_netlist_contract(
        observed,
        {
            "component_voltage_ratings": component_voltage_requirement(
                maximum_expected_voltage_v=15.0
            )
        },
    )
    fault, _, fault_returncode = await parity.analyze_electrical("component-rating-fault")
    assert fault_returncode == 1
    fault_checks = {row.id: row for row in fault.checks}
    assert fault_checks["component-voltage-rating/input-capacitor/utilization"].status == "FAIL"


def test_component_voltage_rating_requirement_matches_cli_and_mcp(parity) -> None:
    asyncio.run(_run_component_voltage_rating_parity(parity))


async def _run_mosfet_stress_parity(parity) -> None:
    parity.configured()
    observed = multi_device_netlist()
    requirement = multi_device_requirement()
    parity.install_netlist_contract(observed, {"mosfet_stress": requirement})

    passed, _, pass_returncode = await parity.analyze_electrical("mosfet-stress-pass")
    assert pass_returncode == 0
    pass_checks = {row.id: row for row in passed.checks}
    for reference in ("q1", "q2"):
        assert pass_checks[f"mosfet-stress/switch-{reference}/state-on/vds"].status == "PASS"
        assert pass_checks[f"mosfet-stress/switch-{reference}/state-on/vgs"].status == "PASS"

    on_state = MosfetOperatingState(
        id="on",
        net_potentials={
            **requirement.states[1].net_potentials,
            "D_NET": MosfetVoltageInterval(minimum_v=80.0, maximum_v=80.0),
            "G_NET": MosfetVoltageInterval(minimum_v=25.0, maximum_v=25.0),
            "S_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
        },
    )
    stressed = requirement.model_copy(update={"states": (requirement.states[0], on_state)})
    parity.install_netlist_contract(observed, {"mosfet_stress": stressed})
    fault, _, fault_returncode = await parity.analyze_electrical("mosfet-stress-fault")
    assert fault_returncode == 1
    fault_checks = {row.id: row for row in fault.checks}
    assert fault_checks["mosfet-stress/switch-q1/state-on/vds"].status == "FAIL"
    assert fault_checks["mosfet-stress/switch-q1/state-on/vgs"].status == "FAIL"
    assert fault_checks["mosfet-stress/switch-q2/state-on/vds"].status == "PASS"
    assert fault_checks["mosfet-stress/switch-q2/state-on/vgs"].status == "PASS"


def test_mosfet_state_stress_requirement_matches_cli_and_mcp(parity) -> None:
    asyncio.run(_run_mosfet_stress_parity(parity))


async def _run_component_power_rating_parity(parity) -> None:
    parity.configured()
    observed = component_power_netlist()
    parity.install_netlist_contract(
        observed,
        {"component_power_ratings": component_power_requirement()},
    )
    passed, _, pass_returncode = await parity.analyze_electrical("component-power-rating-pass")
    assert pass_returncode == 0
    pass_checks = {row.id: row for row in passed.checks}
    assert pass_checks["component-power-rating/sense-resistor/utilization"].status == "PASS"

    parity.install_netlist_contract(
        observed,
        {"component_power_ratings": component_power_requirement(maximum_expected_power_w=0.21)},
    )
    fault, _, fault_returncode = await parity.analyze_electrical("component-power-rating-fault")
    assert fault_returncode == 1
    fault_checks = {row.id: row for row in fault.checks}
    assert fault_checks["component-power-rating/sense-resistor/utilization"].status == "FAIL"


def test_component_power_rating_requirement_matches_cli_and_mcp(parity) -> None:
    asyncio.run(_run_component_power_rating_parity(parity))
