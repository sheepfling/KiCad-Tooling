"""CLI/MCP parity for reviewed serial-peer contracts."""

from __future__ import annotations

import asyncio

import pytest

from tests.electrical_parity_support import parity_harness  # noqa: F401
from tests.electrical_serial_support import serial_peer_netlist, serial_peer_requirement

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_serial_peer_requirements(parity) -> None:
    parity.configured()
    requirement = serial_peer_requirement(endpoint_reference="U10", peer_reference="U11")
    observed = serial_peer_netlist(requirement)
    parity.install_netlist_contract(observed, {"serial_peers": requirement})

    passed, _, pass_returncode = await parity.analyze_electrical("serial-peer-pass")
    assert pass_returncode == 0
    pass_checks = {row.id: row for row in passed.checks}
    assert pass_checks["serial/console-link/route/a_tx_to_b_rx"].status == "PASS"
    assert pass_checks["serial/console-link/route/b_tx_to_a_rx"].status == "PASS"
    assert pass_checks["serial/console-link/reference"].status == "PASS"

    voltage_requirement = serial_peer_requirement(peer_output_high_maximum_v=5.0)
    parity.install_netlist_contract(observed, {"serial_peers": voltage_requirement})
    voltage_fault, _, voltage_returncode = await parity.analyze_electrical(
        "serial-voltage-fault"
    )
    assert voltage_returncode == 1
    voltage_checks = {row.id: row for row in voltage_fault.checks}
    assert voltage_checks["serial/console-link/logic-voltage/b_tx_to_a_rx"].status == "FAIL"

    wrong_routes = serial_peer_netlist(requirement, fault="tx-to-tx")
    parity.install_netlist_contract(wrong_routes, {"serial_peers": requirement})
    route_fault, _, route_returncode = await parity.analyze_electrical("serial-peer-fault")
    assert route_returncode == 1
    route_checks = {row.id: row for row in route_fault.checks}
    assert route_checks["serial/console-link/route/a_tx_to_b_rx"].status == "FAIL"
    assert route_checks["serial/console-link/route/b_tx_to_a_rx"].status == "FAIL"


def test_serial_peer_requirements_match_cli_and_mcp(parity) -> None:
    asyncio.run(_run_serial_peer_requirements(parity))


async def _run_serial_bonded_reference(parity) -> None:
    parity.configured()
    requirement = serial_peer_requirement(reference_policy="bonded")

    parity.install_netlist_contract(
        serial_peer_netlist(requirement), {"serial_peers": requirement}
    )
    control, _, control_returncode = await parity.analyze_electrical("serial-bond-control")
    assert control_returncode == 0
    control_checks = {item.id: item for item in control.checks}
    assert control_checks["serial/console-link/reference"].status == "PASS"

    fault_netlist = serial_peer_netlist(requirement, fault="bond-wrong-net")
    parity.install_netlist_contract(fault_netlist, {"serial_peers": requirement})
    fault, _, fault_returncode = await parity.analyze_electrical("serial-bond-fault")
    assert fault_returncode == 1
    reference_check = {item.id: item for item in fault.checks}["serial/console-link/reference"]
    assert reference_check.status == "FAIL"
    assert "R3.2 is on FLOATING_GND; expected GND_B" in reference_check.detail


def test_serial_peer_bonded_reference_matches_cli_and_mcp_for_pass_and_fault(parity) -> None:
    asyncio.run(_run_serial_bonded_reference(parity))
