"""Coverage states for guarded connector aliases with native PART_ID values."""

from __future__ import annotations

import json

import pytest

from kicad_tooling.hwrepo.design_lint_connector_report import connector_peer_report_lines
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from tests.connector_part_id_peer_support import (
    PART_ID_PEER_PIN_DIVERGENCE_RULE_ID,
    PART_ID_PEER_PIN_OUTLIER_RULE_ID,
    connector_netlist,
    lint_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


@pytest.mark.parametrize(
    ("overrides", "expected_status", "outcome"),
    (
        ({"part_ids": {}}, "NO_CANDIDATES", None),
        ({"values": {"J1": "Port A", "J2": "Port B"}}, "INCOMPLETE_EVIDENCE", "identity"),
        (
            {"footprints": {"J1": "Synthetic:Port_2x1", "J2": "Synthetic:Other"}},
            "INCOMPLETE_EVIDENCE",
            "identity",
        ),
        (
            {"pin_inventories": {"J1": ("1", "2"), "J2": ("1",)}},
            "INCOMPLETE_EVIDENCE",
            "inventory",
        ),
        (
            {
                "pin_functions": {
                    "J1.1": "Pin_1",
                    "J1.2": "Pin_2",
                    "J2.1": "Pin_1",
                    "J2.2": "RETURN",
                }
            },
            "PARTIALLY_EVALUATED",
            "differing_metadata",
        ),
        (
            {
                "pin_electrical_types": {
                    "J1.1": "passive",
                    "J1.2": "passive",
                    "J2.1": "passive",
                    "J2.2": "input",
                }
            },
            "PARTIALLY_EVALUATED",
            "differing_metadata",
        ),
        (
            {
                "pin_functions": {
                    "J1.1": "Pin_1",
                    "J1.2": "Pin_2",
                    "J2.1": "Pin_1",
                    "J2.2": None,
                }
            },
            "INCOMPLETE_EVIDENCE",
            "metadata",
        ),
        (
            {
                "pin_functions": {
                    "J1.1": "Pin_1",
                    "J1.2": "Pin_2",
                    "J2.1": "Other",
                    "J2.2": None,
                }
            },
            "INCOMPLETE_EVIDENCE",
            "metadata",
        ),
        (
            {
                "pin_electrical_types": {
                    "J1.1": "passive",
                    "J1.2": "passive",
                    "J2.1": "passive",
                    "J2.2": "~",
                }
            },
            "INCOMPLETE_EVIDENCE",
            "metadata",
        ),
    ),
    ids=(
        "missing-part-id",
        "value-mismatch",
        "footprint-mismatch",
        "inventory-mismatch",
        "function-mismatch",
        "type-mismatch",
        "missing-function",
        "missing-metadata-takes-precedence",
        "unnamed-electrical-type",
    ),
)
def test_part_id_peer_scan_reports_one_identity_and_metadata_outcome(
    overrides: dict[str, object], expected_status: str, outcome: str | None
) -> None:
    report = lint_report(
        connector_netlist(
            symbols={"J1": "Synthetic:PortLeft", "J2": "Synthetic:PortRight"},
            **overrides,
        )
    )
    assert not any(
        item.rule_id in {PART_ID_PEER_PIN_OUTLIER_RULE_ID, PART_ID_PEER_PIN_DIVERGENCE_RULE_ID}
        for item in report.findings
    )

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.part_id_alias_coverage
    assert alias.status == expected_status
    assert alias.incomplete_component_identity_group_count == int(outcome == "identity")
    assert alias.incomplete_pin_inventory_group_count == int(outcome == "inventory")
    assert alias.incomplete_pin_metadata_group_count == int(outcome == "metadata")
    assert alias.differing_pin_metadata_group_count == int(outcome == "differing_metadata")
    if outcome == "differing_metadata":
        assert any(
            "differing metadata groups: 1" in line for line in connector_peer_report_lines(report)
        )


def test_schema_five_part_id_coverage_defaults_the_new_count_to_zero() -> None:
    report = lint_report(connector_netlist())
    payload = report.model_dump(mode="json")
    payload["schema_version"] = "5"
    alias = payload["connector_peer_pin_coverage"]["part_id_alias_coverage"]
    alias.pop("differing_pin_metadata_group_count")

    restored = DesignLintReport.model_validate_json(json.dumps(payload))

    assert restored.schema_version == "5"
    assert restored.connector_peer_pin_coverage is not None
    assert (
        restored.connector_peer_pin_coverage.part_id_alias_coverage.differing_pin_metadata_group_count
        == 0
    )


def test_mixed_missing_and_differing_candidate_groups_are_counted_separately() -> None:
    report = lint_report(
        connector_netlist(
            references=("J1", "J2", "J3", "J4"),
            part_ids={"J1": "PORT-A", "J2": "PORT-A", "J3": "PORT-B", "J4": "PORT-B"},
            pin_two_nets=(None, None, None, None),
            pin_functions={
                "J1.1": "Pin_1",
                "J1.2": "Pin_2",
                "J2.1": "Pin_1",
                "J2.2": "RETURN",
                "J3.1": "Pin_1",
                "J3.2": "Pin_2",
                "J4.1": "Pin_1",
                "J4.2": None,
            },
        )
    )

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.part_id_alias_coverage
    assert alias.status == "PARTIALLY_EVALUATED"
    assert alias.candidate_group_count == 2
    assert alias.incomplete_pin_metadata_group_count == 1
    assert alias.differing_pin_metadata_group_count == 1
