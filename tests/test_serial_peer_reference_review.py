"""Synthetic UART reference-domain review candidates and decision lifecycle."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from kicad_tooling.hwrepo.design_lint import evaluate, text_report
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    NetlistContract,
    ReferenceBondRequirement,
    SerialDirectPeerRequirement,
    SerialEndpointRequirement,
    SerialPeerAnalysis,
    SerialPeerLinkRequirement,
    SerialPeerReferenceCoverageReport,
    SerialPinNetRequirement,
)
from kicad_tooling.hwrepo.serial_participants import SerialPeerRosterContext
from kicad_tooling.hwrepo.serial_peer_reference_review import (
    unmapped_serial_peer_reference_reviews,
)

RULE_ID = "bus.serial_peer_reference_review"


def serial_reference_netlist(
    *,
    output_reference_net: str = "GND_A",
    input_reference_net: str = "GND_B",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    reference_nets: dict[str, list[str]] = {output_reference_net: ["U1.9"]}
    reference_nets.setdefault(input_reference_net, []).append("U2.9")
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART transmitter", footprint="Package:UART-TX"
            ),
            "U2": ComponentContract(value="Synthetic UART receiver", footprint="Package:UART-RX"),
        },
        nets={
            "UART_A": ("U1.1", "U2.1"),
            "UART_B": ("U1.2", "U2.2"),
            "+3V3": ("U1.8", "U2.8"),
            **{net: tuple(pins) for net, pins in reference_nets.items()},
        },
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
        },
        pin_functions={
            "U1.1": "UART1_TX",
            "U1.2": "UART1_RX",
            "U1.8": "VDD",
            "U1.9": "GND",
            "U2.1": "UART1_RX",
            "U2.2": "UART1_TX",
            "U2.8": "VDD",
            "U2.9": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "input",
            "U1.8": "power_in",
            "U1.9": "power_in",
            "U2.1": "input",
            "U2.2": "output",
            "U2.8": "power_in",
            "U2.9": "power_in",
        },
        component_pin_numbers={
            "U1": ("1", "2", "8", "9"),
            "U2": ("1", "2", "8", "9"),
        },
    )


def labelled_serial_reference_netlist(
    *,
    first_reference_net: str = "GND_A",
    second_reference_net: str = "GND_B",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Use exact UART channel labels with generic signal pin functions."""
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic translator", footprint="Package:UART-TX"),
            "U2": ComponentContract(value="Synthetic serial bridge", footprint="Package:UART-RX"),
        },
        nets={
            "Compute module/UART.0.TX": ("U1.1", "U2.2"),
            "Compute module/UART.0.RX": ("U1.2", "U2.1"),
            "+3V3": ("U1.8", "U2.8"),
            first_reference_net: ("U1.9",),
            second_reference_net: ("U2.9",),
        },
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
        },
        pin_functions={
            "U1.1": "B2",
            "U1.2": "B1",
            "U1.8": "VDD",
            "U1.9": "GND",
            "U2.1": "ADBUS0",
            "U2.2": "ADBUS1",
            "U2.8": "VDD",
            "U2.9": "GND",
        },
        pin_electrical_types={
            "U1.1": "tri_state",
            "U1.2": "tri_state",
            "U1.8": "power_in",
            "U1.9": "power_in",
            "U2.1": "bidirectional",
            "U2.2": "bidirectional",
            "U2.8": "power_in",
            "U2.9": "power_in",
        },
        component_pin_numbers={
            "U1": ("1", "2", "8", "9"),
            "U2": ("1", "2", "8", "9"),
        },
    )


def serial_peer_map(
    *,
    reference_policy: str,
    output_reference_net: str,
    input_reference_net: str,
    output_reference_pin: str = "U1.9",
    input_reference_pin: str = "U2.9",
    reference_bond: ReferenceBondRequirement | None = None,
) -> SerialPeerAnalysis:
    left = SerialEndpointRequirement(
        id="controller",
        reference="U1",
        symbol="Synthetic:UartTransmitter",
        footprint="Package:UART-TX",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U1.1", net="UART_A"),
        rx=SerialPinNetRequirement(pin="U1.2", net="UART_B"),
        reference_pins=(
            SerialPinNetRequirement(pin=output_reference_pin, net=output_reference_net),
        ),
    )
    right = SerialEndpointRequirement(
        id="peripheral",
        reference="U2",
        symbol="Synthetic:UartReceiver",
        footprint="Package:UART-RX",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U2.2", net="UART_B"),
        rx=SerialPinNetRequirement(pin="U2.1", net="UART_A"),
        reference_pins=(SerialPinNetRequirement(pin=input_reference_pin, net=input_reference_net),),
    )
    return SerialPeerAnalysis(
        basis="Synthetic reviewed direct serial peer and reference policy",
        links=(
            SerialPeerLinkRequirement(
                id="controller-peripheral",
                basis="Synthetic direct UART TX/RX link",
                endpoint=left,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=right),
                reference_policy=reference_policy,
                reference_bond=reference_bond,
            ),
        ),
    )


def bonded_serial_reference_netlist(*, fault: bool = False) -> NetlistContract:
    source = serial_reference_netlist()
    floating_net = "FLOATING_GND" if fault else "GND_B"
    return source.model_copy(
        update={
            "components": {
                **source.components,
                "R3": ComponentContract(value="0R", footprint="Synthetic:0603"),
            },
            "nets": {
                **source.nets,
                "GND_A": ("U1.9", "R3.1"),
                "GND_B": ("U2.9",) if fault else ("U2.9", "R3.2"),
                **({floating_net: ("R3.2",)} if fault else {}),
            },
            "component_symbols": {**source.component_symbols, "R3": "Device:R"},
            "component_pin_numbers": {
                **source.component_pin_numbers,
                "R3": ("1", "2"),
            },
            "pin_functions": {
                **source.pin_functions,
                "R3.1": "~",
                "R3.2": "~",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "R3.1": "passive",
                "R3.2": "passive",
            },
        }
    )


def bonded_label_serial_reference_netlist(*, fault: bool = False) -> NetlistContract:
    source = bonded_serial_reference_netlist(fault=fault)
    nets = {name: pins for name, pins in source.nets.items() if name not in {"UART_A", "UART_B"}}
    nets.update(
        {
            "Compute module/UART.0.TX": ("U1.1", "U2.2"),
            "Compute module/UART.0.RX": ("U1.2", "U2.1"),
        }
    )
    return source.model_copy(
        update={
            "nets": nets,
            "pin_functions": {
                **source.pin_functions,
                "U1.1": "B2",
                "U1.2": "B1",
                "U2.1": "ADBUS0",
                "U2.2": "ADBUS1",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.1": "tri_state",
                "U1.2": "tri_state",
                "U2.1": "bidirectional",
                "U2.2": "bidirectional",
            },
        }
    )


def labelled_serial_peer_map(
    *,
    reference_policy: str,
    first_reference_net: str,
    second_reference_net: str,
    reference_bond: ReferenceBondRequirement | None = None,
) -> SerialPeerAnalysis:
    left = SerialEndpointRequirement(
        id="translator-side",
        reference="U1",
        symbol="Synthetic:UartTransmitter",
        footprint="Package:UART-TX",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U1.1", net="Compute module/UART.0.TX"),
        rx=SerialPinNetRequirement(pin="U1.2", net="Compute module/UART.0.RX"),
        reference_pins=(SerialPinNetRequirement(pin="U1.9", net=first_reference_net),),
    )
    right = SerialEndpointRequirement(
        id="bridge-side",
        reference="U2",
        symbol="Synthetic:UartReceiver",
        footprint="Package:UART-RX",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U2.1", net="Compute module/UART.0.RX"),
        rx=SerialPinNetRequirement(pin="U2.2", net="Compute module/UART.0.TX"),
        reference_pins=(SerialPinNetRequirement(pin="U2.9", net=second_reference_net),),
    )
    return SerialPeerAnalysis(
        basis="Synthetic reviewed label-identified serial segment and reference policy",
        links=(
            SerialPeerLinkRequirement(
                id="translator-bridge",
                basis="Synthetic direct TX/RX net-label pair",
                endpoint=left,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=right),
                reference_policy=reference_policy,
                reference_bond=reference_bond,
            ),
        ),
    )


def serial_connector_reference_netlist(
    *, output_reference_net: str = "GND_A", input_reference_net: str = "GND_B"
) -> NetlistContract:
    references: dict[str, list[str]] = {output_reference_net: ["U1.4"]}
    references.setdefault(input_reference_net, []).append("J1.4")
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART controller", footprint="Package:UART-CONTROLLER"
            ),
            "J1": ComponentContract(value="Synthetic UART header", footprint="Package:UART-HEADER"),
        },
        nets={
            "UART_TX": ("J1.1", "U1.1"),
            "UART_RX": ("J1.2", "U1.2"),
            "+3V3": ("J1.3", "U1.3"),
            **{net: tuple(sorted(pins)) for net, pins in references.items()},
        },
        component_symbols={
            "U1": "Synthetic:UartController",
            "J1": "Synthetic:UartHeader",
        },
        pin_functions={
            "U1.1": "UART1_TX",
            "U1.2": "UART1_RX",
            "U1.3": "VDD",
            "U1.4": "GND",
            "J1.1": "UART1_RX",
            "J1.2": "UART1_TX",
            "J1.3": "VDD",
            "J1.4": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
            "J1.1": "input",
            "J1.2": "output",
            "J1.3": "passive",
            "J1.4": "passive",
        },
        component_pin_numbers={"U1": ("1", "2", "3", "4"), "J1": ("1", "2", "3", "4")},
    )


def multi_uart_connector_reference_netlist(*, common_first_return: bool = False) -> NetlistContract:
    """One MCU with two UART headers: one split-reference fault and one control."""
    source = serial_connector_reference_netlist()
    nets = {net: tuple(pins) for net, pins in source.nets.items()}
    nets["+3V3"] = (*nets["+3V3"], "J2.3")
    nets["GND_A"] = (*nets["GND_A"], "J2.4")
    nets["UART2_TX"] = ("U1.5", "J2.1")
    nets["UART2_RX"] = ("U1.6", "J2.2")
    if common_first_return:
        nets["GND_A"] = (*nets["GND_A"], "J1.4")
        nets.pop("GND_B")

    return source.model_copy(
        update={
            "components": {
                **source.components,
                "J2": ComponentContract(
                    value="Synthetic second UART header", footprint="Package:UART-HEADER"
                ),
            },
            "nets": nets,
            "component_symbols": {
                **source.component_symbols,
                "J2": "Synthetic:UartHeader",
            },
            "pin_functions": {
                **source.pin_functions,
                "U1.5": "UART2_TX",
                "U1.6": "UART2_RX",
                "J2.1": "UART2_RX",
                "J2.2": "UART2_TX",
                "J2.3": "VDD",
                "J2.4": "GND",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.5": "output",
                "U1.6": "input",
                "J2.1": "input",
                "J2.2": "output",
                "J2.3": "passive",
                "J2.4": "passive",
            },
            "component_pin_numbers": {
                **source.component_pin_numbers,
                "U1": (*source.component_pin_numbers["U1"], "5", "6"),
                "J2": ("1", "2", "3", "4"),
            },
        }
    )


def serial_connector_peer_map(
    *, reference_policy: str, output_reference_net: str, input_reference_net: str
) -> SerialPeerAnalysis:
    return SerialPeerAnalysis(
        basis="Synthetic reviewed MCU-to-header UART link and reference policy",
        links=(
            SerialPeerLinkRequirement(
                id="controller-header",
                basis="Synthetic direct UART header link",
                endpoint=SerialEndpointRequirement(
                    id="controller",
                    reference="U1",
                    symbol="Synthetic:UartController",
                    footprint="Package:UART-CONTROLLER",
                    logic_domain="3V3",
                    tx=SerialPinNetRequirement(pin="U1.1", net="UART_TX"),
                    rx=SerialPinNetRequirement(pin="U1.2", net="UART_RX"),
                    reference_pins=(SerialPinNetRequirement(pin="U1.4", net=output_reference_net),),
                ),
                peer=SerialDirectPeerRequirement(
                    mode="direct",
                    endpoint=SerialEndpointRequirement(
                        id="header",
                        reference="J1",
                        symbol="Synthetic:UartHeader",
                        footprint="Package:UART-HEADER",
                        logic_domain="3V3",
                        tx=SerialPinNetRequirement(pin="J1.2", net="UART_RX"),
                        rx=SerialPinNetRequirement(pin="J1.1", net="UART_TX"),
                        reference_pins=(
                            SerialPinNetRequirement(pin="J1.4", net=input_reference_net),
                        ),
                    ),
                ),
                reference_policy=reference_policy,
            ),
        ),
    )


def report(
    source: NetlistContract,
    *,
    policy: DesignLintPolicy | None = None,
    serial_peers: SerialPeerAnalysis | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-serial-reference",
        observed=source,
        netlist_sha256="a" * 64,
    )
    return evaluate(
        "synthetic-serial-reference",
        coach,
        policy or DesignLintPolicy(),
        serial_peer_roster=(
            SerialPeerRosterContext(state="required", analysis=serial_peers)
            if serial_peers is not None
            else SerialPeerRosterContext(state="not_configured")
        ),
    )


class SerialPeerReferenceReviewTests(unittest.TestCase):
    def test_reference_coverage_distinguishes_evaluated_incomplete_and_unseen_links(self) -> None:
        split = report(serial_reference_netlist())
        self.assertIsNotNone(split.serial_peer_reference_coverage)
        assert split.serial_peer_reference_coverage is not None
        self.assertEqual(
            (
                split.serial_peer_reference_coverage.status,
                split.serial_peer_reference_coverage.native_peer_link_count,
                split.serial_peer_reference_coverage.supported_reference_link_count,
                split.serial_peer_reference_coverage.separate_reference_link_count,
                split.serial_peer_reference_coverage.candidate_group_count,
            ),
            ("EVALUATED", 2, 2, 2, 1),
        )

        common = report(
            serial_reference_netlist(output_reference_net="GND", input_reference_net="GND")
        )
        assert common.serial_peer_reference_coverage is not None
        self.assertEqual(
            (
                common.serial_peer_reference_coverage.status,
                common.serial_peer_reference_coverage.common_reference_link_count,
                common.serial_peer_reference_coverage.candidate_group_count,
            ),
            ("EVALUATED", 2, 0),
        )
        common_coverage = common.serial_peer_reference_coverage
        assert common_coverage is not None
        self.assertEqual(
            {item.disposition for item in common_coverage.link_entries or ()},
            {"COMMON_REFERENCE"},
        )

        source = serial_reference_netlist()
        incomplete_source = source.model_copy(
            update={
                "pin_functions": {
                    pin: function for pin, function in source.pin_functions.items() if pin != "U2.9"
                }
            }
        )
        incomplete = report(incomplete_source)
        assert incomplete.serial_peer_reference_coverage is not None
        self.assertEqual(
            (
                incomplete.serial_peer_reference_coverage.status,
                incomplete.serial_peer_reference_coverage.native_peer_link_count,
                incomplete.serial_peer_reference_coverage.incomplete_reference_link_count,
                incomplete.serial_peer_reference_coverage.candidate_group_count,
            ),
            ("INCOMPLETE", 2, 2, 0),
        )
        incomplete_coverage = incomplete.serial_peer_reference_coverage
        assert incomplete_coverage is not None
        self.assertEqual(
            tuple(
                (
                    item.discovery_basis,
                    item.first_reference,
                    item.second_reference,
                    item.signal_group,
                    item.signal_pins,
                    item.disposition,
                )
                for item in incomplete_coverage.link_entries or ()
            ),
            (
                ("native_function", "U1", "U2", "UART_A", ("U1.1", "U2.1"), "INCOMPLETE"),
                ("native_function", "U2", "U1", "UART_B", ("U2.2", "U1.2"), "INCOMPLETE"),
            ),
        )

        disconnected_source = source.model_copy(
            update={
                "nets": {
                    **source.nets,
                    "UART_A": ("U1.1",),
                    "UART_B": ("U1.2",),
                    "UART_RX_ONLY": ("U2.1",),
                    "UART_TX_ONLY": ("U2.2",),
                }
            }
        )
        disconnected = report(disconnected_source)
        assert disconnected.serial_peer_reference_coverage is not None
        self.assertEqual(
            (
                disconnected.serial_peer_reference_coverage.status,
                disconnected.serial_peer_reference_coverage.native_peer_link_count,
                disconnected.serial_peer_reference_coverage.label_peer_link_count,
            ),
            ("NO_DIRECT_PEERS", 0, 0),
        )

        rendered = text_report(incomplete)
        self.assertIn("UART peer-reference heuristic coverage:", rendered)
        self.assertIn(
            "2 discovered link(s) lacked complete explicit reference-pin evidence", rendered
        )
        self.assertIn(
            "native-function: U1 -> U2 (UART_A; nets UART_A; pins U1.1, U2.1): INCOMPLETE",
            rendered,
        )
        self.assertIn("Native netlist SHA-256:", rendered)

        legacy_payload = incomplete_coverage.model_dump()
        legacy_payload.pop("link_entries")
        self.assertIsNone(
            SerialPeerReferenceCoverageReport.model_validate(legacy_payload).link_entries
        )
        inconsistent_payload = incomplete_coverage.model_dump()
        inconsistent_payload["incomplete_reference_link_count"] = 0
        with self.assertRaisesRegex(ValidationError, "Incomplete serial link count"):
            SerialPeerReferenceCoverageReport.model_validate(inconsistent_payload)

    def test_reference_coverage_records_exact_map_suppression(self) -> None:
        source = serial_reference_netlist()
        reviewed = serial_peer_map(
            reference_policy="separate_nets",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
        )
        mapped = report(source, serial_peers=reviewed)
        assert mapped.serial_peer_reference_coverage is not None
        self.assertEqual(
            (
                mapped.serial_peer_reference_coverage.authored_map_state,
                mapped.serial_peer_reference_coverage.authored_serial_peer_map_sha256 is not None,
                mapped.serial_peer_reference_coverage.separate_reference_link_count,
                mapped.serial_peer_reference_coverage.mapped_separate_reference_link_count,
                mapped.serial_peer_reference_coverage.candidate_group_count,
            ),
            ("required", True, 2, 2, 0),
        )
        self.assertEqual(
            {item.disposition for item in mapped.serial_peer_reference_coverage.link_entries or ()},
            {"MAP_COVERED_SEPARATE_REFERENCE"},
        )

    def test_schema_one_report_without_serial_coverage_remains_readable(self) -> None:
        payload = report(serial_reference_netlist()).model_dump()
        payload["schema_version"] = "1"
        payload.pop("serial_peer_reference_coverage")

        legacy = DesignLintReport.model_validate(payload)

        self.assertEqual(legacy.schema_version, "1")
        self.assertIsNone(legacy.serial_peer_reference_coverage)

    def test_distinct_explicit_return_nets_prompt_with_exact_signal_and_pin_evidence(self) -> None:
        source = serial_reference_netlist()
        candidates = unmapped_serial_peer_reference_reviews(source)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(candidates[0].links), 2)
        self.assertEqual(candidates[0].first_reference_domain.net, "GND_A")
        self.assertEqual(candidates[0].second_reference_domain.net, "GND_B")

        lint = report(source)
        findings = [item for item in lint.findings if item.rule_id == RULE_ID]
        self.assertEqual(len(findings), 1)
        self.assertEqual(lint.status, "REVIEW")
        self.assertEqual(findings[0].mode, "review")
        self.assertEqual(findings[0].subject, "U1 / U2: serial reference-domain review")
        self.assertEqual(
            findings[0].evidence["shared_serial_pin_assignments"],
            (
                "UART_A: U1.1 (UART1_TX, output) -> U2.1 (UART1_RX, input)",
                "UART_B: U2.2 (UART1_TX, output) -> U1.2 (UART1_RX, input)",
            ),
        )
        self.assertEqual(
            findings[0].evidence["first_reference_pin_assignments"],
            ("U1.9 (GND, power_in)=GND_A",),
        )
        self.assertEqual(
            findings[0].evidence["second_reference_pin_assignments"],
            ("U2.9 (GND, power_in)=GND_B",),
        )

    def test_same_reference_net_is_a_quiet_control(self) -> None:
        source = serial_reference_netlist(
            output_reference_net="SIGNAL_RETURN", input_reference_net="SIGNAL_RETURN"
        )
        self.assertEqual(unmapped_serial_peer_reference_reviews(source), ())
        self.assertFalse(any(item.rule_id == RULE_ID for item in report(source).findings))

    def test_direct_mcu_to_serial_header_peer_reviews_split_reference_nets(self) -> None:
        source = serial_connector_reference_netlist()
        candidates = unmapped_serial_peer_reference_reviews(source)
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual({candidate.first_reference, candidate.second_reference}, {"U1", "J1"})
        self.assertEqual(
            {candidate.first_reference_domain.net, candidate.second_reference_domain.net},
            {"GND_A", "GND_B"},
        )
        self.assertEqual(len(candidate.links), 2)

        findings = [item for item in report(source).findings if item.rule_id == RULE_ID]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].subject, "J1 / U1: serial reference-domain review")
        self.assertEqual(
            findings[0].evidence["shared_serial_pin_assignments"],
            (
                "UART_RX: J1.2 (UART1_TX, output) -> U1.2 (UART1_RX, input)",
                "UART_TX: U1.1 (UART1_TX, output) -> J1.1 (UART1_RX, input)",
            ),
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
        self.assertEqual(
            {item.rule_id for item in other_findings},
            {"bus.serial_unmapped_peer", "power.ic_rail_without_fitted_capacitor"},
        )
        self.assertFalse(
            any(net in str(item.evidence) for item in other_findings for net in ("GND_A", "GND_B"))
        )

        common = serial_connector_reference_netlist(
            output_reference_net="GND", input_reference_net="GND"
        )
        self.assertEqual(unmapped_serial_peer_reference_reviews(common), ())

    def test_multi_uart_headers_localize_one_split_reference(self) -> None:
        source = multi_uart_connector_reference_netlist()
        candidates = unmapped_serial_peer_reference_reviews(source)
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual({candidate.first_reference, candidate.second_reference}, {"U1", "J1"})
        self.assertEqual({link.net for link in candidate.links}, {"UART_RX", "UART_TX"})
        self.assertNotIn("J2", {candidate.first_reference, candidate.second_reference})

        findings = [item for item in report(source).findings if item.rule_id == RULE_ID]
        self.assertEqual(len(findings), 1)
        reference_assignments = (
            *findings[0].evidence["first_reference_pin_assignments"],
            *findings[0].evidence["second_reference_pin_assignments"],
        )
        self.assertIn("J1.4 (GND, passive)=GND_B", reference_assignments)

    def test_multi_uart_headers_with_common_references_are_a_quiet_control(self) -> None:
        common = multi_uart_connector_reference_netlist(common_first_return=True)
        self.assertEqual(unmapped_serial_peer_reference_reviews(common), ())
        self.assertFalse(any(item.rule_id == RULE_ID for item in report(common).findings))

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
        self.assertEqual(
            unmapped_serial_peer_reference_reviews(source),
            unmapped_serial_peer_reference_reviews(reordered),
        )
        self.assertEqual(report(source).findings, report(reordered).findings)

    def test_source_matched_separate_header_reference_map_suppresses_prompt(self) -> None:
        source = serial_connector_reference_netlist()
        reviewed = serial_connector_peer_map(
            reference_policy="separate_nets",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
        )
        self.assertEqual(unmapped_serial_peer_reference_reviews(source, reviewed), ())
        self.assertFalse(
            any(item.rule_id == RULE_ID for item in report(source, serial_peers=reviewed).findings)
        )

        stale = serial_connector_peer_map(
            reference_policy="common_net",
            output_reference_net="GND",
            input_reference_net="GND",
        )
        self.assertEqual(len(unmapped_serial_peer_reference_reviews(source, stale)), 1)

    def test_exact_direct_map_suppresses_reviewed_common_or_separate_references(self) -> None:
        split = serial_reference_netlist()
        split_map = serial_peer_map(
            reference_policy="separate_nets",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
        )
        self.assertEqual(unmapped_serial_peer_reference_reviews(split, split_map), ())
        self.assertFalse(
            any(item.rule_id == RULE_ID for item in report(split, serial_peers=split_map).findings)
        )

        common = serial_reference_netlist(output_reference_net="GND", input_reference_net="GND")
        common_map = serial_peer_map(
            reference_policy="common_net", output_reference_net="GND", input_reference_net="GND"
        )
        self.assertEqual(unmapped_serial_peer_reference_reviews(common, common_map), ())

    def test_bonded_reference_map_suppresses_only_when_exact_bond_matches(self) -> None:
        bond = ReferenceBondRequirement(
            reference="R3",
            expected_symbol="Device:R",
            expected_footprint="Synthetic:0603",
            expected_value="0R",
            side_a_pin="R3.1",
            side_b_pin="R3.2",
            side_a_net="GND_A",
            side_b_net="GND_B",
        )
        reviewed = serial_peer_map(
            reference_policy="bonded",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
            reference_bond=bond,
        )
        control = bonded_serial_reference_netlist()
        self.assertEqual(unmapped_serial_peer_reference_reviews(control, reviewed), ())
        self.assertFalse(
            any(item.rule_id == RULE_ID for item in report(control, serial_peers=reviewed).findings)
        )

        fault = bonded_serial_reference_netlist(fault=True)
        findings = unmapped_serial_peer_reference_reviews(fault, reviewed)
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].first_reference_domain.net,
            "GND_A",
        )
        self.assertEqual(
            next(
                item
                for item in report(fault, serial_peers=reviewed).findings
                if item.rule_id == RULE_ID
            ).subject,
            "U1 / U2: serial reference-domain review",
        )

        label_map = labelled_serial_peer_map(
            reference_policy="bonded",
            first_reference_net="GND_A",
            second_reference_net="GND_B",
            reference_bond=bond,
        )
        self.assertEqual(
            unmapped_serial_peer_reference_reviews(
                bonded_label_serial_reference_netlist(), label_map
            ),
            (),
        )
        labelled_fault = unmapped_serial_peer_reference_reviews(
            bonded_label_serial_reference_netlist(fault=True), label_map
        )
        self.assertEqual(len(labelled_fault), 1)
        self.assertEqual(len(labelled_fault[0].label_links), 1)

    def test_stale_reference_map_does_not_suppress_prompt(self) -> None:
        source = serial_reference_netlist()
        stale = serial_peer_map(
            reference_policy="common_net", output_reference_net="GND", input_reference_net="GND"
        )
        self.assertEqual(len(unmapped_serial_peer_reference_reviews(source, stale)), 1)

    def test_map_of_supply_pins_does_not_suppress_return_domain_prompt(self) -> None:
        source = serial_reference_netlist()
        wrong_roles = serial_peer_map(
            reference_policy="common_net",
            output_reference_net="+3V3",
            input_reference_net="+3V3",
            output_reference_pin="U1.8",
            input_reference_pin="U2.8",
        )
        self.assertEqual(len(unmapped_serial_peer_reference_reviews(source, wrong_roles)), 1)

    def test_reference_domain_finding_is_order_stable_and_exact_map_clears_it(self) -> None:
        source = serial_reference_netlist()
        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        self.assertEqual(
            unmapped_serial_peer_reference_reviews(source),
            unmapped_serial_peer_reference_reviews(reordered),
        )
        self.assertEqual(
            report(source).findings,
            report(reordered).findings,
        )
        reviewed = serial_peer_map(
            reference_policy="separate_nets",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
        )
        self.assertEqual(unmapped_serial_peer_reference_reviews(source, reviewed), ())

    def test_channel_labelled_generic_ic_pair_reviews_split_reference_domains(self) -> None:
        source = labelled_serial_reference_netlist()
        candidates = unmapped_serial_peer_reference_reviews(source)
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual({candidate.first_reference, candidate.second_reference}, {"U1", "U2"})
        self.assertEqual(candidate.links, ())
        self.assertEqual(len(candidate.label_links), 1)
        link = candidate.label_links[0]
        self.assertEqual(link.channel, "uart0")
        self.assertEqual(link.tx_net, "Compute module/UART.0.TX")
        self.assertEqual(link.rx_net, "Compute module/UART.0.RX")
        self.assertEqual(
            {candidate.first_reference_domain.net, candidate.second_reference_domain.net},
            {"GND_A", "GND_B"},
        )

        lint_report = report(source)
        findings = [item for item in lint_report.findings if item.rule_id == RULE_ID]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, "review")
        self.assertIn("Exact UART/USART TX and RX channel labels", findings[0].message)
        coverage = lint_report.serial_peer_reference_coverage
        self.assertIsNotNone(coverage)
        assert coverage is not None
        self.assertEqual(
            (
                coverage.native_peer_link_count,
                coverage.label_peer_link_count,
                coverage.separate_reference_link_count,
                coverage.candidate_group_count,
            ),
            (0, 1, 1, 1),
        )
        self.assertEqual(
            findings[0].evidence["serial_label_link_assignments"],
            (
                "uart0: TX Compute module/UART.0.TX (U1.1, U2.2); "
                + "RX Compute module/UART.0.RX (U1.2, U2.1)",
            ),
        )
        self.assertEqual(findings[0].evidence["discovery_basis"], ("net_label",))
        self.assertEqual(
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
            ),
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
            ),
        )
        self.assertIn(
            "channel-label: U1 / U2 (uart0; nets Compute module/UART.0.TX, "
            "Compute module/UART.0.RX; pins U1.1, U2.2, U1.2, U2.1): "
            "SEPARATE_REFERENCE_REVIEW",
            text_report(lint_report),
        )

    def test_channel_labelled_generic_ic_pair_with_common_reference_is_quiet(self) -> None:
        source = labelled_serial_reference_netlist(
            first_reference_net="GND", second_reference_net="GND"
        )
        self.assertEqual(unmapped_serial_peer_reference_reviews(source), ())
        self.assertFalse(any(item.rule_id == RULE_ID for item in report(source).findings))

    def test_exact_channel_label_map_suppresses_but_stale_map_does_not(self) -> None:
        source = labelled_serial_reference_netlist()
        reviewed = labelled_serial_peer_map(
            reference_policy="separate_nets",
            first_reference_net="GND_A",
            second_reference_net="GND_B",
        )
        self.assertEqual(unmapped_serial_peer_reference_reviews(source, reviewed), ())
        self.assertFalse(
            any(item.rule_id == RULE_ID for item in report(source, serial_peers=reviewed).findings)
        )

        stale = labelled_serial_peer_map(
            reference_policy="separate_nets",
            first_reference_net="GND_C",
            second_reference_net="GND_D",
        )
        self.assertEqual(len(unmapped_serial_peer_reference_reviews(source, stale)), 1)

    def test_channel_label_candidate_skips_ambiguous_or_incomplete_cases(self) -> None:
        source = labelled_serial_reference_netlist()
        tx_net = "Compute module/UART.0.TX"
        rx_net = "Compute module/UART.0.RX"
        cases = {
            "DNP endpoint": source.model_copy(update={"dnp_components": ("U2",)}),
            "mismatched channel": source.model_copy(
                update={
                    "nets": {
                        **{net: pins for net, pins in source.nets.items() if net != rx_net},
                        "Compute module/UART.1.RX": source.nets[rx_net],
                    }
                }
            ),
            "third pin on signal net": source.model_copy(
                update={
                    "components": {
                        **source.components,
                        "U3": ComponentContract(value="Other", footprint="Package:Other"),
                    },
                    "nets": {**source.nets, tx_net: (*source.nets[tx_net], "U3.1")},
                }
            ),
            "missing signal pin function": source.model_copy(
                update={
                    "pin_functions": {
                        pin: function
                        for pin, function in source.pin_functions.items()
                        if pin != "U1.1"
                    }
                }
            ),
            "missing signal electrical type": source.model_copy(
                update={
                    "pin_electrical_types": {
                        pin: kind
                        for pin, kind in source.pin_electrical_types.items()
                        if pin != "U1.1"
                    }
                }
            ),
            "incomplete component pin inventory": source.model_copy(
                update={
                    "component_pin_numbers": {
                        reference: numbers
                        for reference, numbers in source.component_pin_numbers.items()
                        if reference != "U2"
                    }
                }
            ),
            "multiple return domains": source.model_copy(
                update={
                    "component_pin_numbers": {
                        **source.component_pin_numbers,
                        "U1": (*source.component_pin_numbers["U1"], "10"),
                    },
                    "pin_functions": {**source.pin_functions, "U1.10": "AGND"},
                    "pin_electrical_types": {
                        **source.pin_electrical_types,
                        "U1.10": "power_in",
                    },
                    "nets": {**source.nets, "AGND_LOCAL": ("U1.10",)},
                }
            ),
            "unqualified UART labels": source.model_copy(
                update={
                    "nets": {
                        **{
                            net: pins
                            for net, pins in source.nets.items()
                            if net not in {tx_net, rx_net}
                        },
                        "UART_TX": source.nets[tx_net],
                        "UART_RX": source.nets[rx_net],
                    }
                }
            ),
        }
        for name, candidate in cases.items():
            with self.subTest(case=name):
                self.assertEqual(unmapped_serial_peer_reference_reviews(candidate), ())

    def test_channel_label_candidate_is_order_stable(self) -> None:
        source = labelled_serial_reference_netlist()
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
        self.assertEqual(
            unmapped_serial_peer_reference_reviews(source),
            unmapped_serial_peer_reference_reviews(reordered),
        )
        self.assertEqual(report(source).findings, report(reordered).findings)

    def test_channel_label_candidate_obeys_rule_override_and_exact_ignore(self) -> None:
        source = labelled_serial_reference_netlist()
        open_finding = next(item for item in report(source).findings if item.rule_id == RULE_ID)
        disabled = report(
            source,
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="off",
                        reason="Synthetic isolated UART segment has separate approved references.",
                    ),
                )
            ),
        )
        disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
        self.assertEqual(disabled_finding.disposition, "RULE_OFF")

        ignored = report(
            source,
            policy=DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=open_finding.fingerprint,
                        reason="Synthetic owner recorded the isolated-interface review.",
                    ),
                )
            ),
        )
        ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
        self.assertEqual(ignored_finding.disposition, "IGNORED")

    def test_incomplete_or_ambiguous_native_reference_evidence_is_skipped(self) -> None:
        source = serial_reference_netlist()
        cases = {
            "DNP endpoint": source.model_copy(update={"dnp_components": ("U2",)}),
            "missing return pin type": source.model_copy(
                update={
                    "pin_electrical_types": {
                        key: value
                        for key, value in source.pin_electrical_types.items()
                        if key != "U1.9"
                    }
                }
            ),
            "missing pin function inventory": source.model_copy(
                update={
                    "pin_functions": {
                        key: value for key, value in source.pin_functions.items() if key != "U1.8"
                    }
                }
            ),
            "shield return is not a signal reference": source.model_copy(
                update={
                    "pin_functions": {
                        **source.pin_functions,
                        "U1.9": "SHIELD_GND",
                        "U2.9": "CHASSIS_GND",
                    }
                }
            ),
            "multiple return nets on endpoint": source.model_copy(
                update={
                    "components": {
                        **source.components,
                        "U1": source.components["U1"],
                    },
                    "component_pin_numbers": {
                        **source.component_pin_numbers,
                        "U1": (*source.component_pin_numbers["U1"], "10"),
                    },
                    "pin_functions": {**source.pin_functions, "U1.10": "AGND"},
                    "pin_electrical_types": {
                        **source.pin_electrical_types,
                        "U1.10": "power_in",
                    },
                    "nets": {**source.nets, "AGND_LOCAL": ("U1.10",)},
                }
            ),
        }
        for name, candidate in cases.items():
            with self.subTest(case=name):
                self.assertEqual(unmapped_serial_peer_reference_reviews(candidate), ())

    def test_rule_mode_and_exact_ignore_are_project_configurable(self) -> None:
        source = serial_reference_netlist()
        open_finding = next(item for item in report(source).findings if item.rule_id == RULE_ID)
        blocked = report(
            source,
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="block",
                        reason="Synthetic project explicitly requires common UART reference.",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")
        self.assertEqual(
            next(item for item in blocked.findings if item.rule_id == RULE_ID).mode, "block"
        )

        disabled = report(
            source,
            policy=DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=RULE_ID,
                        mode="off",
                        reason="Synthetic isolated interface review is covered elsewhere.",
                    ),
                )
            ),
        )
        disabled_finding = next(item for item in disabled.findings if item.rule_id == RULE_ID)
        self.assertEqual(disabled_finding.disposition, "RULE_OFF")
        self.assertEqual(
            disabled_finding.reason, "Synthetic isolated interface review is covered elsewhere."
        )

        ignored = report(
            source,
            policy=DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=RULE_ID,
                        fingerprint=open_finding.fingerprint,
                        reason="Synthetic project owner reviewed the explicit separate-reference design.",
                    ),
                )
            ),
        )
        ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(
            ignored_finding.reason,
            "Synthetic project owner reviewed the explicit separate-reference design.",
        )


if __name__ == "__main__":
    unittest.main()
