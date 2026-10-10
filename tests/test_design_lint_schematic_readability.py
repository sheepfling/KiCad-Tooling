"""Focused synthetic regressions for the schematic readability lint theme."""

from __future__ import annotations

import unittest

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
    symbol_body_wire_fixture,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
]


class DesignLintSchematicReadabilityTests(unittest.TestCase):
    def test_wire_through_symbol_body_rule_is_configurable_and_off_by_default(self) -> None:
        scan = scan_wire_ends_on_pin_lines(
            symbol_body_wire_fixture(),
            source_path="synthetic/body-wire/fault.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        native = coach(NetlistContract(components={}, nets={}))
        default = evaluate(
            "synthetic-body-wire", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        self.assertEqual(
            next(
                item
                for item in default.findings
                if item.rule_id == "schematic.wire_through_symbol_body"
            ).disposition,
            "RULE_OFF",
        )

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_through_symbol_body",
                    mode="review",
                    reason="Review wires that overlap symbol body graphics",
                ),
            )
        )
        review = evaluate("synthetic-body-wire", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.wire_through_symbol_body"
        )
        self.assertEqual(finding.evidence["reference"], ("R1",))
        self.assertEqual(finding.evidence["symbol_library_id"], ("Lint:R",))
        self.assertEqual(finding.evidence["wire_uuid"], ("f1000000-0000-4000-8000-000000000001",))
        self.assertIn("body_box_mm", finding.evidence)
        self.assertIn("overlap_segment_mm", finding.evidence)

        blocked = evaluate(
            "synthetic-body-wire",
            native,
            review_policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="schematic.wire_through_symbol_body",
                            mode="block",
                            reason="This project requires clear separation of wires and symbol bodies",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-body-wire",
            native,
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
            schematic_geometry=scan,
        )
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "schematic.wire_through_symbol_body"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")
