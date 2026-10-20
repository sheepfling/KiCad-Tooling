"""Focused synthetic regressions for the schematic readability lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import (
    evaluate,
)
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines
from tests.design_lint_fixtures import (
    coach,
)
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    enclosed_connector_body_wire_fixture,
    symbol_body_wire_fixture,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
]


@pytest.fixture
def body_wire_scan():
    return scan_wire_ends_on_pin_lines(
        symbol_body_wire_fixture(),
        source_path="synthetic/body-wire/fault.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )


@pytest.fixture
def empty_native_contract():
    return coach(NetlistContract(components={}, nets={}))


@pytest.fixture
def review_policy():
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.wire_through_symbol_body",
                mode="review",
                reason="Review wires that overlap symbol body graphics",
            ),
        )
    )


def test_wire_through_symbol_body_rule_is_off_by_default(body_wire_scan, empty_native_contract):
    report = evaluate(
        "synthetic-body-wire",
        empty_native_contract,
        DesignLintPolicy(),
        schematic_geometry=body_wire_scan,
    )

    assert report.status == "PASS"
    assert report.schematic_geometry.finding_count == 1
    finding = next(
        item for item in report.findings if item.rule_id == "schematic.wire_through_symbol_body"
    )
    assert finding.disposition == "RULE_OFF"


def test_wire_through_symbol_body_review_has_source_evidence(
    body_wire_scan, empty_native_contract, review_policy
):
    report = evaluate(
        "synthetic-body-wire",
        empty_native_contract,
        review_policy,
        schematic_geometry=body_wire_scan,
    )

    assert report.status == "REVIEW"
    finding = next(
        item for item in report.findings if item.rule_id == "schematic.wire_through_symbol_body"
    )
    assert finding.evidence["reference"] == ("R1",)
    assert finding.evidence["symbol_library_id"] == ("Lint:R",)
    assert finding.evidence["wire_uuid"] == ("f1000000-0000-4000-8000-000000000001",)
    assert "body_box_mm" in finding.evidence
    assert "overlap_segment_mm" in finding.evidence
    assert finding.evidence["pin_endpoint_numbers"] == ()
    assert "pin tip" not in finding.message


def test_wire_body_review_reports_connector_pin_endpoint_context(
    empty_native_contract, review_policy
):
    scan = scan_wire_ends_on_pin_lines(
        enclosed_connector_body_wire_fixture(body_offset_x=0.0),
        source_path="synthetic/enclosed-connector/body-wire.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    report = evaluate(
        "synthetic-enclosed-connector-body-wire",
        empty_native_contract,
        review_policy,
        schematic_geometry=scan,
    )

    findings = [
        item for item in report.findings if item.rule_id == "schematic.wire_through_symbol_body"
    ]
    assert report.status == "REVIEW"
    assert len(findings) == 2
    assert {item.evidence["reference"] for item in findings} == {("J1",), ("J2",)}
    assert all(item.evidence["pin_endpoint_numbers"] == ("1",) for item in findings)
    assert all("pin tip(s): 1 (SIGNAL)" in item.message for item in findings)


def test_wire_through_symbol_body_rule_can_block_by_project_policy(
    body_wire_scan, empty_native_contract, review_policy
):
    blocked_policy = review_policy.model_copy(
        update={
            "rules": (
                DesignLintRuleOverride(
                    rule_id="schematic.wire_through_symbol_body",
                    mode="block",
                    reason="This project requires clear separation of wires and symbol bodies",
                ),
            )
        }
    )
    report = evaluate(
        "synthetic-body-wire",
        empty_native_contract,
        blocked_policy,
        schematic_geometry=body_wire_scan,
    )

    assert report.status == "FAIL"


def test_wire_through_symbol_body_rule_supports_exact_ignore(
    body_wire_scan, empty_native_contract, review_policy
):
    reviewed = evaluate(
        "synthetic-body-wire",
        empty_native_contract,
        review_policy,
        schematic_geometry=body_wire_scan,
    )
    finding = next(
        item for item in reviewed.findings if item.rule_id == "schematic.wire_through_symbol_body"
    )
    ignored = evaluate(
        "synthetic-body-wire",
        empty_native_contract,
        review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="This crossing is a deliberate schematic convention",
                    ),
                )
            }
        ),
        schematic_geometry=body_wire_scan,
    )

    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "schematic.wire_through_symbol_body"
    )
    assert ignored_finding.disposition == "IGNORED"
    assert ignored.status == "PASS"
