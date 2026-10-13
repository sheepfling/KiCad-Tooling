"""CLI/MCP parity for reviewed connector-return requirements."""

from __future__ import annotations

import asyncio

import pytest

from kicad_tooling.hwrepo.models import (
    GroundDomain,
    GroundingAnalysis,
)
from tests.design_lint_fixtures.connector_return_cases import return_case_contracts
from tests.electrical_parity_support import parity_harness  # noqa: F401

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_db9_grounding_requirement_matrix(parity) -> None:
    parity.configured()
    netlists = return_case_contracts()
    all_returns = tuple(f"J{index}.{pin}" for index in range(1, 5) for pin in (7, 9))
    requirements = {
        "common": GroundingAnalysis(
            basis="Synthetic approved DB9 pinout requires all return contacts on one domain",
            domains=(GroundDomain(net="COMMON_RETURN", pins=all_returns),),
        ),
        "isolated": GroundingAnalysis(
            basis="Synthetic approved DB9 pinout requires one isolated domain per connector",
            domains=tuple(
                GroundDomain(net=f"RETURN_PORT_{index}", pins=(f"J{index}.7", f"J{index}.9"))
                for index in range(1, 5)
            ),
        ),
    }
    cases = (
        ("split-against-common", True, "common", "FAIL"),
        ("common-against-common", False, "common", "PASS"),
        ("split-against-isolated", True, "isolated", "PASS"),
        ("common-against-isolated", False, "isolated", "FAIL"),
    )

    for case_id, isolated_returns, requirement_id, expected_status in cases:
        observed = netlists["four-db9-fault" if isolated_returns else "four-db9-control"]
        parity.install_netlist_contract(observed, {"grounding": requirements[requirement_id]})

        cli_report, mcp_report, returncode = await parity.analyze_electrical(f"db9-{case_id}")
        expected_returncode = 0 if expected_status == "PASS" else 1
        assert returncode == expected_returncode
        for report in (cli_report, mcp_report):
            assert report.status == expected_status
            checks = {item.id: item for item in report.checks}
            assert checks["grounding/component-coverage"].status == "PASS"
            if requirement_id == "common":
                assert checks["grounding/COMMON_RETURN"].status == expected_status
            else:
                for index in range(1, 5):
                    assert checks[f"grounding/RETURN_PORT_{index}"].status == expected_status
            if isolated_returns:
                review_status = "FAIL" if requirement_id == "common" else "PASS"
                assert checks["grounding/return-net-review"].status == review_status


def test_db9_grounding_requirement_matrix_matches_cli_and_mcp(parity) -> None:
    asyncio.run(_run_db9_grounding_requirement_matrix(parity))
