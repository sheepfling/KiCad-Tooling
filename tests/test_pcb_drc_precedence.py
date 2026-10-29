"""Mapped rule coverage accounts for later potentially overriding rules."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_coverage import compare_native_rules
from tests.design_lint_fixtures.pcb_signal_path import compare, native_rules
from tests.test_pcb_drc_coverage import pair_map, rules_text

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize(
    "later_rule",
    (
        '(rule "later" (constraint edge_clearance (min 0.1mm)))',
        '(rule "later" (severity ignore) (constraint edge_clearance (min 2mm)))',
        (
            '(rule "later" (condition "A.hasNetclass(\'fast\')") '
            "(constraint edge_clearance (min 1mm)))"
        ),
        '(rule "later" (condition) (constraint edge_clearance (min 1mm)))',
        (
            '(rule "later" (condition "A.NetName == \'SYNTH_*\'") '
            "(constraint edge_clearance (min 1mm)))"
        ),
    ),
)
def test_later_potentially_overlapping_rule_makes_edge_coverage_incomplete(later_rule: str) -> None:
    clock = next(item for item in compare(rules=native_rules() + later_rule) if item.id == "clock")
    edge = next(item for item in clock.constraints if item.constraint == "edge_clearance")
    assert clock.status == "INCOMPLETE"
    assert edge.status == "UNSUPPORTED"
    assert "'later' (rule 5)" in (edge.issue or "")


def test_earlier_general_rule_and_later_disjoint_net_are_controls() -> None:
    source = native_rules()
    general = '(rule "general" (constraint edge_clearance (min 0.1mm)))\n'
    disjoint = (
        '(rule "other" (condition "A.NetName == \'OTHER\'") '
        "(constraint edge_clearance (min 0.1mm)))\n"
    )
    source = source.replace("(version 1)\n", "(version 1)\n" + general) + disjoint
    clock = next(item for item in compare(rules=source) if item.id == "clock")
    edge = next(item for item in clock.constraints if item.constraint == "edge_clearance")
    assert edge.status == "COVERED"


def test_later_different_constraint_does_not_shadow_edge_rule() -> None:
    other = '(rule "later-width" (constraint track_width (min 0.1mm)))'
    clock = next(item for item in compare(rules=native_rules() + other) if item.id == "clock")
    edge = next(item for item in clock.constraints if item.constraint == "edge_clearance")
    assert edge.status == "COVERED"


def test_later_distinct_pair_selector_is_not_assumed_disjoint() -> None:
    later = (
        '(rule "other-pair" (condition "A.inDiffPair(\'USB*\')") '
        "(constraint track_width (min 0.1mm)))"
    )
    (entry,) = compare_native_rules(pair_map(), rules_text() + later, frozenset())
    width = next(item for item in entry.constraints if item.constraint == "track_width")
    assert entry.status == "INCOMPLETE"
    assert width.status == "UNSUPPORTED"
    assert "other-pair" in (width.issue or "")
