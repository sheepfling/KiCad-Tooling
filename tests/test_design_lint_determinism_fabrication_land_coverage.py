"""Cross-process determinism for fabrication land-coverage reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.pcb_lint,
    pytest.mark.slow,
]


def test_land_coverage_fault_and_control_reports_are_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("fabrication_land_coverage",))
    fault = reports["fabrication_land_coverage_fault"]
    control = reports["fabrication_land_coverage_control"]

    assert fault["board_sha256"] != control["board_sha256"]
    assert fault["artifact_sha256"].keys() == control["artifact_sha256"].keys()
    assert (
        fault["artifact_sha256"]["fabrication/board.d356"]
        != control["artifact_sha256"]["fabrication/board.d356"]
    )
    for artifact in fault["artifact_sha256"]:
        if artifact != "fabrication/board.d356":
            assert fault["artifact_sha256"][artifact] == control["artifact_sha256"][artifact]

    assert fault["status"] == "REVIEW"
    assert fault["unsupported_reasons"] == []
    assert [finding["code"] for finding in fault["findings"]] == ["SOURCE_LAND_GEOMETRY_UNREVIEWED"]
    assert fault["findings"][0]["contacts"] == ["J1-2"]
    assert fault["findings"][0]["land_coverage_evidence"]["reason"] == ("unsupported_pad_shape")

    assert control["status"] == "PASS"
    assert control["findings"] == []
