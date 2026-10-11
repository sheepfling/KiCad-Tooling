"""Synthetic regressions for direct SPI peers with split references."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import candidates
from kicad_tooling.hwrepo.design_lint_spi_candidates import spi_peer_reference_candidates
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.spi_peer_reference_scan import scan_spi_peer_references
from tests.spi_peer_reference_support import spi_peer_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.spi_peer_reference_review"


def _rule_candidates(netlist):
    return tuple(item for item in candidates(netlist) if item.rule_id == RULE_ID)


def test_shared_sck_with_split_references_emits_review_and_exact_evidence() -> None:
    source = spi_peer_netlist()
    (finding,) = _rule_candidates(source)

    assert finding.subject == "SCK SPI_SCK: U1, U2"
    assert "does not require a common return" in finding.message
    assert finding.evidence["participants"] == ("U1", "U2")
    assert finding.evidence["SCK"] == ("SPI_SCK",)
    assert finding.evidence["reference_assignments"] == (
        "U1: U1.1 on SPI_SCK; U1.3 on GND_A",
        "U2: U2.1 on SPI_SCK; U2.3 on GND_B",
    )
    assert "bus.spi_peer_voltage_review" not in {item.rule_id for item in candidates(source)}


def test_common_reference_is_a_valid_control() -> None:
    assert not _rule_candidates(spi_peer_netlist(reference_nets={"U1": "GND", "U2": "GND"}))


def test_distinct_clock_segments_are_not_compared() -> None:
    source = spi_peer_netlist(clock_nets={"U1": "SPI_A_SCK", "U2": "SPI_B_SCK"})

    assert scan_spi_peer_references(source).buses == ()
    assert not _rule_candidates(source)


def test_dnp_incomplete_and_shield_only_endpoints_are_not_ground_evidence() -> None:
    assert not _rule_candidates(spi_peer_netlist(dnp=("U2",)))
    incomplete = scan_spi_peer_references(spi_peer_netlist(incomplete_reference_types=("U2",)))
    assert len(incomplete.buses) == 1
    assert incomplete.buses[0].disposition == "INCOMPLETE"
    assert not _rule_candidates(spi_peer_netlist(incomplete_reference_types=("U2",)))
    assert not _rule_candidates(
        spi_peer_netlist(
            reference_nets={"U1": "CHASSIS_A", "U2": "CHASSIS_B"},
            reference_functions={"U1": "SHIELD", "U2": "SHIELD"},
        )
    )


def test_known_split_remains_reviewable_when_another_peer_is_incomplete() -> None:
    source = spi_peer_netlist(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_C"},
        incomplete_reference_types=("U3",),
    )
    (finding,) = _rule_candidates(source)
    report = evaluate(
        "synthetic-spi-peer-reference",
        ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-spi-peer-reference",
            observed=source,
            netlist_sha256="e" * 64,
        ),
        DesignLintPolicy(),
    )

    assert finding.evidence["participants"] == ("U1", "U2", "U3")
    assert finding.evidence["incomplete_reference_evidence"] == ("U3",)
    assert report.spi_peer_reference_coverage is not None
    assert report.spi_peer_reference_coverage.entries[0].disposition == (
        "PARTIAL_SPLIT_REFERENCE_REVIEW"
    )


def test_only_directed_clock_peers_are_covered() -> None:
    all_inputs = spi_peer_netlist(clock_types={"U1": "input", "U2": "input"})
    all_outputs = spi_peer_netlist(clock_types={"U1": "output", "U2": "output"})

    assert scan_spi_peer_references(all_inputs).buses == ()
    assert scan_spi_peer_references(all_outputs).buses == ()


def test_repeated_component_return_review_suppresses_duplicate_prompt() -> None:
    source = spi_peer_netlist(symbols={"U1": "Synthetic:Peer", "U2": "Synthetic:Peer"})
    findings = candidates(source)

    assert not _rule_candidates(source)
    assert any(
        item.rule_id == "component.peer_power_pin_assignment_divergence" for item in findings
    )


def test_component_peer_review_must_cover_every_reference_pin_to_suppress() -> None:
    source = spi_peer_netlist(
        symbols={"U1": "Synthetic:RepeatedPeer", "U2": "Synthetic:RepeatedPeer"}
    )
    component_pin_numbers = {
        reference: (*numbers, "5") for reference, numbers in source.component_pin_numbers.items()
    }
    pin_functions = {
        **source.pin_functions,
        "U1.5": "GND",
        "U2.5": "GND",
    }
    pin_electrical_types = {
        **source.pin_electrical_types,
        "U1.5": "power_in",
        "U2.5": "power_in",
    }
    nets = {
        **source.nets,
        "GND_A": (*source.nets["GND_A"], "U1.5"),
        "GND_B": (*source.nets["GND_B"], "U2.5"),
    }
    source = source.model_copy(
        update={
            "component_pin_numbers": component_pin_numbers,
            "pin_functions": pin_functions,
            "pin_electrical_types": pin_electrical_types,
            "nets": nets,
        }
    )
    partial_component_review = Candidate(
        rule_id="component.peer_power_pin_assignment_divergence",
        subject="U1.3, U2.3",
        message="Synthetic partial component review",
        evidence={
            "peer_role": ("ground/return",),
            "U1.3": ("GND_A",),
            "U2.3": ("GND_B",),
        },
    )

    findings = spi_peer_reference_candidates(
        source, component_peer_findings=(partial_component_review,)
    )

    assert len(findings) == 1
    assert findings[0].rule_id == RULE_ID
    complete_component_review = Candidate(
        rule_id="component.peer_power_pin_assignment_divergence",
        subject="U1.3, U1.5, U2.3, U2.5",
        message="Synthetic complete component review",
        evidence={
            "peer_role": ("ground/return",),
            "U1.3": ("GND_A",),
            "U1.5": ("GND_A",),
            "U2.3": ("GND_B",),
            "U2.5": ("GND_B",),
        },
    )
    assert not spi_peer_reference_candidates(
        source, component_peer_findings=(complete_component_review,)
    )


def test_split_candidate_is_stable_under_mapping_order() -> None:
    source = spi_peer_netlist()
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
    (repeat,) = _rule_candidates(reordered)
    assert (repeat.subject, repeat.evidence) == (original.subject, original.evidence)


def test_report_coverage_tracks_candidate_and_policy_disposition() -> None:
    source = spi_peer_netlist()

    def report(policy: DesignLintPolicy | None = None):
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id="synthetic-spi-peer-reference",
            observed=source,
            netlist_sha256="d" * 64,
        )
        return evaluate(coach.project_id, coach, policy or DesignLintPolicy())

    baseline = report()
    assert baseline.spi_peer_reference_coverage is not None
    assert baseline.spi_peer_reference_coverage.netlist_sha256 == "d" * 64
    assert baseline.spi_peer_reference_coverage.candidate_group_count == 1
    assert baseline.spi_peer_reference_coverage.entries[0].disposition == ("SPLIT_REFERENCE_REVIEW")

    disabled = report(
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
    assert disabled_finding.disposition == "RULE_OFF"
    assert disabled.spi_peer_reference_coverage is not None
    assert disabled.spi_peer_reference_coverage.mode == "off"
    assert disabled.spi_peer_reference_coverage.candidate_group_count == 1

    baseline_finding = next(item for item in baseline.findings if item.rule_id == RULE_ID)
    ignored = report(
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
    assert ignored_finding.disposition == "IGNORED"
    assert ignored.spi_peer_reference_coverage is not None
    assert ignored.spi_peer_reference_coverage.candidate_group_count == 1
