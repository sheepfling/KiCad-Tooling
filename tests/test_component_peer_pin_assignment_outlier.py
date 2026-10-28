"""Generic component peer assignment outlier review regressions."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.component_peer_pin_support import lint_report, peer_component_pin_netlist

RULE_ID = "component.generic_peer_pin_assignment_outlier"
pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


def _generic_peer_assignment_netlist(
    *,
    references: tuple[str, ...] = ("U1", "U2", "U3"),
    assignments: tuple[str | None, ...] = ("PEER_DATA", "PEER_DATA", "OTHER_DATA"),
    symbols: Mapping[str, str] | None = None,
    dnp: tuple[str, ...] = (),
    missing_inventory: tuple[str, ...] = (),
    ambiguous_pins: tuple[str, ...] = (),
    pin_functions: tuple[str | None, ...] | None = None,
    electrical_types: tuple[str, ...] | None = None,
    shared_anchor: bool = True,
) -> NetlistContract:
    source = peer_component_pin_netlist(
        references=references,
        pin_nets=assignments,
        dnp=dnp,
        symbols=symbols,
        default_symbol="Synthetic:PeerModule",
        pin_electrical_types=electrical_types or tuple("passive" for _ in references),
        pin_function="Pin_2",
        pin_functions=pin_functions,
        missing_inventory=missing_inventory,
        ambiguous_pins=ambiguous_pins,
    )
    if shared_anchor:
        return source
    return source.model_copy(
        update={"nets": {name: pins for name, pins in source.nets.items() if name != "DATA"}}
    )


def _review_policy(mode: str = "review") -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Synthetic peer assignment review test",
            ),
        )
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_peer_assignment_outlier_is_default_off_and_source_bound() -> None:
    source = _generic_peer_assignment_netlist()
    default_report = lint_report(source)
    default_finding = next(item for item in default_report.findings if item.rule_id == RULE_ID)
    default_coverage = next(
        item for item in default_report.component_peer_pin_coverage if item.rule_id == RULE_ID
    )

    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    assert default_coverage.mode == "off"
    assert default_coverage.status == "EVALUATED"
    assert default_coverage.candidate_group_count == 1
    assert default_coverage.finding_count == 1
    assert default_coverage.suppressed_candidate_count == 0

    report = lint_report(source, _review_policy())
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == (
        "Synthetic:PeerModule pin 2: generic peer assignment differs from its strict majority"
    )
    assert finding.evidence["majority_net"] == ("PEER_DATA",)
    assert finding.evidence["outlier_pins"] == ("U3.2",)
    assert finding.evidence["U1.2"] == ("PEER_DATA",)
    assert finding.evidence["U2.2"] == ("PEER_DATA",)
    assert finding.evidence["U3.2"] == ("OTHER_DATA",)
    assert finding.evidence["shared_anchor_contacts"] == ("U1.1 / U2.1 / U3.1 -> DATA",)
    assert "do not require peer pins to share a net" in finding.message

    larger_group = _generic_peer_assignment_netlist(
        references=("U1", "U2", "U3", "U4"),
        assignments=("PEER_DATA", "PEER_DATA", "PEER_DATA", "OTHER_DATA"),
    )
    larger_finding = next(
        item
        for item in lint_report(larger_group, _review_policy()).findings
        if item.rule_id == RULE_ID
    )
    assert larger_finding.evidence["majority_net"] == ("PEER_DATA",)
    assert larger_finding.evidence["outlier_pins"] == ("U4.2",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_peer_assignment_outlier_requires_a_unique_majority_and_shared_anchor() -> None:
    controls = (
        _generic_peer_assignment_netlist(assignments=("DATA", "DATA", "DATA")),
        _generic_peer_assignment_netlist(assignments=("A", "B", "C")),
        _generic_peer_assignment_netlist(references=("U1", "U2"), assignments=("DATA", "OTHER")),
        _generic_peer_assignment_netlist(
            references=("U1", "U2", "U3", "U4"),
            assignments=("A", "A", "B", "B"),
        ),
        _generic_peer_assignment_netlist(
            references=("U1", "U2", "U3", "U4"),
            assignments=("A", "A", "B", "C"),
        ),
        _generic_peer_assignment_netlist(
            references=("U1", "U2", "U3", "U4", "U5"),
            assignments=("A", "A", "B", "C", "D"),
        ),
        _generic_peer_assignment_netlist(shared_anchor=False),
        _generic_peer_assignment_netlist(dnp=("U3",)),
        _generic_peer_assignment_netlist(missing_inventory=("U3",)),
        _generic_peer_assignment_netlist(ambiguous_pins=("U3",)),
        _generic_peer_assignment_netlist(pin_functions=("DATA", "DATA", "DATA")),
        _generic_peer_assignment_netlist(electrical_types=("input", "input", "input")),
        _generic_peer_assignment_netlist(
            symbols={"U1": "Synthetic:A", "U2": "Synthetic:B", "U3": "Synthetic:C"}
        ),
        _generic_peer_assignment_netlist(references=("J1", "J2", "J3")),
    )
    for source in controls:
        assert RULE_ID not in {
            item.rule_id for item in lint_report(source, _review_policy()).findings
        }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_peer_assignment_outlier_obeys_project_policy_and_ignore_lifecycle() -> None:
    source = _generic_peer_assignment_netlist()
    finding = next(
        item for item in lint_report(source, _review_policy()).findings if item.rule_id == RULE_ID
    )

    blocked = lint_report(source, _review_policy("block"))
    assert blocked.status == "FAIL"

    disabled = lint_report(source, _review_policy("off"))
    assert any(
        item.rule_id == RULE_ID and item.disposition == "RULE_OFF" for item in disabled.findings
    )

    ignored = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic project enabled this scoped review",
                ),
            ),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project reviewed this peer exception",
                ),
            ),
        ),
    )
    assert any(
        item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_peer_assignment_outlier_is_stable_under_mapping_order() -> None:
    source = _generic_peer_assignment_netlist(
        references=("U3", "U1", "U2"),
        assignments=("OTHER_DATA", "PEER_DATA", "PEER_DATA"),
    )
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    first = [
        item for item in lint_report(source, _review_policy()).findings if item.rule_id == RULE_ID
    ]
    second = [
        item
        for item in lint_report(reordered, _review_policy()).findings
        if item.rule_id == RULE_ID
    ]

    assert [(item.subject, item.evidence, item.fingerprint) for item in second] == [
        (item.subject, item.evidence, item.fingerprint) for item in first
    ]
