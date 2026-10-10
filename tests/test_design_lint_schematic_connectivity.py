"""Focused synthetic regressions for the schematic connectivity lint theme."""

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

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
]


class DesignLintSchematicConnectivityTests(unittest.TestCase):
    def test_pin_tip_on_wire_interior_has_independent_project_policy(self) -> None:
        source_path = Path(__file__).parent / (
            "fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch"
        )
        scan = scan_wire_ends_on_pin_lines(
            source_path.read_bytes(),
            source_path="tests/fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.1"}),
        )
        self.assertEqual(scan.findings, ())
        self.assertEqual(len(scan.pin_tip_on_wire_interiors), 1)
        native = coach(NetlistContract(components={}, nets={"unconnected-(R1-Pad1)": ("R1.1",)}))

        default = evaluate(
            "synthetic-wire-middle", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        default_finding = next(
            item
            for item in default.findings
            if item.rule_id == "schematic.pin_tip_on_wire_interior"
        )
        self.assertEqual(default_finding.disposition, "RULE_OFF")

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.pin_tip_on_wire_interior",
                    mode="review",
                    reason="Review native-open pins crossed by wire segments",
                ),
            )
        )
        review = evaluate("synthetic-wire-middle", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        self.assertEqual(
            review.schematic_geometry.rule_modes["schematic.pin_tip_on_wire_interior"],
            "review",
        )
        self.assertEqual(
            review.schematic_geometry.rule_modes["schematic.wire_end_on_pin_line"], "off"
        )
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.pin_tip_on_wire_interior"
        )
        self.assertEqual(finding.evidence["pin"], ("R1.1",))
        self.assertEqual(finding.evidence["wire_segment_start_mm"], ("50.800000,71.120000",))
        self.assertEqual(finding.evidence["wire_segment_end_mm"], ("101.600000,71.120000",))

        blocking = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.pin_tip_on_wire_interior",
                    mode="block",
                    reason="This project explicitly gates wire-interior pin misses",
                ),
            )
        )
        blocked = evaluate("synthetic-wire-middle", native, blocking, schematic_geometry=scan)
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Reviewed intentionally open pin adjacent to wire geometry",
                    ),
                )
            }
        )
        ignored = evaluate("synthetic-wire-middle", native, ignored_policy, schematic_geometry=scan)
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "schematic.pin_tip_on_wire_interior"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_wire_endpoint_near_pin_tip_has_independent_project_policy(self) -> None:
        source_path = Path(__file__).parent / (
            "fixtures/design_lint/wire-end-near-pin-tip.kicad_sch"
        )
        source = source_path.read_bytes()
        scan = scan_wire_ends_on_pin_lines(
            source,
            source_path="tests/fixtures/design_lint/wire-end-near-pin-tip.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.1"}),
        )
        self.assertEqual(scan.findings, ())
        self.assertEqual(scan.pin_tip_on_wire_interiors, ())
        self.assertEqual(len(scan.wire_endpoints_near_pin_tips), 1)
        native = coach(NetlistContract(components={}, nets={"unconnected-(R1-Pad1)": ("R1.1",)}))

        default = evaluate(
            "synthetic-wire-end-near-pin-tip", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        default_finding = next(
            item
            for item in default.findings
            if item.rule_id == "schematic.wire_endpoint_near_pin_tip"
        )
        self.assertEqual(default_finding.disposition, "RULE_OFF")

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_endpoint_near_pin_tip",
                    mode="review",
                    reason="Review native-open pins with nearby wire endpoints",
                ),
            )
        )
        review = evaluate(
            "synthetic-wire-end-near-pin-tip", native, review_policy, schematic_geometry=scan
        )
        self.assertEqual(review.status, "REVIEW")
        self.assertEqual(
            review.schematic_geometry.rule_modes["schematic.wire_endpoint_near_pin_tip"],
            "review",
        )
        finding = next(
            item
            for item in review.findings
            if item.rule_id == "schematic.wire_endpoint_near_pin_tip"
        )
        self.assertEqual(finding.evidence["pin"], ("R1.1",))
        self.assertEqual(finding.evidence["wire_endpoint_mm"], ("76.200000,70.620000",))
        self.assertEqual(finding.evidence["distance_to_pin_tip_mm"], ("0.500000",))

        blocking_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_endpoint_near_pin_tip",
                    mode="block",
                    reason="This reviewed project gates wire-to-pin near misses",
                ),
            )
        )
        blocked = evaluate(
            "synthetic-wire-end-near-pin-tip", native, blocking_policy, schematic_geometry=scan
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic review accepts this exact near miss",
                    ),
                )
            }
        )
        ignored = evaluate(
            "synthetic-wire-end-near-pin-tip", native, ignored_policy, schematic_geometry=scan
        )
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "schematic.wire_endpoint_near_pin_tip"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

        changed_source = source.replace(b"70.62", b"70.61", 1)
        changed_scan = scan_wire_ends_on_pin_lines(
            changed_source,
            source_path=scan.source_path,
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.1"}),
        )
        stale = evaluate(
            "synthetic-wire-end-near-pin-tip",
            native,
            ignored_policy,
            schematic_geometry=changed_scan,
        )
        self.assertEqual(stale.status, "REVIEW")
        self.assertEqual(len(stale.stale_ignores), 1)

    def test_label_near_wire_endpoint_has_independent_project_policy(self) -> None:
        source_path = Path(__file__).parent / (
            "fixtures/design_lint/label-near-wire-endpoint.kicad_sch"
        )
        scan = scan_wire_ends_on_pin_lines(
            source_path.read_bytes(),
            source_path="tests/fixtures/design_lint/label-near-wire-endpoint.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        self.assertEqual(scan.findings, ())
        self.assertEqual(scan.pin_tip_on_wire_interiors, ())
        self.assertEqual(len(scan.labels_near_wire_endpoints), 1)
        native = coach(NetlistContract(components={}, nets={}))

        default = evaluate(
            "synthetic-label-near-endpoint", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        default_finding = next(
            item
            for item in default.findings
            if item.rule_id == "schematic.label_near_wire_endpoint"
        )
        self.assertEqual(default_finding.disposition, "RULE_OFF")

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.label_near_wire_endpoint",
                    mode="review",
                    reason="Review labels placed close to, but off, wire endpoints",
                ),
            )
        )
        review = evaluate(
            "synthetic-label-near-endpoint", native, review_policy, schematic_geometry=scan
        )
        self.assertEqual(review.status, "REVIEW")
        self.assertEqual(
            review.schematic_geometry.rule_modes["schematic.label_near_wire_endpoint"], "review"
        )
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.label_near_wire_endpoint"
        )
        self.assertEqual(finding.evidence["label_uuid"], ("b0000000-0000-4000-8000-000000000006",))
        self.assertEqual(
            finding.evidence["near_wire_endpoints"],
            ("b0000000-0000-4000-8000-000000000005@101.600000,71.120000 (0.500000 mm)",),
        )

        blocking_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.label_near_wire_endpoint",
                    mode="block",
                    reason="This project explicitly gates schematic label near misses",
                ),
            )
        )
        blocked = evaluate(
            "synthetic-label-near-endpoint", native, blocking_policy, schematic_geometry=scan
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic review control records an intentional detached label",
                    ),
                )
            }
        )
        ignored = evaluate(
            "synthetic-label-near-endpoint", native, ignored_policy, schematic_geometry=scan
        )
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "schematic.label_near_wire_endpoint"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_unmarked_wire_crossing_has_independent_review_and_ignore_policy(self) -> None:
        source_path = Path(__file__).parent / (
            "fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch"
        )
        scan = scan_wire_ends_on_pin_lines(
            source_path.read_bytes(),
            source_path="tests/fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        self.assertEqual(len(scan.unmarked_wire_crossings), 1)
        native = coach(NetlistContract(components={}, nets={}))

        default = evaluate(
            "synthetic-wire-crossing", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        default_finding = next(
            item for item in default.findings if item.rule_id == "schematic.unmarked_wire_crossing"
        )
        self.assertEqual(default_finding.disposition, "RULE_OFF")

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.unmarked_wire_crossing",
                    mode="review",
                    reason="Review unmarked wire crossings for intended connectivity",
                ),
            )
        )
        review = evaluate("synthetic-wire-crossing", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.unmarked_wire_crossing"
        )
        self.assertEqual(finding.evidence["crossing_mm"], ("127.000000,127.000000",))
        self.assertEqual(
            finding.evidence["wire_uuids"],
            (
                "c0000000-0000-4000-8000-000000000008",
                "c0000000-0000-4000-8000-000000000009",
            ),
        )

        blocked = evaluate(
            "synthetic-wire-crossing",
            native,
            review_policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="schematic.unmarked_wire_crossing",
                            mode="block",
                            reason="This project gates all unresolved wire crossings",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="This unmarked crossing is intentionally unconnected",
                    ),
                )
            }
        )
        ignored = evaluate(
            "synthetic-wire-crossing", native, ignored_policy, schematic_geometry=scan
        )
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "schematic.unmarked_wire_crossing"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_unmarked_t_junction_has_independent_review_and_ignore_policy(self) -> None:
        source_path = Path(__file__).parent / (
            "fixtures/design_lint/t-junction/fault-no-junction.kicad_sch"
        )
        scan = scan_wire_ends_on_pin_lines(
            source_path.read_bytes(),
            source_path="tests/fixtures/design_lint/t-junction/fault-no-junction.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.2"}),
        )
        self.assertEqual(len(scan.unmarked_t_junctions), 1)
        native = coach(NetlistContract(components={}, nets={}))
        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.unmarked_t_junction",
                    mode="review",
                    reason="Review endpoint-to-interior contacts for missing junctions",
                ),
            )
        )

        default = evaluate(
            "synthetic-t-junction", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        self.assertEqual(
            next(
                item for item in default.findings if item.rule_id == "schematic.unmarked_t_junction"
            ).disposition,
            "RULE_OFF",
        )

        review = evaluate("synthetic-t-junction", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.unmarked_t_junction"
        )
        self.assertEqual(finding.evidence["junction_mm"], ("88.900000,71.120000",))
        self.assertEqual(
            finding.evidence["endpoint_wire_uuid"],
            ("c0000000-0000-4000-8000-000000000012",),
        )
        self.assertEqual(
            finding.evidence["interior_wire_uuid"],
            ("b0000000-0000-4000-8000-000000000005",),
        )

        blocked = evaluate(
            "synthetic-t-junction",
            native,
            review_policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="schematic.unmarked_t_junction",
                            mode="block",
                            reason="This project requires explicit junction markers at T contacts",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="This branch intentionally remains separate",
                    ),
                )
            }
        )
        ignored = evaluate("synthetic-t-junction", native, ignored_policy, schematic_geometry=scan)
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "schematic.unmarked_t_junction"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")
