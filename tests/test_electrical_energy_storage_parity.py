"""CLI/MCP parity for project-authored energy-storage hold-up checks."""

from __future__ import annotations

import asyncio

import pytest

from tests.electrical_parity_support import parity_harness  # noqa: F401
from tests.test_energy_storage_hold_up import netlist, requirement

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.power_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_energy_storage_parity(parity) -> None:
    parity.configured()
    observed = netlist()
    parity.install_netlist_contract(observed, {"energy_storage": requirement()})
    passed, _, pass_returncode = await parity.analyze_electrical("energy-storage-pass")
    assert pass_returncode == 0
    pass_checks = {row.id: row for row in passed.checks}
    assert pass_checks["energy-storage/controller-rail-hold-up/hold-up"].status == "PASS"

    parity.install_netlist_contract(
        observed,
        {"energy_storage": requirement(minimum_hold_up_time_s=0.6)},
    )
    fault, _, fault_returncode = await parity.analyze_electrical("energy-storage-fault")
    assert fault_returncode == 1
    fault_checks = {row.id: row for row in fault.checks}
    assert fault_checks["energy-storage/controller-rail-hold-up/hold-up"].status == "FAIL"


def test_energy_storage_requirement_matches_cli_and_mcp(parity) -> None:
    asyncio.run(_run_energy_storage_parity(parity))
