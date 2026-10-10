"""Source-bound schematic geometry coverage regressions."""

from __future__ import annotations

import unittest
from pathlib import Path

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
    free_text_wire_fixture,
    symbol_body_wire_fixture,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.schematic_lint]


class DesignLintSchematicCoverageTests(unittest.TestCase):
    def test_schematic_geometry_is_project_opt_in_and_uses_review_block_and_ignore_policy(
        self,
    ) -> None:
        fixture = Path(__file__).parent / "fixtures/design_lint/near-miss-pin-line.kicad_sch"
        source = fixture.read_bytes()
        scan = scan_wire_ends_on_pin_lines(
            source,
            source_path="tests/fixtures/design_lint/near-miss-pin-line.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.1"}),
        )
        native = coach(NetlistContract(components={}, nets={"unconnected-(R1-Pad1)": ("R1.1",)}))

        default = evaluate(
            "synthetic-geometry", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.status, "DISABLED")
        self.assertEqual(default.schematic_geometry.mode, "off")
        default_finding = next(
            item for item in default.findings if item.rule_id == "schematic.wire_end_on_pin_line"
        )
        self.assertEqual(default_finding.disposition, "RULE_OFF")

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_end_on_pin_line",
                    mode="review",
                    reason="Review suspected schematic endpoint near misses",
                ),
            )
        )
        review = evaluate("synthetic-geometry", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        open_finding = next(
            item for item in review.findings if item.rule_id == "schematic.wire_end_on_pin_line"
        )
        self.assertEqual(open_finding.disposition, "OPEN")
        self.assertEqual(open_finding.evidence["schematic_sha256"], (scan.source_sha256,))

        blocked_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_end_on_pin_line",
                    mode="block",
                    reason="This reviewed project gates pin-line near misses",
                ),
            )
        )
        blocked = evaluate("synthetic-geometry", native, blocked_policy, schematic_geometry=scan)
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=open_finding.rule_id,
                        fingerprint=open_finding.fingerprint,
                        reason="Synthetic control records an intentional drawing exception",
                    ),
                )
            }
        )
        ignored = evaluate("synthetic-geometry", native, ignored_policy, schematic_geometry=scan)
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "schematic.wire_end_on_pin_line"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

        changed_source = source.replace(b"FAULT_NET", b"FAULT_NET_CHANGED", 1)
        changed_scan = scan_wire_ends_on_pin_lines(
            changed_source,
            source_path=scan.source_path,
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.1"}),
        )
        stale = evaluate(
            "synthetic-geometry", native, ignored_policy, schematic_geometry=changed_scan
        )
        self.assertEqual(stale.status, "REVIEW")
        self.assertEqual(len(stale.stale_ignores), 1)

    def test_geometry_coverage_is_scoped_to_enabled_rule_capabilities(self) -> None:
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
        wire_report = evaluate(
            "synthetic-rule-coverage", native, wire_policy, schematic_geometry=scan
        )
        self.assertEqual(wire_report.status, "REVIEW")
        self.assertEqual(wire_report.schematic_geometry.status, "COMPLETE")
        self.assertEqual(
            wire_report.schematic_geometry.rule_coverage["schematic.wire_through_symbol_body"],
            "COMPLETE",
        )
        self.assertEqual(
            wire_report.schematic_geometry.rule_coverage["schematic.free_text_overlap"],
            "DISABLED",
        )
        self.assertEqual(wire_report.schematic_geometry.unsupported, ())

        text_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.free_text_overlap",
                    mode="review",
                    reason="Review supported free-text geometry in this project",
                ),
            )
        )
        text_report = evaluate(
            "synthetic-rule-coverage", native, text_policy, schematic_geometry=scan
        )
        self.assertEqual(text_report.status, "REVIEW")
        self.assertEqual(text_report.schematic_geometry.status, "PARTIAL")
        self.assertEqual(
            text_report.schematic_geometry.rule_coverage["schematic.free_text_overlap"],
            "PARTIAL",
        )
        self.assertIn(
            "schematic.free_text_overlap", text_report.schematic_geometry.unsupported_by_rule
        )
        self.assertEqual(
            text_report.schematic_geometry.rule_coverage["schematic.wire_through_symbol_body"],
            "DISABLED",
        )

        multiline_scan = scan_wire_ends_on_pin_lines(
            free_text_wire_fixture("FIRST\nSECOND", (88.9, 80.01)),
            source_path="synthetic/body-wire-with-supported-multiline-text.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        multiline_report = evaluate(
            "synthetic-rule-coverage", native, text_policy, schematic_geometry=multiline_scan
        )
        self.assertEqual(multiline_report.status, "PASS")
        self.assertEqual(multiline_report.schematic_geometry.status, "COMPLETE")
        self.assertEqual(
            multiline_report.schematic_geometry.rule_coverage["schematic.free_text_overlap"],
            "COMPLETE",
        )
        self.assertEqual(multiline_report.schematic_geometry.unsupported, ())
