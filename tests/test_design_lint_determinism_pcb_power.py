"""Pcb Power hash-seed report regressions."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.pcb_lint,
    pytest.mark.power_lint,
]


def test_pcb_and_power_map_reports_remain_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_power",))
    decoupling_fault = reports["pcb_decoupling_distance_fault"]
    assert decoupling_fault["status"] == "REVIEW"
    assert decoupling_fault["pcb_decoupling"]["status"] == "INCOMPLETE"
    assert "pcb.decoupling_proximity" in {
        finding["rule_id"] for finding in decoupling_fault["findings"]
    }
    assert (
        decoupling_fault["pcb_decoupling"]["entries"][0]["candidates"][0]["distance_nm"] == 100001
    )
    decoupling_control = reports["pcb_decoupling_distance_control"]
    assert decoupling_control["status"] == "PASS"
    assert decoupling_control["pcb_decoupling"]["status"] == "COMPLETE"
    assert "pcb.decoupling_proximity" not in {
        finding["rule_id"] for finding in decoupling_control["findings"]
    }
    fault_decoupling_coverage = decoupling_fault["pcb_decoupling"]
    control_decoupling_coverage = decoupling_control["pcb_decoupling"]
    assert fault_decoupling_coverage["map_sha256"] == control_decoupling_coverage["map_sha256"]
    assert (
        fault_decoupling_coverage["snapshot_sha256"]
        != control_decoupling_coverage["snapshot_sha256"]
    )
    reference_plane_fault = reports["pcb_reference_plane_fault"]
    assert reference_plane_fault["status"] == "REVIEW"
    assert reference_plane_fault["pcb_reference_plane"]["status"] == "COMPLETE"
    assert "pcb.reference_plane_coverage" in {
        finding["rule_id"] for finding in reference_plane_fault["findings"]
    }
    reference_measurement = reference_plane_fault["pcb_reference_plane"]["entries"][0]["tracks"][0]
    assert reference_measurement["covered_fraction_numerator"] == 4
    assert reference_measurement["covered_fraction_denominator"] == 5
    reference_plane_control = reports["pcb_reference_plane_control"]
    assert reference_plane_control["status"] == "PASS"
    assert reference_plane_control["pcb_reference_plane"]["status"] == "COMPLETE"
    assert reference_plane_control["findings"] == []
    mapped_power_path_fault = reports["mapped_power_path_fault"]
    assert mapped_power_path_fault["status"] == "REVIEW"
    assert "power.mapped_series_path_mismatch" in {
        finding["rule_id"] for finding in mapped_power_path_fault["findings"]
    }
    power_path_run = next(
        run
        for run in mapped_power_path_fault["mapped_check_runs"]
        if run["rule_id"] == "power.mapped_series_path_mismatch"
    )
    assert power_path_run["status"] == "EVALUATED"
    assert power_path_run["requirement_count"] == 1
    assert power_path_run["finding_count"] == 1
    assert reports["mapped_power_path_control"]["status"] == "PASS"
    assert reports["mapped_power_path_control"]["findings"] == []
    power_sequence_fault = reports["mapped_power_sequence_fault"]
    assert power_sequence_fault["status"] == "REVIEW"
    assert "power.mapped_sequence_dependency_mismatch" in {
        finding["rule_id"] for finding in power_sequence_fault["findings"]
    }
    sequence_run = next(
        run
        for run in power_sequence_fault["mapped_check_runs"]
        if run["rule_id"] == "power.mapped_sequence_dependency_mismatch"
    )
    assert sequence_run["status"] == "EVALUATED"
    assert sequence_run["requirement_count"] == 3
    assert sequence_run["finding_count"] == 1
    assert reports["mapped_power_sequence_control"]["status"] == "PASS"
    assert reports["mapped_power_sequence_control"]["findings"] == []
