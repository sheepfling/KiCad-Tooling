"""CLI/MCP parity for authored digital-peer voltage limits."""

from __future__ import annotations

import asyncio

import pytest

from tests.electrical_parity_support import parity_harness  # noqa: F401
from tests.test_digital_peer_voltages import (
    observed as digital_peer_netlist,
)
from tests.test_digital_peer_voltages import (
    requirement as digital_peer_requirement,
)

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_digital_peer_voltage_parity(parity) -> None:
    parity.configured()
    observed = digital_peer_netlist()
    parity.install_netlist_contract(observed, {"digital_peer_voltages": digital_peer_requirement()})
    passed, _, pass_returncode = await parity.analyze_electrical("digital-peer-pass")
    assert pass_returncode == 0
    pass_checks = {row.id: row for row in passed.checks}
    assert pass_checks["digital-peer-voltage/spi-mosi/compatibility"].status == "PASS"

    parity.install_netlist_contract(
        observed,
        {"digital_peer_voltages": digital_peer_requirement(output_high_maximum_v=5.0)},
    )
    fault, _, fault_returncode = await parity.analyze_electrical("digital-peer-fault")
    assert fault_returncode == 1
    fault_checks = {row.id: row for row in fault.checks}
    assert fault_checks["digital-peer-voltage/spi-mosi/compatibility"].status == "FAIL"


def test_digital_peer_voltage_requirements_match_cli_and_mcp(parity) -> None:
    asyncio.run(_run_digital_peer_voltage_parity(parity))
