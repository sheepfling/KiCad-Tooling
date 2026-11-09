"""Review generic mapped signals split across reviewed connector peers."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.design_lint_fixtures.connector_reviewed_peer_signal_split import (
    peer_signal_coverage,
    peer_signal_netlist,
    peer_signal_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.reviewed_peer_signal_assignment_split"


def _findings(report: object) -> tuple[object, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_split_generic_signal_across_unlike_reviewed_peers_needs_review() -> None:
    observed = peer_signal_netlist()
    coverage = peer_signal_coverage(observed)
    report = peer_signal_report(observed, coverage=coverage)

    assert coverage.status == "COMPLETE"
    findings = _findings(report)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "serial-peers: mapped peer signal UART_RX (logic-3v3) "
        "spans native nets SERIAL_RX_NET, USB_RX_NET"
    )
    assert finding.evidence["component_reference"] == ("J1", "J2")
    assert finding.evidence["component_pin"] == ("J1.2", "J2.7")
    assert finding.evidence["interface_signal"] == ("UART_RX",)
    assert finding.evidence["voltage_domain"] == ("logic-3v3",)
    assert finding.evidence["peer_assignment_group"] == ("serial-peers",)
    assert "does not require direct commoning" in finding.message
    assert not any(
        item.rule_id == "connector.mapped_signals_split_nets" for item in report.findings
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_net_and_unlike_signal_domain_or_group_controls_stay_quiet() -> None:
    common = peer_signal_netlist(nets=("COMMON_RX", "COMMON_RX"))
    distinct_signal = peer_signal_coverage(peer_signal_netlist(), signals=("USB_RX", "SERIAL_RX"))
    distinct_domain = peer_signal_coverage(
        peer_signal_netlist(), voltage_domains=("logic-3v3", "logic-5v")
    )
    distinct_group = peer_signal_coverage(
        peer_signal_netlist(), peer_groups=("usb-port", "serial-port")
    )
    same_symbol = peer_signal_netlist(symbols=("Synthetic:Port", "Synthetic:Port"))

    reports = (
        peer_signal_report(common),
        peer_signal_report(peer_signal_netlist(), coverage=distinct_signal),
        peer_signal_report(peer_signal_netlist(), coverage=distinct_domain),
        peer_signal_report(peer_signal_netlist(), coverage=distinct_group),
        peer_signal_report(same_symbol),
    )
    assert all(not _findings(report) for report in reports)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_dnp_and_non_signal_contacts_are_controls() -> None:
    observed = peer_signal_netlist()
    named = peer_signal_netlist(functions=("RX", "RX"))
    dnp = peer_signal_netlist(dnp=("J2",))
    non_signal = peer_signal_coverage(observed, roles=("return", "return"))

    reports = (
        peer_signal_report(named),
        peer_signal_report(dnp),
        peer_signal_report(observed, coverage=non_signal),
    )
    assert all(not _findings(report) for report in reports)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_stale_and_digestless_maps_are_controls() -> None:
    observed = peer_signal_netlist()
    current = peer_signal_coverage(observed)
    incomplete = current.model_copy(update={"status": "INCOMPLETE"})
    digestless = current.model_copy(update={"interface_catalog_sha256": None})
    stale_source = peer_signal_netlist(functions=("Pin_2", "Pin_7"))

    reports = (
        peer_signal_report(observed, coverage=incomplete),
        peer_signal_report(observed, coverage=digestless),
        peer_signal_report(stale_source, coverage=current),
    )
    assert all(not _findings(report) for report in reports)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_review() -> None:
    observed = peer_signal_netlist()
    baseline = _findings(peer_signal_report(observed))[0]
    blocked = peer_signal_report(
        observed,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic reviewed connector signals must stay on one net.",
                ),
            )
        ),
    )
    disabled = peer_signal_report(
        observed,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project disables this heuristic.",
                ),
            )
        ),
    )
    ignored = peer_signal_report(
        observed,
        policy=DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=baseline.fingerprint,
                    reason="Synthetic split signal path is intentional.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(item.disposition == "RULE_OFF" for item in _findings(disabled))
    assert any(item.disposition == "IGNORED" for item in _findings(ignored))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_stable_under_native_net_and_mapping_order() -> None:
    observed = peer_signal_netlist()
    reordered = observed.model_copy(
        update={
            "nets": {
                name: tuple(reversed(pins)) for name, pins in reversed(tuple(observed.nets.items()))
            }
        }
    )
    renamed = peer_signal_netlist(nets=("NEUTRAL_A", "NEUTRAL_B"))
    map_reordered = peer_signal_coverage(observed)
    map_reordered = map_reordered.model_copy(
        update={"entries": tuple(reversed(map_reordered.entries))}
    )

    first = _findings(peer_signal_report(observed))[0]
    second = _findings(peer_signal_report(reordered))[0]
    reordered_map = _findings(peer_signal_report(observed, coverage=map_reordered))[0]
    neutral = _findings(peer_signal_report(renamed))[0]

    assert first == second == reordered_map
    assert first.evidence["component_pin"] == neutral.evidence["component_pin"]
    assert first.evidence["assigned_nets"] != neutral.evidence["assigned_nets"]
