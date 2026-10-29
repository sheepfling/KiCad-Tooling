"""Unresolved KiCad substitutions cannot establish DRC rule coverage."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.pcb_drc_rule_coverage import compare_native_rules
from kicad_tooling.hwrepo.pcb_drc_rule_parser import native_constraints
from kicad_tooling.hwrepo.pcb_mechanical_edge_clearance import mechanical_edge_rule_coverage_issue
from tests.design_lint_fixtures.pcb_signal_path import compare, native_rules
from tests.test_pcb_drc_coverage import pair_map, rules_text
from tests.test_pcb_mechanical_edge_clearance import _requirement, _rule

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize(
    "addition",
    (
        '\n(rule "later" (constraint ${KIND} (min 0.1mm)))',
        (
            '\n(rule "later" (condition "A.NetName == \'${TARGET}\'") '
            "(constraint edge_clearance (min 0.1mm)))"
        ),
        "\n${EXTRA_RULE}",
        "\n# A substitution can expand across the comment boundary: ${EXTRA}",
    ),
    ids=("constraint-type", "condition", "whole-rule", "comment"),
)
def test_signal_rule_coverage_does_not_credit_unresolved_substitution(addition: str) -> None:
    clock = next(item for item in compare(rules=native_rules() + addition) if item.id == "clock")
    edge = next(item for item in clock.constraints if item.constraint == "edge_clearance")
    assert clock.status == "INCOMPLETE"
    assert edge.status == "UNSUPPORTED"
    assert "text variable" in (edge.issue or "").lower()


@pytest.mark.parametrize(
    "addition",
    (
        '\n(rule "later" (constraint ${KIND} (min 0.1mm)))',
        "\n${EXTRA_RULE}",
    ),
    ids=("constraint-type", "whole-rule"),
)
def test_pair_rule_coverage_does_not_credit_unresolved_substitution(addition: str) -> None:
    (entry,) = compare_native_rules(pair_map(), rules_text() + addition, frozenset())
    assert entry.status == "INCOMPLETE"
    assert all(item.status == "UNSUPPORTED" for item in entry.constraints)
    assert all("text variable" in (item.issue or "").lower() for item in entry.constraints)


@pytest.mark.parametrize(
    "addition",
    (
        '\n(rule "later" (constraint ${KIND} (min 0.1mm)))',
        '\n(rule "later" (layer ${SIDE}) (constraint physical_clearance (min 0.1mm)))',
        '\n(rule "later" (constraint physical_hole_clearance (min ${RADIUS})))',
        "\n${EXTRA_RULE}",
    ),
    ids=("constraint-type", "layer", "radius", "whole-rule"),
)
def test_mechanical_coverage_does_not_credit_unresolved_substitution(addition: str) -> None:
    issue = mechanical_edge_rule_coverage_issue(
        _requirement(), native_constraints(_rule() + addition), kicad_version="10.0.5"
    )
    assert issue is not None
    assert "text variable" in issue.lower()


def test_unexpanded_variable_in_mapped_bound_cannot_be_credited() -> None:
    rules = native_rules().replace(
        "(constraint edge_clearance (min 2mm))", "(constraint edge_clearance (min ${LIMIT}))"
    )
    clock = next(item for item in compare(rules=rules) if item.id == "clock")
    edge = next(item for item in clock.constraints if item.constraint == "edge_clearance")
    assert edge.status == "UNSUPPORTED"
    assert "text variable" in (edge.issue or "").lower()


def test_no_substitutions_leave_exact_rule_coverage_available() -> None:
    clock = next(item for item in compare(rules=native_rules()) if item.id == "clock")
    edge = next(item for item in clock.constraints if item.constraint == "edge_clearance")
    assert edge.status == "COVERED"
    (pair,) = compare_native_rules(pair_map(), rules_text(), frozenset())
    assert pair.status == "COMPLETE"
    assert (
        mechanical_edge_rule_coverage_issue(
            _requirement(), native_constraints(_rule()), kicad_version="10.0.5"
        )
        is None
    )
