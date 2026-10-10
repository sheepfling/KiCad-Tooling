"""Hash-seed regressions for source-bound PCB return-path checks."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
]


def test_pcb_return_path_fault_and_control_reports_are_source_bound_and_deterministic() -> None:
    reports = hashseed_probe_reports(families=("pcb_return_paths",))
    assert set(reports) == {
        "pcb_return_path_disconnected_fault",
        "pcb_return_path_connected_control",
        "pcb_return_path_split_plane_fault",
        "pcb_return_path_single_plane_control",
        "pcb_return_path_unfitted_bond_fault",
        "pcb_return_path_fitted_bond_control",
        "pcb_return_path_unstitched_layer_fault",
        "pcb_return_path_via_stitch_control",
    }

    fault = reports["pcb_return_path_disconnected_fault"]
    control = reports["pcb_return_path_connected_control"]
    split_plane_fault = reports["pcb_return_path_split_plane_fault"]
    single_plane_control = reports["pcb_return_path_single_plane_control"]
    unfitted_bond_fault = reports["pcb_return_path_unfitted_bond_fault"]
    fitted_bond_control = reports["pcb_return_path_fitted_bond_control"]
    unstitched_layer_fault = reports["pcb_return_path_unstitched_layer_fault"]
    via_stitch_control = reports["pcb_return_path_via_stitch_control"]

    direct_cases = (
        fault,
        control,
        split_plane_fault,
        single_plane_control,
        unstitched_layer_fault,
        via_stitch_control,
    )
    bonded_cases = (unfitted_bond_fault, fitted_bond_control)
    all_cases = (*direct_cases, *bonded_cases)
    assert len({case["requirement_sha256"] for case in direct_cases}) == 1
    assert len({case["requirement_sha256"] for case in bonded_cases}) == 1
    assert fault["requirement_sha256"] != unfitted_bond_fault["requirement_sha256"]
    for case in all_cases:
        assert case["kicad_version"] == "10.0.5"
        assert case["image"] == fault["image"]
        assert case["probe_sha256"] == fault["probe_sha256"]
        assert len({row["id"] for row in case["checks"]}) == len(case["checks"])

    assert fault["board_sha256"] != control["board_sha256"]
    assert fault["snapshot_sha256"] != control["snapshot_sha256"]

    assert fault["status"] == "FAIL"
    failed_checks = {row["id"] for row in fault["checks"] if row["status"] == "FAIL"}
    assert failed_checks == {"pcb-return-paths/pwm-return/connectivity"}

    assert control["status"] == "PASS"
    assert {row["status"] for row in control["checks"]} == {"PASS"}
    assert [row["id"] for row in fault["checks"]] == [row["id"] for row in control["checks"]]

    assert split_plane_fault["board_sha256"] != single_plane_control["board_sha256"]
    assert split_plane_fault["snapshot_sha256"] != single_plane_control["snapshot_sha256"]
    assert split_plane_fault["status"] == "FAIL"
    failed_plane_check = next(
        row
        for row in split_plane_fault["checks"]
        if row["id"] == "pcb-return-paths/pwm-return/connectivity"
    )
    assert failed_plane_check["status"] == "FAIL"
    assert "filled islands=2" in failed_plane_check["detail"]
    assert "connected island indexes=[0]" in failed_plane_check["detail"]
    assert "connected island indexes=[1]" in failed_plane_check["detail"]

    assert single_plane_control["status"] == "PASS"
    assert {row["status"] for row in single_plane_control["checks"]} == {"PASS"}
    assert [row["id"] for row in split_plane_fault["checks"]] == [
        row["id"] for row in single_plane_control["checks"]
    ]

    assert unfitted_bond_fault["board_sha256"] != fitted_bond_control["board_sha256"]
    assert unfitted_bond_fault["snapshot_sha256"] != fitted_bond_control["snapshot_sha256"]
    assert unfitted_bond_fault["status"] == "FAIL"
    failed_bond_checks = {
        row["id"] for row in unfitted_bond_fault["checks"] if row["status"] == "FAIL"
    }
    assert failed_bond_checks == {
        "pcb-return-paths/pwm-return/bond/NT1",
        "pcb-return-paths/pwm-return/connectivity",
    }
    assert fitted_bond_control["status"] == "PASS"
    assert {row["status"] for row in fitted_bond_control["checks"]} == {"PASS"}
    assert [row["id"] for row in unfitted_bond_fault["checks"]] == [
        row["id"] for row in fitted_bond_control["checks"]
    ]

    assert unstitched_layer_fault["board_sha256"] != via_stitch_control["board_sha256"]
    assert unstitched_layer_fault["snapshot_sha256"] != via_stitch_control["snapshot_sha256"]
    assert unstitched_layer_fault["status"] == "FAIL"
    unstitched_check = next(
        row
        for row in unstitched_layer_fault["checks"]
        if row["id"] == "pcb-return-paths/pwm-return/connectivity"
    )
    assert unstitched_check["status"] == "FAIL"
    assert "F.Cu zone" in unstitched_check["detail"]
    assert "B.Cu zone" in unstitched_check["detail"]
    assert "J1.7: no component vias observed" in unstitched_check["detail"]
    assert "J2.7: no component vias observed" in unstitched_check["detail"]

    assert via_stitch_control["status"] == "PASS"
    assert {row["status"] for row in via_stitch_control["checks"]} == {"PASS"}
    stitched_check = next(
        row
        for row in via_stitch_control["checks"]
        if row["id"] == "pcb-return-paths/pwm-return/connectivity"
    )
    assert f"via {'2' * 64} (through" in stitched_check["detail"]
    assert "F.Cu to B.Cu" in stitched_check["detail"]
    assert [row["id"] for row in unstitched_layer_fault["checks"]] == [
        row["id"] for row in via_stitch_control["checks"]
    ]
