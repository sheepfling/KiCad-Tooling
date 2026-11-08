"""Review numeric-only connector contacts open on exact-symbol peers."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_comparison_scope_types import ConnectorComparisonScope
from kicad_tooling.hwrepo.connector_coverage_models import ConnectorMappedPinEvidence
from kicad_tooling.hwrepo.connector_numeric_peer_open_outliers import (
    ConnectorNumericPeerOpenCandidate,
    generic_numeric_connector_peer_pin_open_outliers,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.connector_numeric_peer_open import (
    numeric_open_connector_part_id_aliases,
    numeric_open_connector_peers,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]

RULE_ID = "connector.generic_peer_pin_open_outlier"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_numeric_generic_contact_open_on_one_exact_symbol_peer_is_reviewed() -> None:
    source = numeric_open_connector_peers()
    (candidate,) = generic_numeric_connector_peer_pin_open_outliers(source)

    assert isinstance(candidate, ConnectorNumericPeerOpenCandidate)
    assert candidate.source_evidence.observed is source
    assert candidate.rule_id == RULE_ID
    assert candidate.evidence["J1.2"] == ("GND",)
    assert candidate.evidence["J2.2"] == ("GND",)
    assert candidate.evidence["J3.2"] == ()
    assert candidate.evidence["shared_anchor_contacts"] == ("J1.1 / J2.1 / J3.1 -> +3V3",)

    report = evaluate("synthetic-numeric-peer-open", coach(source), DesignLintPolicy())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert report.connector_peer_pin_coverage is not None
    assert report.connector_peer_pin_coverage.generic_peer_pin_open_outlier_finding_count == 1


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_numeric_contact_open_across_exact_part_id_aliases_is_reviewed_once() -> None:
    source = numeric_open_connector_part_id_aliases()

    (candidate,) = generic_numeric_connector_peer_pin_open_outliers(source)

    assert isinstance(candidate, ConnectorNumericPeerOpenCandidate)
    assert candidate.evidence["peer_identity_basis"] == ("part_id",)
    assert candidate.evidence["peer_identity"] == ("SYNTHETIC-CONNECTOR-PEER",)
    assert candidate.evidence["peer_symbols"] == (
        "Connector_Alias_A",
        "Connector_Alias_B",
    )
    assert candidate.evidence["J1.2"] == ("GND",)
    assert candidate.evidence["J2.2"] == ("GND",)
    assert candidate.evidence["J3.2"] == ()
    assert candidate.evidence["shared_anchor_contacts"] == ("J1.1 / J2.1 / J3.1 -> +3V3",)
    report = evaluate("synthetic-part-id-peer-open", coach(source), DesignLintPolicy())
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].evidence["peer_identity_basis"] == ("part_id",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_numeric_peer_open_candidate_is_stable_under_input_reordering() -> None:
    source = numeric_open_connector_peers()
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

    (original,) = generic_numeric_connector_peer_pin_open_outliers(source)
    (permuted,) = generic_numeric_connector_peer_pin_open_outliers(reordered)
    assert permuted == original
    assert fingerprint(permuted) == fingerprint(original)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_part_id_alias_candidate_is_stable_under_input_reordering() -> None:
    source = numeric_open_connector_part_id_aliases()
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

    (original,) = generic_numeric_connector_peer_pin_open_outliers(source)
    (permuted,) = generic_numeric_connector_peer_pin_open_outliers(reordered)
    assert permuted == original
    assert fingerprint(permuted) == fingerprint(original)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "source",
    (
        numeric_open_connector_peers(open_references=()),
        numeric_open_connector_peers(anchor_nets=("PORT_A", "PORT_B", "PORT_C")),
        numeric_open_connector_peers(dnp_references=("J3",)),
    ),
    ids=("common-assignment", "no-common-anchor", "open-peer-is-dnp"),
)
def test_common_and_incomplete_context_controls_are_quiet(source: NetlistContract) -> None:
    assert generic_numeric_connector_peer_pin_open_outliers(source) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "source",
    (
        numeric_open_connector_part_id_aliases(open_references=()),
        numeric_open_connector_part_id_aliases(anchor_nets=("PORT_A", "PORT_B", "PORT_C")),
        numeric_open_connector_part_id_aliases(
            part_ids=("SYNTHETIC-ONE", "SYNTHETIC-ONE", "SYNTHETIC-TWO")
        ),
        numeric_open_connector_part_id_aliases(dnp_references=("J3",)),
    ),
    ids=("common-assignment", "no-common-anchor", "different-part-id", "open-peer-is-dnp"),
)
def test_part_id_alias_controls_are_quiet(source: NetlistContract) -> None:
    assert generic_numeric_connector_peer_pin_open_outliers(source) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_part_id_aliases_obey_reviewed_peer_scopes_and_exclusions() -> None:
    source = numeric_open_connector_part_id_aliases()
    separated = {
        "J1": ConnectorComparisonScope("first", "synthetic interface A"),
        "J2": ConnectorComparisonScope("first", "synthetic interface A"),
        "J3": ConnectorComparisonScope("second", "synthetic interface B"),
    }
    shared = {
        reference: ConnectorComparisonScope("shared", "same synthetic interface")
        for reference in ("J1", "J2", "J3")
    }

    assert (
        generic_numeric_connector_peer_pin_open_outliers(
            source,
            peer_assignment_groups=separated,
        )
        == ()
    )
    assert (
        generic_numeric_connector_peer_pin_open_outliers(
            source,
            not_applicable_references=("J3",),
        )
        == ()
    )
    (candidate,) = generic_numeric_connector_peer_pin_open_outliers(
        source,
        peer_assignment_groups=shared,
    )
    assert candidate.evidence["peer_assignment_group"] == ("shared",)

    split_alias_source = numeric_open_connector_part_id_aliases(open_references=("J2", "J3"))
    (exact_scope_candidate,) = generic_numeric_connector_peer_pin_open_outliers(
        split_alias_source,
        peer_assignment_groups=separated,
    )
    assert exact_scope_candidate.evidence["peer_identity_basis"] == ("exact_symbol",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_no_connect_marker_still_prompts_but_mapping_and_not_applicable_suppress() -> None:
    source = numeric_open_connector_peers().model_copy(
        update={"unconnected_nets": {"unconnected-(J3-2)": ("J3.2",)}}
    )
    mapped = {
        "J3.2": ConnectorMappedPinEvidence(
            interface_pin_number="2",
            interface_signal="optional contact",
            component_pin="J3.2",
        )
    }

    (candidate,) = generic_numeric_connector_peer_pin_open_outliers(source)
    assert candidate.rule_id == RULE_ID
    assert (
        generic_numeric_connector_peer_pin_open_outliers(
            numeric_open_connector_peers(), reviewed_connector_pins=mapped
        )
        == ()
    )
    assert (
        generic_numeric_connector_peer_pin_open_outliers(
            numeric_open_connector_peers(), not_applicable_references=("J3",)
        )
        == ()
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ambiguous_or_split_assignments_and_incomplete_metadata_are_quiet() -> None:
    source = numeric_open_connector_peers()
    ambiguous = source.model_copy(update={"nets": {**source.nets, "OTHER": ("J1.2",)}})
    split = source.model_copy(update={"nets": {**source.nets, "GND_B": ("J2.2",)}})
    incomplete_inventory = source.model_copy(
        update={"component_pin_numbers": {**source.component_pin_numbers, "J3": ("1", "2")}}
    )
    incomplete_metadata = source.model_copy(
        update={
            "pin_electrical_types": {
                pin: value for pin, value in source.pin_electrical_types.items() if pin != "J2.3"
            }
        }
    )

    assert generic_numeric_connector_peer_pin_open_outliers(ambiguous) == ()
    assert generic_numeric_connector_peer_pin_open_outliers(split) == ()
    assert generic_numeric_connector_peer_pin_open_outliers(incomplete_inventory) == ()
    assert generic_numeric_connector_peer_pin_open_outliers(incomplete_metadata) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_current_peer_assignment_groups_partition_comparison() -> None:
    source = numeric_open_connector_peers()
    isolated = {
        "J1": ConnectorComparisonScope("port-a", "separate synthetic port"),
        "J2": ConnectorComparisonScope("port-a", "separate synthetic port"),
        "J3": ConnectorComparisonScope("port-b", "separate synthetic port"),
    }
    shared = {
        reference: ConnectorComparisonScope("shared", "same synthetic interface")
        for reference in ("J1", "J2", "J3")
    }

    assert (
        generic_numeric_connector_peer_pin_open_outliers(source, peer_assignment_groups=isolated)
        == ()
    )
    (candidate,) = generic_numeric_connector_peer_pin_open_outliers(
        source, peer_assignment_groups=shared
    )
    assert candidate.evidence["peer_assignment_group"] == ("shared",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_supports_project_review_block_and_off_modes() -> None:
    source = numeric_open_connector_peers()
    blocked = evaluate(
        "synthetic-numeric-peer-open",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic interface requires a disposition",
                ),
            )
        ),
    )
    disabled = evaluate(
        "synthetic-numeric-peer-open",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project records intentional isolation",
                ),
            )
        ),
    )
    reviewed = evaluate("synthetic-numeric-peer-open", coach(source), DesignLintPolicy())
    finding = next(item for item in reviewed.findings if item.rule_id == RULE_ID)
    ignored = evaluate(
        "synthetic-numeric-peer-open",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic pinout review accepts the open contact",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert disabled_finding.disposition == "RULE_OFF"
    assert ignored_finding.disposition == "IGNORED"
