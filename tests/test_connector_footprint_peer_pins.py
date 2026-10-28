"""Review-only connector peer heuristic across PART_ID-free footprint aliases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_pins import (
    scan_connector_footprint_peer_pin_assignments,
)
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.connector_footprint_peer_support import (
    FOOTPRINT_PEER_RULE_ID as RULE_ID,
)
from tests.connector_footprint_peer_support import (
    NETLIST_SHA256,
    PeerNetlistOverrides,
    lint_report,
    peer_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


def test_generic_assignment_difference_between_footprint_aliases_is_reviewed() -> None:
    report = lint_report(peer_netlist())
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == ("Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2")
    assert finding.evidence["assignments"] == ("J1.2=DATA_A", "J2.2=DATA_B")
    assert finding.evidence["symbols"] == (
        "Synthetic:GenericPort",
        "Synthetic:GenericPortAlias",
    )
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "do not prove the contacts should be common" in finding.message

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.status == "EVALUATED"
    assert alias.netlist_sha256 == NETLIST_SHA256
    assert alias.candidate_group_count == alias.eligible_peer_group_count == 1
    assert alias.peer_scope_group_count == 1
    assert alias.evaluated_pin_group_count == alias.compared_pin_group_count == 2
    assert alias.common_assignment_pin_group_count == 1
    assert alias.generic_different_assignment_pin_group_count == 1
    assert alias.divergence_finding_count == 1


def test_numeric_pin_function_difference_is_reviewed_as_generic() -> None:
    report = lint_report(
        peer_netlist(
            assignments=(("GND", "GND"), ("DATA_A", "DATA_B")),
            functions=("1", "7"),
        )
    )
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert len(findings) == 1
    assert findings[0].subject == "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2"
    assert findings[0].evidence["assignments"] == ("J1.2=DATA_A", "J2.2=DATA_B")
    assert findings[0].evidence["pin_function"] == ("7",)


def test_common_assignment_and_named_pin_controls_are_quiet() -> None:
    common = lint_report(peer_netlist(assignments=(("GND", "GND"), ("DATA", "DATA"))))
    assert not any(item.rule_id == RULE_ID for item in common.findings)
    common_coverage = common.connector_peer_pin_coverage
    assert common_coverage is not None
    assert common_coverage.footprint_alias_coverage.status == "NO_DIVERGENT_ASSIGNMENTS"

    named = lint_report(
        peer_netlist(functions=("Pin_1", "TXD"), assignments=(("GND", "GND"), ("TX1", "TX2")))
    )
    assert not any(item.rule_id == RULE_ID for item in named.findings)
    named_coverage = named.connector_peer_pin_coverage
    assert named_coverage is not None
    assert (
        named_coverage.footprint_alias_coverage.non_generic_different_assignment_pin_group_count
        == 1
    )


def test_incomplete_or_unanchored_alias_evidence_is_reported_without_a_finding() -> None:
    incomplete = lint_report(peer_netlist(incomplete_inventory=True))
    incomplete_coverage = incomplete.connector_peer_pin_coverage
    assert incomplete_coverage is not None
    alias = incomplete_coverage.footprint_alias_coverage
    assert alias.status == "INCOMPLETE_EVIDENCE"
    assert alias.incomplete_pin_inventory_group_count == 1
    assert alias.eligible_peer_group_count == 0
    assert not any(item.rule_id == RULE_ID for item in incomplete.findings)

    unanchored = lint_report(peer_netlist(assignments=(("GND_A", "GND_B"), ("DATA_A", "DATA_B"))))
    unanchored_coverage = unanchored.connector_peer_pin_coverage
    assert unanchored_coverage is not None
    alias = unanchored_coverage.footprint_alias_coverage
    assert alias.status == "NO_SHARED_ASSIGNMENT_ANCHOR"
    assert alias.common_anchor_group_count == 0
    assert alias.unanchored_different_assignment_pin_group_count == 2
    assert not any(item.rule_id == RULE_ID for item in unanchored.findings)


@pytest.mark.parametrize(
    ("kwargs", "field", "expected", "expected_status"),
    (
        (
            {"missing_metadata_pin": "J2.2"},
            "incomplete_pin_metadata_group_count",
            1,
            "INCOMPLETE_EVIDENCE",
        ),
        (
            {"open_pin": "J1.2"},
            "unassigned_assignment_pin_group_count",
            1,
            "PARTIALLY_EVALUATED",
        ),
        (
            {"ambiguous_pin": "J1.2"},
            "ambiguous_assignment_pin_group_count",
            1,
            "PARTIALLY_EVALUATED",
        ),
    ),
    ids=("missing-native-metadata", "open-pin", "ambiguous-pin"),
)
def test_incomplete_alias_assignments_are_counted_and_do_not_become_divergences(
    kwargs: PeerNetlistOverrides, field: str, expected: int, expected_status: str
) -> None:
    report = lint_report(peer_netlist(**kwargs))
    assert not any(item.rule_id == RULE_ID for item in report.findings)
    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.status == expected_status
    assert getattr(alias, field) == expected


def test_part_id_dnp_and_separate_peer_groups_exclude_footprint_alias_comparison() -> None:
    for observed in (
        peer_netlist(part_id="SYNTHETIC-PART-001"),
        peer_netlist(dnp=("J2",)),
    ):
        report = lint_report(observed)
        assert not any(item.rule_id == RULE_ID for item in report.findings)
        coverage = report.connector_peer_pin_coverage
        assert coverage is not None
        assert coverage.footprint_alias_coverage.candidate_group_count == 0

    isolated = scan_connector_footprint_peer_pin_assignments(
        peer_netlist(),
        peer_assignment_groups={
            "J1": ("usb-port", "synthetic current review"),
            "J2": ("uart-port", "synthetic current review"),
        },
    )
    assert isolated.peer_scope_group_count == 0
    assert isolated.finding_count == 0


def test_alias_scan_is_stable_under_mapping_order() -> None:
    source = peer_netlist()
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
    initial = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)
    shuffled = next(item for item in lint_report(reordered).findings if item.rule_id == RULE_ID)
    assert (shuffled.fingerprint, shuffled.evidence) == (initial.fingerprint, initial.evidence)


def test_footprint_alias_review_obeys_project_policy_and_ignore_fingerprint() -> None:
    source = peer_netlist()
    default = lint_report(source)
    finding = next(item for item in default.findings if item.rule_id == RULE_ID)

    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic fixture explicitly tests project policy selection",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"

    disabled = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic control records an intentionally disabled heuristic",
                ),
            )
        ),
    )
    disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert disabled_finding.disposition == "RULE_OFF"

    ignored = lint_report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic control records an approved intentional port difference",
                ),
            )
        ),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"
