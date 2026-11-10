"""Review separate connector peers that map distinct signals to one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintFinding
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.design_lint_fixtures.connector_reviewed_peer_signal_split import (
    peer_signal_coverage,
    peer_signal_netlist,
    peer_signal_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.reviewed_peer_distinct_signals_shared_net"


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


def _fault():
    observed = peer_signal_netlist(nets=("SHARED_SIGNAL", "SHARED_SIGNAL"))
    coverage = peer_signal_coverage(
        observed,
        signals=("UART_TX", "UART_RX"),
    )
    return observed, coverage


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_distinct_mapped_signals_on_separate_reviewed_peers_need_review() -> None:
    observed, coverage = _fault()
    report = peer_signal_report(observed, coverage=coverage)

    assert coverage.status == "COMPLETE"
    findings = _findings(report)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "serial-peers: distinct mapped peer signals UART_RX, UART_TX share native net "
        "SHARED_SIGNAL across separate connectors"
    )
    assert finding.evidence["component_reference"] == ("J1", "J2")
    assert finding.evidence["component_pin"] == ("J1.2", "J2.7")
    assert finding.evidence["interface_signal"] == ("UART_RX", "UART_TX")
    assert finding.evidence["assigned_nets"] == ("SHARED_SIGNAL",)
    assert "does not establish an electrical conflict" in finding.message
    assert not any(
        item.rule_id
        in {
            "connector.mapped_signals_share_net",
            "connector.reviewed_peer_signal_domain_shared_net",
        }
        for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_native_contacts_with_distinct_peer_signals_need_review() -> None:
    observed = peer_signal_netlist(
        nets=("SHARED_SIGNAL", "SHARED_SIGNAL"),
        functions=("CONTACT_A", "CONTACT_B"),
    )
    coverage = peer_signal_coverage(
        observed,
        signals=("UART_TX", "UART_RX"),
        voltage_domains=("logic-3v3", "logic-3v3"),
    )
    report = peer_signal_report(observed, coverage=coverage)

    assert coverage.status == "COMPLETE"
    findings = _findings(report)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.evidence["component_pin"] == ("J1.2", "J2.7")
    assert finding.evidence["interface_signal"] == ("UART_RX", "UART_TX")
    assert finding.evidence["native_pin_function"] == (
        "J1.2=CONTACT_A",
        "J2.7=CONTACT_B",
    )
    assert finding.evidence["assigned_nets"] == ("SHARED_SIGNAL",)
    assert "named native connector contacts" in finding.message
    assert not any(
        item.rule_id
        in {
            "connector.mapped_signals_share_net",
            "connector.reviewed_peer_signal_domain_shared_net",
        }
        for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_signal_distinct_nets_and_separate_peer_groups_stay_quiet() -> None:
    observed = peer_signal_netlist(nets=("NET_A", "NET_A"))
    reports = (
        peer_signal_report(observed),
        peer_signal_report(
            peer_signal_netlist(nets=("NET_A", "NET_B")),
            coverage=peer_signal_coverage(
                peer_signal_netlist(nets=("NET_A", "NET_B")),
                signals=("UART_TX", "UART_RX"),
            ),
        ),
        peer_signal_report(
            observed,
            coverage=peer_signal_coverage(
                observed,
                signals=("UART_TX", "UART_RX"),
                peer_groups=("usb-ports", "serial-ports"),
            ),
        ),
        peer_signal_report(
            peer_signal_netlist(
                nets=("SHARED_SIGNAL", "SHARED_SIGNAL"),
                functions=("CONTACT_A", "CONTACT_B"),
            ),
        ),
        peer_signal_report(
            peer_signal_netlist(
                nets=("NET_A", "NET_B"),
                functions=("CONTACT_A", "CONTACT_B"),
            ),
            coverage=peer_signal_coverage(
                peer_signal_netlist(
                    nets=("NET_A", "NET_B"),
                    functions=("CONTACT_A", "CONTACT_B"),
                ),
                signals=("UART_TX", "UART_RX"),
                voltage_domains=("logic-3v3", "logic-3v3"),
            ),
        ),
    )
    assert all(not _findings(report) for report in reports)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_return_shield_dnp_and_non_signal_contacts_are_controls() -> None:
    observed, _ = _fault()
    named_dnp = peer_signal_netlist(
        nets=("SHARED_SIGNAL", "SHARED_SIGNAL"),
        functions=("TX", "RX"),
        dnp=("J2",),
    )
    dnp = peer_signal_netlist(nets=("SHARED_SIGNAL", "SHARED_SIGNAL"), dnp=("J2",))
    named_supply = peer_signal_netlist(
        nets=("SHARED_SIGNAL", "SHARED_SIGNAL"),
        functions=("VBUS", "RX"),
    )
    named_return = peer_signal_netlist(
        nets=("SHARED_SIGNAL", "SHARED_SIGNAL"),
        functions=("GND", "RX"),
    )
    named_shield = peer_signal_netlist(
        nets=("SHARED_SIGNAL", "SHARED_SIGNAL"),
        functions=("SHIELD", "RX"),
    )
    reports = (
        peer_signal_report(
            named_dnp,
            coverage=peer_signal_coverage(
                named_dnp,
                signals=("UART_TX", "UART_RX"),
                voltage_domains=("logic-3v3", "logic-3v3"),
            ),
        ),
        peer_signal_report(
            named_supply,
            coverage=peer_signal_coverage(
                named_supply,
                signals=("UART_TX", "UART_RX"),
                voltage_domains=("logic-3v3", "logic-3v3"),
            ),
        ),
        peer_signal_report(
            named_return,
            coverage=peer_signal_coverage(
                named_return,
                signals=("UART_TX", "UART_RX"),
                voltage_domains=("logic-3v3", "logic-3v3"),
            ),
        ),
        peer_signal_report(
            named_shield,
            coverage=peer_signal_coverage(
                named_shield,
                signals=("UART_TX", "UART_RX"),
                voltage_domains=("logic-3v3", "logic-3v3"),
            ),
        ),
        peer_signal_report(
            dnp,
            coverage=peer_signal_coverage(dnp, signals=("UART_TX", "UART_RX")),
        ),
        peer_signal_report(
            observed,
            coverage=peer_signal_coverage(
                observed,
                signals=("UART_TX", "UART_RX"),
                roles=("return", "signal"),
            ),
        ),
    )
    assert all(not _findings(report) for report in reports)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_stale_and_digestless_maps_are_controls() -> None:
    observed, current = _fault()
    incomplete = current.model_copy(update={"status": "INCOMPLETE"})
    digestless = current.model_copy(update={"interface_catalog_sha256": None})
    stale_source = peer_signal_netlist(
        nets=("SHARED_SIGNAL", "SHARED_SIGNAL"),
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
    observed, coverage = _fault()
    baseline = _findings(peer_signal_report(observed, coverage=coverage))[0]
    blocked = peer_signal_report(
        observed,
        coverage=coverage,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic distinct peer signals need explicit review.",
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
                    reason="Synthetic cross-connector sharing is intentional.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_stable_under_net_and_mapping_order() -> None:
    named = peer_signal_netlist(
        nets=("SHARED_SIGNAL", "SHARED_SIGNAL"),
        functions=("CONTACT_A", "CONTACT_B"),
    )
    cases = (
        _fault(),
        (
            named,
            peer_signal_coverage(
                named,
                signals=("UART_TX", "UART_RX"),
                voltage_domains=("logic-3v3", "logic-3v3"),
            ),
        ),
    )

    for observed, coverage in cases:
        reordered = observed.model_copy(
            update={
                "nets": {
                    name: tuple(reversed(pins))
                    for name, pins in reversed(tuple(observed.nets.items()))
                },
                "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            }
        )
        reordered_coverage = coverage.model_copy(
            update={"entries": tuple(reversed(coverage.entries))}
        )

        first = _findings(peer_signal_report(observed, coverage=coverage))[0]
        second = _findings(peer_signal_report(reordered, coverage=coverage))[0]
        third = _findings(peer_signal_report(observed, coverage=reordered_coverage))[0]
        assert first == second == third
