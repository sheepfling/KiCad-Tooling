"""Cross-process determinism for source-land-flash reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.pcb_lint,
    pytest.mark.slow,
]


def test_missing_land_flash_and_routed_copper_control_reports_are_deterministic() -> None:
    reports = hashseed_probe_reports(families=("fabrication_land_flash",))
    fault = reports["fabrication_land_flash_fault"]
    control = reports["fabrication_land_flash_control"]

    assert fault["board_sha256"] == control["board_sha256"]
    assert fault["artifact_sha256"].keys() == control["artifact_sha256"].keys()
    assert (
        fault["artifact_sha256"]["fabrication/board-F_Cu.gbr"]
        != control["artifact_sha256"]["fabrication/board-F_Cu.gbr"]
    )
    for artifact in fault["artifact_sha256"]:
        if artifact != "fabrication/board-F_Cu.gbr":
            assert fault["artifact_sha256"][artifact] == control["artifact_sha256"][artifact]

    assert fault["status"] == "REVIEW"
    assert fault["unsupported_reasons"] == []
    assert [finding["code"] for finding in fault["findings"]] == ["SOURCE_LAND_FLASH_MISSING"]
    assert fault["findings"][0]["contacts"] == ["J1-2"]
    assert fault["findings"][0]["net"] == "SIGNAL"
    assert fault["findings"][0]["location_mm"] == [7.0, -5.0]
    assert fault["findings"][0]["missing_layers"] == ["F.Cu"]

    assert control["status"] == "PASS"
    assert control["findings"] == []
