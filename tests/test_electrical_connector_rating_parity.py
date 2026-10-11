"""CLI/MCP parity for authored connector contact-current limits."""

from __future__ import annotations

import asyncio

import pytest

from tests.electrical_parity_support import parity_harness  # noqa: F401
from tests.test_connector_contact_ratings import contact, netlist, requirement

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_connector_contact_rating_parity(parity) -> None:
    parity.configured()
    observed = netlist()
    parity.install_netlist_contract(
        observed,
        {"connector_contact_ratings": requirement()},
    )
    passed, _, pass_returncode = await parity.analyze_electrical("connector-contact-rating-pass")
    assert pass_returncode == 0
    pass_checks = {row.id: row for row in passed.checks}
    check_id = "connector-contact-rating/host-connector/contact-vbus-contact/utilization"
    assert pass_checks[check_id].status == "PASS"

    parity.install_netlist_contract(
        observed,
        {
            "connector_contact_ratings": requirement(
                contacts=(contact(maximum_expected_current_a=1.61),)
            )
        },
    )
    fault, _, fault_returncode = await parity.analyze_electrical("connector-contact-rating-fault")
    assert fault_returncode == 1
    fault_checks = {row.id: row for row in fault.checks}
    assert fault_checks[check_id].status == "FAIL"


def test_connector_contact_rating_requirement_matches_cli_and_mcp(parity) -> None:
    asyncio.run(_run_connector_contact_rating_parity(parity))
