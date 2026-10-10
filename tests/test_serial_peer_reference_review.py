"""Synthetic UART return-path review candidate regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import text_report
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride
from kicad_tooling.hwrepo.serial_peer_reference_review import (
    unmapped_serial_peer_reference_reviews,
)
from tests.serial_peer_reference_support import (
    RULE_ID,
    labelled_serial_reference_netlist,
    multi_uart_connector_reference_netlist,
    report,
    serial_connector_reference_netlist,
    serial_reference_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


class SerialPeerReferenceReviewTests:
    def test_distinct_explicit_return_nets_prompt_with_exact_signal_and_pin_evidence(self) -> None:
        source = serial_reference_netlist()
        candidates = unmapped_serial_peer_reference_reviews(source)
        assert (len(candidates)) == (1)
        assert (len(candidates[0].links)) == (2)
        assert (candidates[0].first_reference_domain.net) == ("GND_A")
        assert (candidates[0].second_reference_domain.net) == ("GND_B")

        lint = report(source)
        findings = [item for item in lint.findings if item.rule_id == RULE_ID]
        assert (len(findings)) == (1)
        assert (lint.status) == ("REVIEW")
        assert (findings[0].mode) == ("review")
        assert (findings[0].subject) == ("U1 / U2: serial reference-domain review")
        assert (findings[0].evidence["shared_serial_pin_assignments"]) == (
            (
                "UART_A: U1.1 (UART1_TX, output) -> U2.1 (UART1_RX, input)",
                "UART_B: U2.2 (UART1_TX, output) -> U1.2 (UART1_RX, input)",
            )
        )
        assert (findings[0].evidence["first_reference_pin_assignments"]) == (
            ("U1.9 (GND, power_in)=GND_A",)
        )
        assert (findings[0].evidence["second_reference_pin_assignments"]) == (
            ("U2.9 (GND, power_in)=GND_B",)
        )

    def test_same_reference_net_is_a_quiet_control(self) -> None:
        source = serial_reference_netlist(
            output_reference_net="SIGNAL_RETURN", input_reference_net="SIGNAL_RETURN"
        )
        assert (unmapped_serial_peer_reference_reviews(source)) == (())
        assert not (any(item.rule_id == RULE_ID for item in report(source).findings))

    def test_direct_mcu_to_serial_header_peer_reviews_split_reference_nets(self) -> None:
        source = serial_connector_reference_netlist()
        candidates = unmapped_serial_peer_reference_reviews(source)
        assert (len(candidates)) == (1)
        candidate = candidates[0]
        assert ({candidate.first_reference, candidate.second_reference}) == ({"U1", "J1"})
        assert ({candidate.first_reference_domain.net, candidate.second_reference_domain.net}) == (
            {"GND_A", "GND_B"}
        )
        assert (len(candidate.links)) == (2)

        findings = [item for item in report(source).findings if item.rule_id == RULE_ID]
        assert (len(findings)) == (1)
        assert (findings[0].subject) == ("J1 / U1: serial reference-domain review")
        assert (findings[0].evidence["shared_serial_pin_assignments"]) == (
            (
                "UART_RX: J1.2 (UART1_TX, output) -> U1.2 (UART1_RX, input)",
                "UART_TX: U1.1 (UART1_TX, output) -> J1.1 (UART1_RX, input)",
            )
        )

        baseline = report(
            source,
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="off",
                        reason="Synthetic incremental-value comparison",
                    ),
                )
            ),
        )
        other_findings = tuple(item for item in baseline.findings if item.rule_id != RULE_ID)
        assert ({item.rule_id for item in other_findings}) == (
            {"bus.serial_unmapped_peer", "power.ic_rail_without_fitted_capacitor"}
        )
        assert not (
            any(net in str(item.evidence) for item in other_findings for net in ("GND_A", "GND_B"))
        )

        common = serial_connector_reference_netlist(
            output_reference_net="GND", input_reference_net="GND"
        )
        assert (unmapped_serial_peer_reference_reviews(common)) == (())

    def test_multi_uart_headers_localize_one_split_reference(self) -> None:
        source = multi_uart_connector_reference_netlist()
        candidates = unmapped_serial_peer_reference_reviews(source)
        assert (len(candidates)) == (1)
        candidate = candidates[0]
        assert ({candidate.first_reference, candidate.second_reference}) == ({"U1", "J1"})
        assert ({link.net for link in candidate.links}) == ({"UART_RX", "UART_TX"})
        assert ("J2") not in ({candidate.first_reference, candidate.second_reference})

        findings = [item for item in report(source).findings if item.rule_id == RULE_ID]
        assert (len(findings)) == (1)
        reference_assignments = (
            *findings[0].evidence["first_reference_pin_assignments"],
            *findings[0].evidence["second_reference_pin_assignments"],
        )
        assert ("J1.4 (GND, passive)=GND_B") in (reference_assignments)

    def test_multi_uart_headers_with_common_references_are_a_quiet_control(self) -> None:
        common = multi_uart_connector_reference_netlist(common_first_return=True)
        assert (unmapped_serial_peer_reference_reviews(common)) == (())
        assert not (any(item.rule_id == RULE_ID for item in report(common).findings))

    def test_multi_uart_peer_reference_review_is_order_stable(self) -> None:
        source = multi_uart_connector_reference_netlist()
        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        assert (unmapped_serial_peer_reference_reviews(source)) == (
            unmapped_serial_peer_reference_reviews(reordered)
        )
        assert (report(source).findings) == (report(reordered).findings)

    def test_channel_labelled_generic_ic_pair_reviews_split_reference_domains(self) -> None:
        source = labelled_serial_reference_netlist()
        candidates = unmapped_serial_peer_reference_reviews(source)
        assert (len(candidates)) == (1)
        candidate = candidates[0]
        assert ({candidate.first_reference, candidate.second_reference}) == ({"U1", "U2"})
        assert (candidate.links) == (())
        assert (len(candidate.label_links)) == (1)
        link = candidate.label_links[0]
        assert (link.channel) == ("uart0")
        assert (link.tx_net) == ("Compute module/UART.0.TX")
        assert (link.rx_net) == ("Compute module/UART.0.RX")
        assert ({candidate.first_reference_domain.net, candidate.second_reference_domain.net}) == (
            {"GND_A", "GND_B"}
        )

        lint_report = report(source)
        findings = [item for item in lint_report.findings if item.rule_id == RULE_ID]
        assert (len(findings)) == (1)
        assert (findings[0].mode) == ("review")
        assert ("Exact UART/USART TX and RX channel labels") in (findings[0].message)
        coverage = lint_report.serial_peer_reference_coverage
        assert (coverage) is not None
        assert coverage is not None
        assert (
            (
                coverage.native_peer_link_count,
                coverage.label_peer_link_count,
                coverage.separate_reference_link_count,
                coverage.candidate_group_count,
            )
        ) == ((0, 1, 1, 1))
        assert (findings[0].evidence["serial_label_link_assignments"]) == (
            (
                "uart0: TX Compute module/UART.0.TX (U1.1, U2.2); "
                + "RX Compute module/UART.0.RX (U1.2, U2.1)",
            )
        )
        assert (findings[0].evidence["discovery_basis"]) == (("net_label",))
        assert (
            tuple(
                (
                    item.discovery_basis,
                    item.first_reference,
                    item.second_reference,
                    item.signal_group,
                    item.signal_nets,
                    item.signal_pins,
                    item.disposition,
                )
                for item in coverage.link_entries or ()
            )
        ) == (
            (
                (
                    "channel_label",
                    "U1",
                    "U2",
                    "uart0",
                    ("Compute module/UART.0.TX", "Compute module/UART.0.RX"),
                    ("U1.1", "U2.2", "U1.2", "U2.1"),
                    "SEPARATE_REFERENCE_REVIEW",
                ),
            )
        )
        assert (
            "channel-label: U1 / U2 (uart0; nets Compute module/UART.0.TX, "
            "Compute module/UART.0.RX; pins U1.1, U2.2, U1.2, U2.1): "
            "SEPARATE_REFERENCE_REVIEW"
        ) in (text_report(lint_report))

    def test_channel_labelled_generic_ic_pair_with_common_reference_is_quiet(self) -> None:
        source = labelled_serial_reference_netlist(
            first_reference_net="GND", second_reference_net="GND"
        )
        assert (unmapped_serial_peer_reference_reviews(source)) == (())
        assert not (any(item.rule_id == RULE_ID for item in report(source).findings))
