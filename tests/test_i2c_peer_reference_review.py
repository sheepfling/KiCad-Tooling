"""Synthetic regression cases for shared-bus I2C reference review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import candidates
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.i2c_peer_reference_support import i2c_peer_netlist
from tests.reference_pin_role_support import with_unspecified_reference_pins

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.i2c_peer_reference_review"


def _rule_candidates(netlist):
    return tuple(item for item in candidates(netlist) if item.rule_id == RULE_ID)


def test_shared_i2c_bus_with_split_references_emits_exact_review() -> None:
    source = i2c_peer_netlist()
    (finding,) = _rule_candidates(source)

    assert finding.subject == "SDA I2C_SDA / SCL I2C_SCL: U1, U2"
    assert "does not require common grounding" in finding.message
    assert finding.evidence["participants"] == ("U1", "U2")
    assert not any(
        item.rule_id == "component.peer_power_pin_assignment_divergence"
        for item in candidates(source)
    )
    assert finding.evidence["reference_assignments"] == (
        "U1: U1.1 on I2C_SDA; U1.2 on I2C_SCL; U1.3 on GND_A",
        "U2: U2.1 on I2C_SDA; U2.2 on I2C_SCL; U2.3 on GND_B",
    )


def test_common_reference_is_a_valid_control() -> None:
    assert not _rule_candidates(i2c_peer_netlist(reference_nets={"U1": "GND", "U2": "GND"}))


def test_explicit_unspecified_vss_pins_support_split_review_and_common_control() -> None:
    split = with_unspecified_reference_pins(i2c_peer_netlist(), ("U1.3", "U2.3"))
    suffixed = with_unspecified_reference_pins(
        i2c_peer_netlist(), ("U1.3", "U2.3"), function="VSS1"
    )
    common = with_unspecified_reference_pins(
        i2c_peer_netlist(reference_nets={"U1": "GND", "U2": "GND"}),
        ("U1.3", "U2.3"),
    )
    nonreturn = with_unspecified_reference_pins(
        i2c_peer_netlist(), ("U1.3", "U2.3"), function="GPIO"
    )

    assert len(_rule_candidates(split)) == 1
    assert len(_rule_candidates(suffixed)) == 1
    assert not _rule_candidates(common)
    assert not _rule_candidates(nonreturn)


def test_one_split_among_three_shared_bus_peers_emits_one_grouped_review() -> None:
    findings = _rule_candidates(
        i2c_peer_netlist(reference_nets={"U1": "GND_A", "U2": "GND_A", "U3": "GND_B"})
    )

    assert len(findings) == 1
    assert findings[0].evidence["participants"] == ("U1", "U2", "U3")


def test_known_split_remains_reviewable_when_another_peer_is_incomplete() -> None:
    source = i2c_peer_netlist(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_C"},
        incomplete_reference_types=("U3",),
    )
    (finding,) = _rule_candidates(source)

    assert finding.evidence["participants"] == ("U1", "U2", "U3")
    assert finding.evidence["incomplete_reference_evidence"] == ("U3",)


def test_repeated_component_return_review_is_not_duplicated() -> None:
    source = i2c_peer_netlist(symbols={"U1": "Synthetic:I2cPeer", "U2": "Synthetic:I2cPeer"})
    findings = candidates(source)

    assert not _rule_candidates(source)
    assert any(
        item.rule_id == "component.peer_power_pin_assignment_divergence" for item in findings
    )


def test_shared_part_id_return_review_is_not_duplicated() -> None:
    source = i2c_peer_netlist(part_ids={"U1": "i2c-peer", "U2": "I2C-PEER"})
    findings = candidates(source)

    assert not _rule_candidates(source)
    assert any(
        item.rule_id == "component.peer_power_pin_assignment_divergence" for item in findings
    )


def test_distinct_i2c_segments_are_not_compared_as_one_bus() -> None:
    assert not _rule_candidates(
        i2c_peer_netlist(
            reference_nets={"U1": "GND_A", "U2": "GND_B"},
            signal_nets={
                "U1": ("I2C_A_SDA", "I2C_A_SCL"),
                "U2": ("I2C_B_SDA", "I2C_B_SCL"),
            },
        )
    )


def test_dnp_incomplete_reference_and_shield_pins_are_not_ground_evidence() -> None:
    assert not _rule_candidates(
        i2c_peer_netlist(reference_nets={"U1": "GND_A", "U2": "GND_B"}, dnp=("U2",))
    )
    assert not _rule_candidates(
        i2c_peer_netlist(
            reference_nets={"U1": "GND_A", "U2": "GND_B"},
            incomplete_reference_types=("U2",),
        )
    )
    assert not _rule_candidates(
        i2c_peer_netlist(
            reference_nets={"U1": "GND", "U2": "GND"},
            shield_nets={"U1": "CHASSIS_A", "U2": "CHASSIS_B"},
        )
    )


def test_split_reference_candidate_is_stable_under_mapping_order() -> None:
    source = i2c_peer_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
        }
    )
    (original,) = _rule_candidates(source)
    (repeated,) = _rule_candidates(reordered)

    assert (repeated.subject, repeated.evidence) == (original.subject, original.evidence)


def test_report_coverage_accounts_for_unique_and_component_covered_buses() -> None:
    def report(source, policy: DesignLintPolicy | None = None):
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-i2c-peer-reference",
            observed=source,
            netlist_sha256="c" * 64,
        )
        return evaluate(coach.project_id, coach, policy or DesignLintPolicy())

    unique = report(i2c_peer_netlist())
    assert unique.i2c_peer_reference_coverage is not None
    assert unique.i2c_peer_reference_coverage.netlist_sha256 == "c" * 64
    assert unique.i2c_peer_reference_coverage.candidate_group_count == 1
    assert unique.i2c_peer_reference_coverage.component_peer_covered_bus_count == 0

    repeated = report(
        i2c_peer_netlist(symbols={"U1": "Synthetic:I2cPeer", "U2": "Synthetic:I2cPeer"})
    )
    assert repeated.i2c_peer_reference_coverage is not None
    assert repeated.i2c_peer_reference_coverage.candidate_group_count == 0
    assert repeated.i2c_peer_reference_coverage.component_peer_covered_bus_count == 1
    assert repeated.i2c_peer_reference_coverage.entries[0].disposition == (
        "COMPONENT_PEER_REVIEW_COVERS"
    )


def test_project_override_and_exact_ignore_change_disposition_not_detection() -> None:
    source = i2c_peer_netlist()

    def lint(policy: DesignLintPolicy):
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-i2c-peer-reference",
            observed=source,
            netlist_sha256="c" * 64,
        )
        return evaluate(coach.project_id, coach, policy)

    baseline = lint(DesignLintPolicy())
    baseline_finding = next(item for item in baseline.findings if item.rule_id == RULE_ID)
    disabled = lint(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project-level decision",
                ),
            )
        )
    )
    disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
    assert (disabled_finding.subject, disabled_finding.evidence) == (
        baseline_finding.subject,
        baseline_finding.evidence,
    )
    assert (disabled_finding.mode, disabled_finding.disposition) == ("off", "RULE_OFF")
    assert disabled.i2c_peer_reference_coverage is not None
    assert (
        disabled.i2c_peer_reference_coverage.mode,
        disabled.i2c_peer_reference_coverage.candidate_group_count,
    ) == (
        "off",
        1,
    )

    ignored = lint(
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline_finding.fingerprint,
                    reason="Synthetic reviewed exception",
                ),
            )
        )
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert (ignored_finding.subject, ignored_finding.evidence) == (
        baseline_finding.subject,
        baseline_finding.evidence,
    )
    assert (ignored_finding.mode, ignored_finding.disposition) == ("review", "IGNORED")
    assert ignored.i2c_peer_reference_coverage is not None
    assert ignored.i2c_peer_reference_coverage.candidate_group_count == 1
