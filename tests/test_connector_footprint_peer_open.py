"""Review incomplete generic pin assignments across footprint-alias connectors."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import (
    FOOTPRINT_OPEN_RULE_ID as RULE_ID,
)
from tests.connector_footprint_peer_support import (
    lint_report,
    peer_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]


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
