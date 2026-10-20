"""Deterministic CAN shared-pair reference-domain regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.can_peer_reference_scan import scan_can_peer_references
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_can_candidates import can_peer_reference_candidates
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)
from tests.can_peer_reference_support import can_peer_reference_netlist
from tests.design_lint_fixtures import coach
from tests.reference_pin_role_support import with_unspecified_reference_pins

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.can_peer_reference_review"


def _rule_findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def test_shared_can_line_pair_with_split_references_emits_one_exact_review() -> None:
    source = can_peer_reference_netlist()
    scan = scan_can_peer_references(source)
    report = evaluate("synthetic-can-reference", coach(source), DesignLintPolicy())
    findings = _rule_findings(report)

    assert len(scan.buses) == 1
    assert scan.buses[0].disposition == "SPLIT_REFERENCE_REVIEW"
    assert len(findings) == 1
    assert findings[0].mode == "review"
    assert findings[0].evidence == {
        "CANH": ("CAN_HIGH",),
        "CANL": ("CAN_LOW",),
        "participants": ("U1", "U2"),
        "line_assignments": (
            "U1: U1.1 on CAN_HIGH; U1.2 on CAN_LOW",
            "U2: U2.1 on CAN_HIGH; U2.2 on CAN_LOW",
        ),
        "reference_assignments": (
            "U1: U1.3 on GND_A",
            "U2: U2.3 on GND_B",
        ),
    }
    assert "common return" in findings[0].message
    assert "bus.can_peer_assignment_divergence" not in {item.rule_id for item in report.findings}
    assert report.can_peer_reference_coverage is not None
    assert report.can_peer_reference_coverage.netlist_sha256 == report.netlist_sha256
    assert report.can_peer_reference_coverage.candidate_group_count == 1


def test_common_reference_distinct_can_buses_dnp_and_shield_are_controls() -> None:
    common = evaluate(
        "synthetic-can-reference",
        coach(can_peer_reference_netlist(reference_nets={"U1": "GND", "U2": "GND"})),
        DesignLintPolicy(),
    )
    separate = evaluate(
        "synthetic-can-reference",
        coach(
            can_peer_reference_netlist(
                line_nets={"U1": ("CANH_A", "CANL_A"), "U2": ("CANH_B", "CANL_B")}
            )
        ),
        DesignLintPolicy(),
    )
    dnp = evaluate(
        "synthetic-can-reference",
        coach(can_peer_reference_netlist(dnp=("U2",))),
        DesignLintPolicy(),
    )
    shield = evaluate(
        "synthetic-can-reference",
        coach(can_peer_reference_netlist(reference_functions={"U1": "SHIELD", "U2": "SHIELD"})),
        DesignLintPolicy(),
    )

    assert not _rule_findings(common)
    assert common.can_peer_reference_coverage.entries[0].disposition == "COMMON_REFERENCE"
    assert not _rule_findings(separate)
    assert separate.can_peer_reference_coverage.status == "NO_SHARED_CAN_BUSES"
    assert not _rule_findings(dnp)
    assert dnp.can_peer_reference_coverage.status == "NO_SHARED_CAN_BUSES"
    assert not _rule_findings(shield)
    assert shield.can_peer_reference_coverage.entries[0].disposition == "INCOMPLETE"


def test_explicit_unspecified_vss_pins_support_split_review_and_common_control() -> None:
    split = with_unspecified_reference_pins(can_peer_reference_netlist(), ("U1.3", "U2.3"))
    common = with_unspecified_reference_pins(
        can_peer_reference_netlist(reference_nets={"U1": "GND", "U2": "GND"}),
        ("U1.3", "U2.3"),
    )
    nonreturn = with_unspecified_reference_pins(
        can_peer_reference_netlist(), ("U1.3", "U2.3"), function="GPIO"
    )

    assert (
        len(_rule_findings(evaluate("synthetic-can-reference", coach(split), DesignLintPolicy())))
        == 1
    )
    assert not _rule_findings(
        evaluate("synthetic-can-reference", coach(common), DesignLintPolicy())
    )
    assert not _rule_findings(
        evaluate("synthetic-can-reference", coach(nonreturn), DesignLintPolicy())
    )


def test_known_split_survives_an_incomplete_peer_and_keeps_coverage_visible() -> None:
    source = can_peer_reference_netlist(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_C"},
        incomplete_reference_types=("U3",),
    )
    report = evaluate("synthetic-can-reference", coach(source), DesignLintPolicy())

    assert len(_rule_findings(report)) == 1
    coverage = report.can_peer_reference_coverage
    assert coverage is not None
    assert coverage.status == "INCOMPLETE"
    assert coverage.entries[0].disposition == "PARTIAL_SPLIT_REFERENCE_REVIEW"
    assert coverage.entries[0].incomplete_references == ("U3",)


def test_component_peer_duplicate_suppression_requires_every_reference_assignment() -> None:
    source = can_peer_reference_netlist()
    scan = scan_can_peer_references(source)
    assignments = tuple(
        (pin.pin, pin.net)
        for endpoint in scan.reviews[0].endpoints
        for pin in endpoint.reference_pins
    )
    complete_finding = Candidate(
        rule_id="component.peer_power_pin_assignment_divergence",
        subject="synthetic component-peer return review",
        message="synthetic duplicate coverage",
        evidence={"peer_role": ("ground/return",), **{pin: (net,) for pin, net in assignments}},
    )
    partial_finding = Candidate(
        rule_id="component.peer_power_pin_assignment_divergence",
        subject="synthetic partial component-peer return review",
        message="synthetic partial coverage",
        evidence={
            "peer_role": ("ground/return",),
            assignments[0][0]: (assignments[0][1],),
        },
    )

    assert not can_peer_reference_candidates(source, scan, (complete_finding,))
    assert len(can_peer_reference_candidates(source, scan, (partial_finding,))) == 1


def test_rule_policy_ignore_and_mapping_order_are_deterministic() -> None:
    source = can_peer_reference_netlist()
    baseline = evaluate("synthetic-can-reference", coach(source), DesignLintPolicy())
    finding = _rule_findings(baseline)[0]
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
        }
    )
    reordered_finding = _rule_findings(
        evaluate("synthetic-can-reference", coach(reordered), DesignLintPolicy())
    )[0]
    blocked = evaluate(
        "synthetic-can-reference",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="The synthetic board requires review to block",
                ),
            )
        ),
    )
    disabled = evaluate(
        "synthetic-can-reference",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="The synthetic board intentionally isolates references",
                ),
            )
        ),
    )
    ignored = evaluate(
        "synthetic-can-reference",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="The synthetic split is an intentional isolated segment",
                ),
            )
        ),
    )

    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        finding.fingerprint,
        finding.evidence,
    )
    assert blocked.status == "FAIL"
    assert _rule_findings(blocked)[0].mode == "block"
    assert disabled.can_peer_reference_coverage.mode == "off"
    assert _rule_findings(disabled)[0].disposition == "RULE_OFF"
    assert _rule_findings(ignored)[0].disposition == "IGNORED"
