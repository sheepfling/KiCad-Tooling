"""Current reviewed peer assignments as evidence for open mapped signals."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.connector_reviewed_peer_signal_split import (
    peer_signal_coverage,
    peer_signal_netlist,
    peer_signal_report,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.mapped_interface_signal_unassigned"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_mapped_signal_reports_current_peer_assignment_context() -> None:
    observed = peer_signal_netlist(open_pins=("J2.7",))
    coverage = peer_signal_coverage(observed)
    report = peer_signal_report(observed, coverage=coverage)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert coverage.status == "COMPLETE"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == "J2.7: reviewed signal contact has no net assignment"
    assert finding.evidence["peer_assignment_group"] == ("serial-peers",)
    assert finding.evidence["peer_component_reference"] == ("J1",)
    assert finding.evidence["peer_component_pin"] == ("J1.2",)
    assert finding.evidence["peer_interface_signal"] == ("UART_RX",)
    assert finding.evidence["peer_interface_voltage_domain"] == ("logic-3v3",)
    assert finding.evidence["peer_assigned_nets"] == ("USB_RX_NET",)
    assert "does not require commoning" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_peer_context_requires_matching_current_signal_domain_and_group() -> None:
    observed = peer_signal_netlist(open_pins=("J2.7",))
    alternate_maps = (
        peer_signal_coverage(observed, signals=("UART_TX", "UART_RX")),
        peer_signal_coverage(observed, voltage_domains=("logic-3v3", "logic-5v")),
        peer_signal_coverage(observed, peer_groups=("usb-peers", "serial-peers")),
        peer_signal_coverage(
            observed.model_copy(
                update={"nets": {"USB_RX_NET": ("J1.2",), "AMBIGUOUS_NET": ("J1.2",)}}
            )
        ),
    )

    for coverage in alternate_maps:
        report = peer_signal_report(observed, coverage=coverage)
        findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
        assert len(findings) == 1
        assert "peer_assignment_group" not in findings[0].evidence


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_peer_context_evidence_is_stable_under_native_input_order() -> None:
    observed = peer_signal_netlist(open_pins=("J2.7",))
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )
    first_coverage = peer_signal_coverage(observed)
    second_coverage = peer_signal_coverage(reordered)
    first_report = peer_signal_report(observed, coverage=first_coverage)
    second_report = peer_signal_report(reordered, coverage=second_coverage)
    first = next(item for item in first_report.findings if item.rule_id == RULE_ID)
    second = next(item for item in second_report.findings if item.rule_id == RULE_ID)

    assert first_coverage.status == second_coverage.status == "COMPLETE"
    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_current_peers_keep_each_pin_paired_with_its_native_net() -> None:
    references = ("J1", "J2", "J3")
    pins = ("J1.2", "J2.7", "J3.8")
    observed = peer_signal_netlist(
        nets=("USB_RX_NET", "SERIAL_RX_NET", "UNUSED"),
        symbols=("Synthetic:UsbPort", "Synthetic:SerialPort", "Synthetic:SerialPort"),
        functions=("2", "7", "8"),
        open_pins=("J3.8",),
        references=references,
        pins=pins,
    )
    coverage = peer_signal_coverage(observed, references=references, pins=pins)
    report = peer_signal_report(observed, coverage=coverage)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert coverage.status == "COMPLETE"
    assert finding.evidence["component_pin"] == ("J3.8",)
    assert finding.evidence["peer_component_reference"] == ("J1", "J2")
    assert finding.evidence["peer_component_pin"] == ("J1.2", "J2.7")
    assert finding.evidence["peer_assigned_nets"] == ("USB_RX_NET", "SERIAL_RX_NET")
    assert "does not require commoning" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_or_dnp_peers_do_not_supply_assignment_context() -> None:
    all_open = peer_signal_netlist(open_pins=("J1.2", "J2.7"))
    dnp_peer = peer_signal_netlist(dnp=("J1",), open_pins=("J2.7",))

    for observed in (all_open, dnp_peer):
        coverage = peer_signal_coverage(observed)
        report = peer_signal_report(observed, coverage=coverage)
        findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
        target = tuple(item for item in findings if item.evidence["component_pin"] == ("J2.7",))
        assert len(target) == 1
        assert "peer_assignment_group" not in target[0].evidence


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_documented_intentional_open_removes_target_finding() -> None:
    observed = peer_signal_netlist(open_pins=("J2.7",))
    coverage = peer_signal_coverage(
        observed,
        unconnected_reasons=(None, "Reviewed as an intentionally unused signal contact"),
    )

    report = peer_signal_report(observed, coverage=coverage)

    assert coverage.status == "COMPLETE"
    assert not tuple(item for item in report.findings if item.rule_id == RULE_ID)
