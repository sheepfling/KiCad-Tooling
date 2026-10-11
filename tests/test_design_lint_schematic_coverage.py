"""Source-bound schematic geometry coverage regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    free_text_wire_fixture,
    symbol_body_wire_fixture,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.schematic_lint]


@pytest.fixture
def near_miss_geometry_case():
    fixture = Path(__file__).parent / "fixtures/design_lint/near-miss-pin-line.kicad_sch"
    source = fixture.read_bytes()
    scan = scan_wire_ends_on_pin_lines(
        source,
        source_path="tests/fixtures/design_lint/near-miss-pin-line.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset({"R1.1"}),
    )
    native = coach(NetlistContract(components={}, nets={"unconnected-(R1-Pad1)": ("R1.1",)}))
    return source, scan, native


def test_schematic_geometry_finding_is_disabled_by_default(
    near_miss_geometry_case,
) -> None:
    _, scan, native = near_miss_geometry_case

    report = evaluate("synthetic-geometry", native, DesignLintPolicy(), schematic_geometry=scan)

    assert report.status == "PASS"
    assert report.schematic_geometry.status == "DISABLED"
    assert report.schematic_geometry.mode == "off"
    finding = next(
        item for item in report.findings if item.rule_id == "schematic.wire_end_on_pin_line"
    )
    assert finding.disposition == "RULE_OFF"


def test_schematic_geometry_finding_can_be_reviewed_with_source_evidence(
    near_miss_geometry_case,
) -> None:
    _, scan, native = near_miss_geometry_case
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.wire_end_on_pin_line",
                mode="review",
                reason="Review suspected schematic endpoint near misses",
            ),
        )
    )

    report = evaluate("synthetic-geometry", native, policy, schematic_geometry=scan)
    finding = next(
        item for item in report.findings if item.rule_id == "schematic.wire_end_on_pin_line"
    )

    assert report.status == "REVIEW"
    assert finding.disposition == "OPEN"
    assert finding.evidence["schematic_sha256"] == (scan.source_sha256,)


def test_schematic_geometry_policy_can_block_a_finding(
    near_miss_geometry_case,
) -> None:
    _, scan, native = near_miss_geometry_case
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.wire_end_on_pin_line",
                mode="block",
                reason="This reviewed project gates pin-line near misses",
            ),
        )
    )

    report = evaluate("synthetic-geometry", native, policy, schematic_geometry=scan)

    assert report.status == "FAIL"


def test_geometry_ignore_clears_finding_and_becomes_stale_after_source_change(
    near_miss_geometry_case,
) -> None:
    source, scan, native = near_miss_geometry_case
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.wire_end_on_pin_line",
                mode="review",
                reason="Review suspected schematic endpoint near misses",
            ),
        )
    )
    report = evaluate("synthetic-geometry", native, policy, schematic_geometry=scan)
    finding = next(
        item for item in report.findings if item.rule_id == "schematic.wire_end_on_pin_line"
    )
    ignored_policy = policy.model_copy(
        update={
            "ignores": (
                DesignLintIgnore(
                    rule_id=finding.rule_id,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic control records an intentional drawing exception",
                ),
            )
        }
    )

    ignored = evaluate("synthetic-geometry", native, ignored_policy, schematic_geometry=scan)
    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "schematic.wire_end_on_pin_line"
    )
    changed_source = source.replace(b"FAULT_NET", b"FAULT_NET_CHANGED", 1)
    changed_scan = scan_wire_ends_on_pin_lines(
        changed_source,
        source_path=scan.source_path,
        kicad_version="10.0.6",
        unconnected_pins=frozenset({"R1.1"}),
    )
    stale = evaluate("synthetic-geometry", native, ignored_policy, schematic_geometry=changed_scan)

    assert ignored_finding.disposition == "IGNORED"
    assert ignored.status == "PASS"
    assert stale.status == "REVIEW"
    assert len(stale.stale_ignores) == 1


def test_geometry_coverage_is_scoped_to_enabled_rule_capabilities() -> None:
    source = symbol_body_wire_fixture()
    text = (
        b'  (text "UNSUPPORTED~{LINE}" (at 25.4 25.4 0) '
        b"(effects (font (size 1.27 1.27))) "
        b'(uuid "f1000000-0000-4000-8000-000000000009"))\n'
    )
    source = source.replace(b"  (sheet_instances", text + b"  (sheet_instances", 1)
    scan = scan_wire_ends_on_pin_lines(
        source,
        source_path="synthetic/body-wire-with-unsupported-text.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    native = coach(NetlistContract(components={}, nets={}))

    wire_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.wire_through_symbol_body",
                mode="review",
                reason="Review body crossings in this project",
            ),
        )
    )
    wire_report = evaluate("synthetic-rule-coverage", native, wire_policy, schematic_geometry=scan)
    assert wire_report.status == "REVIEW"
    assert wire_report.schematic_geometry.status == "COMPLETE"
    assert (
        wire_report.schematic_geometry.rule_coverage["schematic.wire_through_symbol_body"]
        == "COMPLETE"
    )
    assert wire_report.schematic_geometry.rule_coverage["schematic.free_text_overlap"] == (
        "DISABLED"
    )
    assert wire_report.schematic_geometry.unsupported == ()

    text_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.free_text_overlap",
                mode="review",
                reason="Review supported free-text geometry in this project",
            ),
        )
    )
    text_report = evaluate("synthetic-rule-coverage", native, text_policy, schematic_geometry=scan)
    assert text_report.status == "REVIEW"
    assert text_report.schematic_geometry.status == "PARTIAL"
    assert text_report.schematic_geometry.rule_coverage["schematic.free_text_overlap"] == (
        "PARTIAL"
    )
    assert "schematic.free_text_overlap" in text_report.schematic_geometry.unsupported_by_rule
    assert text_report.schematic_geometry.rule_coverage["schematic.wire_through_symbol_body"] == (
        "DISABLED"
    )


def test_supported_multiline_free_text_geometry_has_complete_coverage() -> None:
    scan = scan_wire_ends_on_pin_lines(
        free_text_wire_fixture("FIRST\nSECOND", (88.9, 80.01)),
        source_path="synthetic/body-wire-with-supported-multiline-text.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    native = coach(NetlistContract(components={}, nets={}))
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.free_text_overlap",
                mode="review",
                reason="Review supported free-text geometry in this project",
            ),
        )
    )

    report = evaluate("synthetic-rule-coverage", native, policy, schematic_geometry=scan)

    assert report.status == "PASS"
    assert report.schematic_geometry.status == "COMPLETE"
    assert report.schematic_geometry.rule_coverage["schematic.free_text_overlap"] == ("COMPLETE")
    assert report.schematic_geometry.unsupported == ()
