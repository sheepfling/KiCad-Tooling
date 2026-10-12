"""Focused synthetic regressions for the schematic text lint theme."""

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
    free_text_anchor_fixture,
    free_text_objects_fixture,
    free_text_symbol_body_fixture,
    free_text_wire_fixture,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
]


def test_coincident_text_anchor_rule_is_configurable_and_review_only_by_default() -> None:
    scan = scan_wire_ends_on_pin_lines(
        free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4)),
        source_path="synthetic/text-anchor/coincident.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    native = coach(NetlistContract(components={}, nets={}))
    review_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.coincident_text_anchors",
                mode="review",
                reason="Review coincident free-text source anchors",
            ),
        )
    )

    default = evaluate("synthetic-text-anchor", native, DesignLintPolicy(), schematic_geometry=scan)
    assert default.status == "PASS"
    assert default.schematic_geometry.finding_count == 1
    assert (
        next(
            item for item in default.findings if item.rule_id == "schematic.coincident_text_anchors"
        ).disposition
        == "RULE_OFF"
    )

    review = evaluate("synthetic-text-anchor", native, review_policy, schematic_geometry=scan)
    assert review.status == "REVIEW"
    finding = next(
        item for item in review.findings if item.rule_id == "schematic.coincident_text_anchors"
    )
    assert finding.evidence["anchor_mm"] == ("25.400000,25.400000",)
    assert finding.evidence["first_text_uuid"] == ("d0000000-0000-4000-8000-000000000001",)

    blocked = evaluate(
        "synthetic-text-anchor",
        native,
        review_policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id="schematic.coincident_text_anchors",
                        mode="block",
                        reason="This project requires unique free-text anchors",
                    ),
                )
            }
        ),
        schematic_geometry=scan,
    )
    assert blocked.status == "FAIL"

    ignored = evaluate(
        "synthetic-text-anchor",
        native,
        review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="The two annotations intentionally share an anchor",
                    ),
                )
            }
        ),
        schematic_geometry=scan,
    )
    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "schematic.coincident_text_anchors"
    )
    assert ignored_finding.disposition == "IGNORED"
    assert ignored.status == "PASS"


def test_free_text_overlap_rule_is_configurable_and_review_only_by_default() -> None:
    scan = scan_wire_ends_on_pin_lines(
        free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (29.0, 25.4)
        ),
        source_path="synthetic/text-overlap/fault.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    native = coach(NetlistContract(components={}, nets={}))
    review_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.free_text_overlap",
                mode="review",
                reason="Review the bounded native-font text-overlap candidate",
            ),
        )
    )

    default = evaluate(
        "synthetic-text-overlap", native, DesignLintPolicy(), schematic_geometry=scan
    )
    assert default.status == "PASS"
    assert default.schematic_geometry.finding_count == 1
    assert (
        next(
            item for item in default.findings if item.rule_id == "schematic.free_text_overlap"
        ).disposition
        == "RULE_OFF"
    )

    review = evaluate("synthetic-text-overlap", native, review_policy, schematic_geometry=scan)
    assert review.status == "REVIEW"
    finding = next(
        item for item in review.findings if item.rule_id == "schematic.free_text_overlap"
    )
    assert finding.evidence["first_text_uuid"] == ("d0000000-0000-4000-8000-000000000001",)
    assert "overlap_box_mm" in finding.evidence

    blocked = evaluate(
        "synthetic-text-overlap",
        native,
        review_policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id="schematic.free_text_overlap",
                        mode="block",
                        reason="This project requires free-text envelopes to stay clear",
                    ),
                )
            }
        ),
        schematic_geometry=scan,
    )
    assert blocked.status == "FAIL"

    ignored = evaluate(
        "synthetic-text-overlap",
        native,
        review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="The annotations intentionally overlap for this project",
                    ),
                )
            }
        ),
        schematic_geometry=scan,
    )
    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "schematic.free_text_overlap"
    )
    assert ignored_finding.disposition == "IGNORED"
    assert ignored.status == "PASS"


def test_free_text_over_wire_rule_is_configurable_and_review_only_by_default() -> None:
    scan = scan_wire_ends_on_pin_lines(
        free_text_wire_fixture("WIRE CROSSING FAULT", (88.9, 71.12)),
        source_path="synthetic/text-wire/fault.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    native = coach(NetlistContract(components={}, nets={}))
    review_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.free_text_over_wire",
                mode="review",
                reason="Review free-text placement across native wire geometry",
            ),
        )
    )

    default = evaluate("synthetic-text-wire", native, DesignLintPolicy(), schematic_geometry=scan)
    assert default.status == "PASS"
    assert default.schematic_geometry.finding_count == 1
    assert (
        next(
            item for item in default.findings if item.rule_id == "schematic.free_text_over_wire"
        ).disposition
        == "RULE_OFF"
    )

    review = evaluate("synthetic-text-wire", native, review_policy, schematic_geometry=scan)
    assert review.status == "REVIEW"
    finding = next(
        item for item in review.findings if item.rule_id == "schematic.free_text_over_wire"
    )
    assert finding.evidence["text"] == ("WIRE CROSSING FAULT",)
    assert finding.evidence["wire_uuid"] == ("b0000000-0000-4000-8000-000000000005",)
    assert "overlap_segment_mm" in finding.evidence

    blocked = evaluate(
        "synthetic-text-wire",
        native,
        review_policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id="schematic.free_text_over_wire",
                        mode="block",
                        reason="This project requires annotations to stay clear of wires",
                    ),
                )
            }
        ),
        schematic_geometry=scan,
    )
    assert blocked.status == "FAIL"

    ignored = evaluate(
        "synthetic-text-wire",
        native,
        review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="This schematic annotation intentionally crosses the wire",
                    ),
                )
            }
        ),
        schematic_geometry=scan,
    )
    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "schematic.free_text_over_wire"
    )
    assert ignored_finding.disposition == "IGNORED"
    assert ignored.status == "PASS"


def test_free_text_over_symbol_body_rule_is_configurable_and_off_by_default() -> None:
    scan = scan_wire_ends_on_pin_lines(
        free_text_symbol_body_fixture(),
        source_path="synthetic/text-body/fault.kicad_sch",
        kicad_version="10.0.6",
        unconnected_pins=frozenset(),
    )
    native = coach(NetlistContract(components={}, nets={}))
    default = evaluate("synthetic-text-body", native, DesignLintPolicy(), schematic_geometry=scan)
    assert default.status == "PASS"
    assert default.schematic_geometry.finding_count == 1
    assert (
        next(
            item
            for item in default.findings
            if item.rule_id == "schematic.free_text_over_symbol_body"
        ).disposition
        == "RULE_OFF"
    )

    review_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="schematic.free_text_over_symbol_body",
                mode="review",
                reason="Review free text that overlaps a component body",
            ),
        )
    )
    review = evaluate("synthetic-text-body", native, review_policy, schematic_geometry=scan)
    assert review.status == "REVIEW"
    finding = next(
        item for item in review.findings if item.rule_id == "schematic.free_text_over_symbol_body"
    )
    assert finding.evidence["text"] == ("BODY NOTE",)
    assert finding.evidence["reference"] == ("R1",)
    assert finding.evidence["text_uuid"] == ("f2000000-0000-4000-8000-000000000001",)
    assert finding.evidence["symbol_library_id"] == ("Lint:R",)
    assert "overlap_box_mm" in finding.evidence
    assert "overlap_area_mm2" in finding.evidence

    blocked = evaluate(
        "synthetic-text-body",
        native,
        review_policy.model_copy(
            update={
                "rules": (
                    DesignLintRuleOverride(
                        rule_id="schematic.free_text_over_symbol_body",
                        mode="block",
                        reason="This project requires annotation clearance from symbols",
                    ),
                )
            }
        ),
        schematic_geometry=scan,
    )
    assert blocked.status == "FAIL"

    ignored = evaluate(
        "synthetic-text-body",
        native,
        review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="This note intentionally sits within the symbol outline",
                    ),
                )
            }
        ),
        schematic_geometry=scan,
    )
    ignored_finding = next(
        item for item in ignored.findings if item.rule_id == "schematic.free_text_over_symbol_body"
    )
    assert ignored_finding.disposition == "IGNORED"
    assert ignored.status == "PASS"
