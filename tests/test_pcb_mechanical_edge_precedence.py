"""A later physical-clearance rule can override mapped mechanical coverage."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_mechanical_edge_clearance import (
    mechanical_edge_rule_coverage_issue,
)
from tests.test_pcb_mechanical_edge_clearance import _requirement, _rule

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.mechanical_edge_clearance_rule_coverage"),
]


def _rules(first: str, second: str) -> str:
    return f"(version 1)\n{first.split(chr(10), 1)[1]}\n{second}"


@pytest.mark.parametrize(
    "later",
    (
        '(rule "general" (constraint physical_clearance (min 0.1mm)))',
        '(rule "ignored" (severity ignore) (constraint physical_clearance (min 0.1mm)))',
        (
            '(rule "selected" (layer "F.Courtyard") '
            "(condition \"A.Reference == 'J1'\") (constraint physical_clearance (min 0.1mm)))"
        ),
        '(rule "unknown-layer" (layer) (constraint physical_clearance (min 0.1mm)))',
    ),
)
def test_later_potentially_overlapping_rule_leaves_mechanical_coverage_unconfirmed(
    later: str,
) -> None:
    issue = mechanical_edge_rule_coverage_issue(
        _requirement(), native_constraints(_rules(_rule(), later)), kicad_version="10.0.5"
    )
    assert issue is not None
    assert "may override" in issue


def test_earlier_general_rule_does_not_override_the_mapped_rule() -> None:
    general = '(rule "general" (constraint physical_clearance (min 2mm)))'
    source = f"(version 1)\n{general}\n{_rule().split(chr(10), 1)[1]}"
    assert (
        mechanical_edge_rule_coverage_issue(
            _requirement(), native_constraints(source), kicad_version="10.0.5"
        )
        is None
    )


def test_later_opposite_courtyard_or_other_constraint_is_disjoint() -> None:
    opposite = '(rule "back" (layer "B.Courtyard") (constraint physical_clearance (min 2mm)))'
    other_type = '(rule "track" (constraint track_width (min 0.1mm)))'
    source = _rules(_rule(), f"{opposite}\n{other_type}")
    assert (
        mechanical_edge_rule_coverage_issue(
            _requirement(), native_constraints(source), kicad_version="10.0.5"
        )
        is None
    )


@pytest.mark.parametrize("placement", ("before", "opposite"))
def test_small_unconditional_radius_is_not_credited_even_without_precedence_overlap(
    placement: str,
) -> None:
    small = '(rule "small" (severity ignore) (constraint physical_clearance (min 0.1mm)))'
    if placement == "before":
        source = f"(version 1)\n{small}\n{_rule().split(chr(10), 1)[1]}"
    else:
        source = _rules(_rule(), small.replace("(severity ignore)", '(layer "B.Courtyard")'))
    issue = mechanical_edge_rule_coverage_issue(
        _requirement(), native_constraints(source), kicad_version="10.0.5"
    )
    assert issue is not None
    assert "search radius is below" in issue


def test_conditional_only_rule_requires_verified_version_or_sufficient_anchor() -> None:
    rules = native_constraints(_rule())
    assert (
        mechanical_edge_rule_coverage_issue(_requirement(), rules, kicad_version="10.0.5") is None
    )
    for version in ("10.0.0", "10.0.6", None):
        issue = mechanical_edge_rule_coverage_issue(_requirement(), rules, kicad_version=version)
        assert issue is not None
        assert "Conditional-only" in issue
    general = '(rule "anchor" (severity ignore) (constraint physical_clearance (min 2mm)))'
    source = f"(version 1)\n{general}\n{_rule().split(chr(10), 1)[1]}"
    assert (
        mechanical_edge_rule_coverage_issue(
            _requirement(), native_constraints(source), kicad_version="10.0.0"
        )
        is None
    )


def test_small_unconditional_hole_clearance_reduces_search_radius() -> None:
    hole = '(rule "hole" (constraint physical_hole_clearance (min 0.1mm)))'
    issue = mechanical_edge_rule_coverage_issue(
        _requirement(), native_constraints(_rules(_rule(), hole)), kicad_version="10.0.5"
    )
    assert issue is not None
    assert "search radius is below" in issue


def test_sufficient_unconditional_hole_clearance_is_a_radius_control() -> None:
    hole = '(rule "hole" (constraint physical_hole_clearance (min 2mm)))'
    assert (
        mechanical_edge_rule_coverage_issue(
            _requirement(), native_constraints(_rules(_rule(), hole)), kicad_version="10.0.0"
        )
        is None
    )


@pytest.mark.parametrize("condition", ('(condition "")', '(condition) (condition "x")'))
def test_empty_or_malformed_condition_cannot_be_a_search_radius_anchor(condition: str) -> None:
    uncertain = f'(rule "uncertain" {condition} (constraint physical_clearance (min 2mm)))'
    source = f"(version 1)\n{uncertain}\n{_rule().split(chr(10), 1)[1]}"
    issue = mechanical_edge_rule_coverage_issue(
        _requirement(), native_constraints(source), kicad_version="10.0.0"
    )
    assert issue is not None
    assert "unsupported or empty condition" in issue
