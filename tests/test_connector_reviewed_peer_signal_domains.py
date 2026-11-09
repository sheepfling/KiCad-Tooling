"""Review shared peer signals whose source maps declare different domains."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.design_lint_fixtures.connector_reviewed_peer_signal_split import (
    peer_signal_coverage,
    peer_signal_netlist,
    peer_signal_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.reviewed_peer_signal_domain_shared_net"


def _findings(report: object) -> tuple[object, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_signal_on_shared_net_across_distinct_voltage_domains_needs_review() -> None:
    observed = peer_signal_netlist(nets=("SHARED_RX", "SHARED_RX"))
    coverage = peer_signal_coverage(
        observed,
        voltage_domains=("logic-3v3", "logic-5v"),
    )
    report = peer_signal_report(observed, coverage=coverage)

    assert coverage.status == "COMPLETE"
    findings = _findings(report)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "serial-peers: mapped peer signal UART_RX in voltage domains "
        "logic-3v3, logic-5v shares native net SHARED_RX"
    )
    assert finding.evidence["component_reference"] == ("J1", "J2")
    assert finding.evidence["component_pin"] == ("J1.2", "J2.7")
    assert finding.evidence["interface_signal"] == ("UART_RX",)
    assert finding.evidence["voltage_domain"] == ("logic-3v3", "logic-5v")
    assert finding.evidence["assigned_nets"] == ("SHARED_RX",)
    assert "do not establish nominal voltages" in finding.message
    assert not any(
        item.rule_id == "connector.reviewed_peer_signal_assignment_split"
        for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_domain_and_nonmatching_signal_group_or_net_stay_quiet() -> None:
    observed = peer_signal_netlist(nets=("SHARED_RX", "SHARED_RX"))
    reports = (
        peer_signal_report(observed),
        peer_signal_report(
            observed,
            coverage=peer_signal_coverage(
                observed,
                voltage_domains=("logic-3v3", "logic-5v"),
                signals=("UART_RX", "UART_TX"),
            ),
        ),
        peer_signal_report(
            observed,
            coverage=peer_signal_coverage(
                observed,
                voltage_domains=("logic-3v3", "logic-5v"),
                peer_groups=("usb-port", "serial-port"),
            ),
        ),
        peer_signal_report(
            peer_signal_netlist(
                nets=("NET_A", "NET_B"),
            ),
            coverage=peer_signal_coverage(
                peer_signal_netlist(nets=("NET_A", "NET_B")),
                voltage_domains=("logic-3v3", "logic-5v"),
            ),
        ),
        peer_signal_report(
            peer_signal_netlist(nets=("SHARED_RX", "shared_rx")),
            coverage=peer_signal_coverage(
                peer_signal_netlist(nets=("SHARED_RX", "shared_rx")),
                voltage_domains=("logic-3v3", "logic-5v"),
            ),
        ),
    )
    assert all(not _findings(report) for report in reports)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_dnp_and_non_signal_contacts_are_controls() -> None:
    observed = peer_signal_netlist(nets=("SHARED_RX", "SHARED_RX"))
    distinct_domains = peer_signal_coverage(
        observed,
        voltage_domains=("logic-3v3", "logic-5v"),
    )
    reports = (
        peer_signal_report(
            peer_signal_netlist(nets=("SHARED_RX", "SHARED_RX"), functions=("RX", "RX")),
            coverage=distinct_domains,
        ),
        peer_signal_report(
            peer_signal_netlist(nets=("SHARED_RX", "SHARED_RX"), dnp=("J2",)),
            coverage=distinct_domains,
        ),
        peer_signal_report(
            observed,
            coverage=peer_signal_coverage(
                observed,
                voltage_domains=("logic-3v3", "logic-5v"),
                roles=("return", "return"),
            ),
        ),
    )
    assert all(not _findings(report) for report in reports)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_stale_and_digestless_maps_are_controls() -> None:
    observed = peer_signal_netlist(nets=("SHARED_RX", "SHARED_RX"))
    current = peer_signal_coverage(
        observed,
        voltage_domains=("logic-3v3", "logic-5v"),
    )
    incomplete = current.model_copy(update={"status": "INCOMPLETE"})
    digestless = current.model_copy(update={"interface_catalog_sha256": None})
    stale_source = peer_signal_netlist(
        nets=("SHARED_RX", "SHARED_RX"),
        functions=("Pin_2", "Pin_7"),
    )

    reports = (
        peer_signal_report(observed, coverage=incomplete),
        peer_signal_report(observed, coverage=digestless),
        peer_signal_report(stale_source, coverage=current),
    )
    assert all(not _findings(report) for report in reports)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_review() -> None:
    observed = peer_signal_netlist(nets=("SHARED_RX", "SHARED_RX"))
    coverage = peer_signal_coverage(
        observed,
        voltage_domains=("logic-3v3", "logic-5v"),
    )
    baseline = _findings(peer_signal_report(observed, coverage=coverage))[0]
    blocked = peer_signal_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic shared signal domains require explicit approval.",
                ),
            )
        ),
    )
    disabled = peer_signal_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project disables this review cue.",
                ),
            )
        ),
    )
    ignored = peer_signal_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic domain sharing is intentional.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_stable_under_native_net_and_mapping_order() -> None:
    observed = peer_signal_netlist(nets=("SHARED_RX", "SHARED_RX"))
    coverage = peer_signal_coverage(
        observed,
        voltage_domains=("logic-3v3", "logic-5v"),
    )
    reordered = observed.model_copy(
        update={
            "nets": {
                name: tuple(reversed(pins)) for name, pins in reversed(tuple(observed.nets.items()))
            }
        }
    )
    reordered_coverage = coverage.model_copy(update={"entries": tuple(reversed(coverage.entries))})

    first = _findings(peer_signal_report(observed, coverage=coverage))[0]
    second = _findings(peer_signal_report(reordered, coverage=coverage))[0]
    third = _findings(peer_signal_report(observed, coverage=reordered_coverage))[0]
    assert first == second == third
