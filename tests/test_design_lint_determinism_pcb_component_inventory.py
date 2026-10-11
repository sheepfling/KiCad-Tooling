"""Cross-process determinism checks for schematic-to-PCB inventory review."""

from __future__ import annotations

from typing import cast

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.pcb_lint]


def test_component_inventory_fault_and_control_reports_are_deterministic() -> None:
    reports = cast(
        dict[str, dict[str, object]],
        hashseed_probe_reports(families=("pcb_component_inventory",)),
    )
    assert set(reports) == {
        "pcb_inventory_missing_placement_fault",
        "pcb_inventory_footprint_mismatch_fault",
        "pcb_inventory_exact_footprint_control",
    }

    missing = reports["pcb_inventory_missing_placement_fault"]
    mismatch = reports["pcb_inventory_footprint_mismatch_fault"]
    control = reports["pcb_inventory_exact_footprint_control"]
    missing_findings = cast(list[dict[str, object]], missing["findings"])
    mismatch_findings = cast(list[dict[str, object]], mismatch["findings"])
    rule_id = "pcb.schematic_component_inventory"

    assert missing["status"] == "REVIEW"
    assert mismatch["status"] == "REVIEW"
    assert control["status"] == "PASS"
    assert {item["rule_id"] for item in missing_findings} == {rule_id}
    assert {item["rule_id"] for item in mismatch_findings} == {rule_id}
    assert control["findings"] == []
    assert missing_findings != mismatch_findings
