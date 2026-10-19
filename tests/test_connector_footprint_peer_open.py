"""Review incomplete generic pin assignments across footprint-alias connectors."""

from __future__ import annotations

import json

import pytest

from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)
from tests.connector_footprint_peer_support import (
    FOOTPRINT_ALL_OPEN_RULE_ID as ALL_OPEN_RULE_ID,
)
from tests.connector_footprint_peer_support import (
    FOOTPRINT_OPEN_RULE_ID as RULE_ID,
)
from tests.connector_footprint_peer_support import (
    lint_report,
    peer_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


def test_all_generic_contacts_open_across_footprint_aliases_is_opt_in_review() -> None:
    source = peer_netlist(assignments=(("GND", "GND"), (None, None)))
    default_report = lint_report(source)
    finding = next(item for item in default_report.findings if item.rule_id == ALL_OPEN_RULE_ID)

    assert default_report.status == "PASS"
    assert finding.mode == "off"
    assert finding.disposition == "RULE_OFF"
    assert finding.evidence["assignments"] == (
        "J1.2=<unassigned>",
        "J2.2=<unassigned>",
    )
    assert finding.evidence["open_pins"] == ("J1.2", "J2.2")
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "do not establish that the contact must connect" in finding.message
    coverage = default_report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.all_open_peer_pin_group_count == 1
    assert alias.unanchored_all_open_peer_pin_group_count == 0
    assert alias.all_open_finding_count == 1

    reviewed = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=ALL_OPEN_RULE_ID,
                    mode="review",
                    reason="Synthetic project chooses to review every generic alias contact.",
                ),
            )
        ),
    )
    assert reviewed.status == "REVIEW"
    reviewed_finding = next(item for item in reviewed.findings if item.rule_id == ALL_OPEN_RULE_ID)
    assert reviewed_finding.mode == "review"
    assert reviewed_finding.disposition == "OPEN"


def test_version_three_report_defaults_new_footprint_coverage_counts() -> None:
    report = lint_report(peer_netlist(assignments=(("GND", "GND"), ("DATA", "DATA"))))
    payload = report.model_dump(mode="json")
    payload["schema_version"] = "3"
    alias = payload["connector_peer_pin_coverage"]["footprint_alias_coverage"]
    for field in (
        "all_open_peer_pin_group_count",
        "unanchored_all_open_peer_pin_group_count",
        "all_open_finding_count",
    ):
        alias.pop(field)

    restored = DesignLintReport.model_validate_json(json.dumps(payload))

    assert restored.schema_version == "3"
    assert restored.connector_peer_pin_coverage is not None
    assert restored.connector_peer_pin_coverage.footprint_alias_coverage.all_open_finding_count == 0


def test_all_open_footprint_alias_requires_a_shared_anchor_and_eligible_generic_metadata() -> None:
    unanchored = lint_report(
        peer_netlist(assignments=(("GND_A", "GND_B"), (None, None)))
    ).connector_peer_pin_coverage
    assert unanchored is not None
    assert unanchored.footprint_alias_coverage.all_open_peer_pin_group_count == 1
    assert unanchored.footprint_alias_coverage.unanchored_all_open_peer_pin_group_count == 1
    assert unanchored.footprint_alias_coverage.all_open_finding_count == 0

    named = peer_netlist(
        assignments=(("GND", "GND"), (None, None)),
        functions=("Pin_1", "SIGNAL"),
    )
    non_signal = peer_netlist(assignments=(("GND", "GND"), (None, None))).model_copy(
        update={
            "pin_electrical_types": {
                **peer_netlist(assignments=(("GND", "GND"), (None, None))).pin_electrical_types,
                "J1.2": "power_in",
                "J2.2": "power_in",
            }
        }
    )
    common = peer_netlist(assignments=(("GND", "GND"), ("DATA", "DATA")))
    for source in (named, non_signal, common):
        report = lint_report(source)
        assert not any(item.rule_id == ALL_OPEN_RULE_ID for item in report.findings)


def test_all_open_footprint_alias_is_stable_under_mapping_order() -> None:
    source = peer_netlist(assignments=(("GND", "GND"), (None, None)))
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
    original = next(
        item for item in lint_report(source).findings if item.rule_id == ALL_OPEN_RULE_ID
    )
    shuffled = next(
        item for item in lint_report(reordered).findings if item.rule_id == ALL_OPEN_RULE_ID
    )
    assert (shuffled.fingerprint, shuffled.evidence) == (original.fingerprint, original.evidence)


def test_all_open_footprint_alias_obeys_block_off_and_exact_ignore_policy() -> None:
    source = peer_netlist(assignments=(("GND", "GND"), (None, None)))
    review_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=ALL_OPEN_RULE_ID,
                mode="review",
                reason="Synthetic project opts into this all-open alias review.",
            ),
        )
    )
    finding = next(
        item
        for item in lint_report(source, review_policy).findings
        if item.rule_id == ALL_OPEN_RULE_ID
    )
    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=ALL_OPEN_RULE_ID,
                    mode="block",
                    reason="Synthetic policy exercises configurable blocking.",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"
    assert (
        next(item for item in blocked.findings if item.rule_id == ALL_OPEN_RULE_ID).mode == "block"
    )

    ignored = lint_report(
        source,
        DesignLintPolicy(
            rules=review_policy.rules,
            ignores=(
                DesignLintIgnore(
                    rule_id=ALL_OPEN_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic policy records an intentionally unused contact.",
                ),
            ),
        ),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == ALL_OPEN_RULE_ID)
    assert ignored_finding.disposition == "IGNORED"


def test_generic_open_contact_on_one_footprint_peer_is_reviewed() -> None:
    report = lint_report(peer_netlist(assignments=(("GND", "GND"), ("DATA_A", None))))
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review"
    assert finding.subject == "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2"
    assert finding.evidence["assignments"] == ("J1.2=DATA_A", "J2.2=<unassigned>")
    assert finding.evidence["open_pins"] == ("J2.2",)
    assert finding.evidence["symbols"] == (
        "Synthetic:GenericPort",
        "Synthetic:GenericPortAlias",
    )
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "does not prove that this contact must connect" in finding.message

    coverage = report.connector_peer_pin_coverage
    assert coverage is not None
    alias = coverage.footprint_alias_coverage
    assert alias.netlist_sha256 == "a" * 64
    assert alias.candidate_group_count == alias.eligible_peer_group_count == 1
    assert alias.peer_scope_group_count == 1
    assert alias.open_peer_pin_group_count == 1
    assert alias.unanchored_open_peer_pin_group_count == 0
    assert alias.open_outlier_finding_count == 1


def test_numeric_open_contact_on_one_footprint_peer_is_reviewed() -> None:
    report = lint_report(
        peer_netlist(
            assignments=(("GND", "GND"), ("DATA_A", None)),
            functions=("1", "7"),
        )
    )
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].evidence["pin_function"] == ("7",)
    assert findings[0].evidence["open_pins"] == ("J2.2",)
    assert findings[0].evidence["common_anchor_pin_numbers"] == ("1",)


def test_common_open_and_unanchored_controls_do_not_prompt() -> None:
    common = lint_report(peer_netlist(assignments=(("GND", "GND"), ("DATA", "DATA"))))
    assert not any(item.rule_id == RULE_ID for item in common.findings)
    common_coverage = common.connector_peer_pin_coverage
    assert common_coverage is not None
    assert common_coverage.footprint_alias_coverage.open_outlier_finding_count == 0

    unanchored = lint_report(peer_netlist(assignments=(("GND_A", "GND_B"), ("DATA_A", None))))
    assert not any(item.rule_id == RULE_ID for item in unanchored.findings)
    unanchored_coverage = unanchored.connector_peer_pin_coverage
    assert unanchored_coverage is not None
    alias = unanchored_coverage.footprint_alias_coverage
    assert alias.open_peer_pin_group_count == 1
    assert alias.unanchored_open_peer_pin_group_count == 1
    assert alias.open_outlier_finding_count == 0

    all_open = lint_report(peer_netlist(assignments=(("GND", "GND"), (None, None))))
    assert not any(item.rule_id == RULE_ID for item in all_open.findings)
    all_open_coverage = all_open.connector_peer_pin_coverage
    assert all_open_coverage is not None
    assert all_open_coverage.footprint_alias_coverage.open_peer_pin_group_count == 0


def test_named_incomplete_and_ineligible_aliases_do_not_prompt() -> None:
    cases = (
        peer_netlist(
            assignments=(("GND", "GND"), ("DATA_A", None)),
            functions=("Pin_1", "TXD"),
        ),
        peer_netlist(
            assignments=(("GND", "GND"), ("DATA_A", None)),
            missing_metadata_pin="J2.2",
        ),
        peer_netlist(assignments=(("GND", "GND"), ("DATA_A", None)), part_id="SYNTHETIC-ID"),
        peer_netlist(assignments=(("GND", "GND"), ("DATA_A", None)), dnp=("J2",)),
        peer_netlist(
            assignments=(("GND", "GND"), ("DATA_A", None)),
            incomplete_inventory=True,
        ),
        peer_netlist(
            assignments=(("GND", "GND"), ("DATA_A", None)),
            ambiguous_pin="J1.2",
        ),
    )
    for observed in cases:
        report = lint_report(observed)
        assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_open_peer_scan_is_stable_under_mapping_order() -> None:
    source = peer_netlist(assignments=(("GND", "GND"), ("DATA_A", None)))
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


def test_open_peer_review_obeys_policy_and_exact_ignore() -> None:
    source = peer_netlist(assignments=(("GND", "GND"), ("DATA_A", None)))
    finding = next(item for item in lint_report(source).findings if item.rule_id == RULE_ID)

    blocked = lint_report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic fixture exercises the project-selected mode.",
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
                    reason="Synthetic fixture records an intentional open-contact heuristic opt-out.",
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
                    reason="Synthetic fixture records an intentionally unused connector contact.",
                ),
            )
        ),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"
