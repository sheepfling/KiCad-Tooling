"""Focused synthetic checks for mapped signal-path edge-clearance rules."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.models import (
    PcbDrcMinMaxRequirement,
    PcbSignalPathRequirement,
    PcbSignalPathRuleMap,
)
from tests.design_lint_fixtures.pcb_signal_path import compare, native_rules

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.signal_path_rule_coverage"),
]


def test_authored_edge_clearance_bound_requires_exact_selector_and_minimum() -> None:
    source = native_rules()
    edge_rule = """(rule "synthetic-clock-edge-clearance"
  (condition "A.NetName == 'SYNTH_CLK'")
  (constraint edge_clearance (min 2mm)))
"""
    missing = compare(rules=source.replace(edge_rule, ""))
    clock = next(entry for entry in missing if entry.id == "clock")
    edge = next(item for item in clock.constraints if item.constraint == "edge_clearance")
    assert edge.status == "MISSING"

    wrong_selector = source.replace("'SYNTH_CLK'", "'SYNTH_DATA'")
    mismatched_selector = compare(rules=wrong_selector)
    clock = next(entry for entry in mismatched_selector if entry.id == "clock")
    assert (
        next(item for item in clock.constraints if item.constraint == "edge_clearance").status
        == "MISSING"
    )

    wrong_bound = compare(
        rules=source.replace(
            "(constraint edge_clearance (min 2mm))",
            "(constraint edge_clearance (min 1.5mm))",
        )
    )
    clock = next(entry for entry in wrong_bound if entry.id == "clock")
    edge = next(item for item in clock.constraints if item.constraint == "edge_clearance")
    assert edge.status == "MISMATCH"
    assert edge.observed_min_nm == 1_500_000


def test_edge_rule_duplicates_and_ignored_severity_do_not_count_as_coverage() -> None:
    source = native_rules()
    edge_rule = """(rule "synthetic-clock-edge-clearance"
  (condition "A.NetName == 'SYNTH_CLK'")
  (constraint edge_clearance (min 2mm)))
"""
    duplicated = compare(
        rules=source
        + edge_rule.replace('"synthetic-clock-edge-clearance"', '"duplicate-edge-clearance"')
    )
    clock = next(entry for entry in duplicated if entry.id == "clock")
    edge = next(item for item in clock.constraints if item.constraint == "edge_clearance")
    assert edge.status == "AMBIGUOUS"

    ignored_severity = source.replace(
        '(rule "synthetic-clock-edge-clearance"',
        '(rule "synthetic-clock-edge-clearance"\n  (severity ignore)',
    )
    ignored = compare(rules=ignored_severity)
    clock = next(entry for entry in ignored if entry.id == "clock")
    edge = next(item for item in clock.constraints if item.constraint == "edge_clearance")
    assert edge.status == "IGNORED"
    assert "severity is 'ignore'" in (edge.issue or "")

    disabled = compare(ignored=frozenset({"copper_edge_clearance"}))
    clock = next(entry for entry in disabled if entry.id == "clock")
    assert (
        next(item for item in clock.constraints if item.constraint == "edge_clearance").status
        == "IGNORED"
    )


def test_edge_only_signal_path_is_complete_without_length_or_skew_rules() -> None:
    requirements = PcbSignalPathRuleMap(
        basis="Synthetic edge-sensitive path",
        paths=(
            PcbSignalPathRequirement(
                id="clock-edge",
                basis="Synthetic authored edge margin",
                net="SYNTH_CLK",
                from_pad="J1.1",
                to_pad="U1.1",
                edge_clearance=PcbDrcMinMaxRequirement(min_nm=2_000_000),
            ),
        ),
    )
    rules = """(version 1)
(rule "synthetic-clock-edge-clearance"
  (condition "A.NetName == 'SYNTH_CLK'")
  (constraint edge_clearance (min 2mm)))
"""

    (entry,) = compare(requirements=requirements, rules=rules)

    assert entry.id == "clock-edge"
    assert entry.status == "COMPLETE"
    assert [item.constraint for item in entry.constraints] == ["edge_clearance"]


def test_edge_clearance_is_a_minimum_and_requires_a_representable_net_name() -> None:
    with pytest.raises(ValidationError, match="only an authored minimum"):
        PcbSignalPathRequirement(
            id="edge-path",
            basis="Synthetic authored edge margin",
            net="SYNTH_CLK",
            from_pad="J1.1",
            to_pad="U1.1",
            edge_clearance=PcbDrcMinMaxRequirement(min_nm=2_000_000, max_nm=3_000_000),
        )

    with pytest.raises(ValidationError, match="cannot be represented exactly"):
        PcbSignalPathRequirement(
            id="quoted-edge-path",
            basis="Synthetic unsafe native selector",
            net="SYNTH'CLK",
            from_pad="J1.1",
            to_pad="U1.1",
            edge_clearance=PcbDrcMinMaxRequirement(min_nm=2_000_000),
        )
