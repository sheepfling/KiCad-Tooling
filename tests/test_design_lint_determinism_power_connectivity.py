"""Power source/load connectivity check determinism across Python processes."""

from __future__ import annotations

import pytest
from pydantic import JsonValue

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports
from tests.json_types import JsonObject

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint, pytest.mark.slow]

SOURCE_CHECK_ID = "power-connectivity/supply/source/approved-inputs"
LOAD_CHECK_ID = "power-connectivity/supply/load/load"


def test_authored_power_connectivity_checks_remain_deterministic() -> None:
    reports = hashseed_probe_reports(families=("power_connectivity",))
    source_fault = reports["power_connectivity_source_fault"]
    load_fault = reports["power_connectivity_load_fault"]
    control = reports["power_connectivity_control"]

    assert source_fault["requirements_sha256"] == load_fault["requirements_sha256"]
    assert source_fault["requirements_sha256"] == control["requirements_sha256"]
    assert (
        len(
            {
                source_fault["netlist_sha256"],
                load_fault["netlist_sha256"],
                control["netlist_sha256"],
            }
        )
        == 3
    )

    def checks_by_id(report: JsonObject) -> dict[str, JsonObject]:
        checks: JsonValue = report["checks"]
        assert isinstance(checks, list)
        return {check["id"]: check for check in checks}

    source_checks = checks_by_id(source_fault)
    load_checks = checks_by_id(load_fault)
    control_checks = checks_by_id(control)
    assert (
        set(source_checks)
        == set(load_checks)
        == set(control_checks)
        == {
            SOURCE_CHECK_ID,
            LOAD_CHECK_ID,
        }
    )

    assert source_checks[SOURCE_CHECK_ID]["status"] == "FAIL"
    assert (
        "J40.1 is assigned to WRONG_INPUT; expected VIN_IN"
        in source_checks[SOURCE_CHECK_ID]["detail"]
    )
    assert source_checks[LOAD_CHECK_ID]["status"] == "PASS"

    assert load_checks[SOURCE_CHECK_ID]["status"] == "PASS"
    assert load_checks[LOAD_CHECK_ID]["status"] == "FAIL"
    assert (
        "U40.1 is assigned to WRONG_INPUT; expected VIN_IN" in load_checks[LOAD_CHECK_ID]["detail"]
    )
    assert all(check["status"] == "PASS" for check in control_checks.values())
