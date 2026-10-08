"""Synthetic coverage for likely UART endpoints omitted from the peer map."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint import _serial_peer_roster_context, evaluate
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    AnalysisPending,
    ComponentContract,
    ComponentIdentity,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    ElectricalAnalysisContract,
    IgnoredChecks,
    NetlistContract,
    ProjectConfig,
    ProjectKind,
    SchematicValidationContract,
    SerialDirectPeerRequirement,
    SerialEndpointRequirement,
    SerialPeerAnalysis,
    SerialPeerLinkRequirement,
    SerialPinNetRequirement,
)
from kicad_tooling.hwrepo.serial_participants import (
    SerialPeerRosterContext,
    unmapped_serial_peers,
)

_NETLIST_SHA256 = "a" * 64


def serial_netlist(*, dnp: tuple[str, ...] = ()) -> NetlistContract:
    components = {
        reference: ComponentContract(value=f"Synthetic {reference}", footprint="Synthetic:Header")
        for reference in ("J1", "J2", "J3", "J4", "U1")
    }
    functions = {
        "J1.1": "TX",
        "J1.2": "RX",
        "J2.1": "TXD",
        "J2.2": "RXD",
        "J3.1": "UART_TXD",
        "J3.2": "UART_RXD",
        "J4.1": "TX",
        "J4.2": "RX",
        "U1.1": "USART1_TX",
        "U1.2": "USART1_RX",
        "U1.3": "UART2_TXD",
        "U1.4": "UART2_RXD",
        "U1.5": "TX+",
        "U1.6": "RX-",
    }
    nets = {
        "SERIAL_A_TX": ("J1.1", "J2.2"),
        "SERIAL_A_RX": ("J1.2", "J2.1"),
        "SERIAL_B_TX": ("J3.1",),
        "SERIAL_B_RX": ("J3.2",),
        "J4_TX": ("J4.1",),
        "J4_RX": ("J4.2",),
        "UART1_TX": ("U1.1",),
        "UART1_RX": ("U1.2",),
        "UART2_TX": ("U1.3",),
        "UART2_RX": ("U1.4",),
        "DIFF_TX_P": ("U1.5",),
        "DIFF_RX_N": ("U1.6",),
    }
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols={reference: f"Synthetic:{reference}" for reference in components},
        pin_functions=functions,
        component_pin_numbers={
            reference: tuple(
                pin.rsplit(".", 1)[1] for pin in functions if pin.startswith(f"{reference}.")
            )
            for reference in components
        },
    )


def alternate_function_serial_netlist(*, dnp: tuple[str, ...] = ()) -> NetlistContract:
    """Use explicit UART net labels with MCU package-pin functions and generic connector pins."""
    components = {
        "U1": ComponentContract(value="Synthetic MCU", footprint="Synthetic:MCU"),
        "J5": ComponentContract(value="Synthetic serial header", footprint="Synthetic:Header"),
    }
    return NetlistContract(
        components=components,
        nets={
            "UART_TX": ("J5.1", "U1.1"),
            "UART_RX": ("J5.2", "U1.2"),
            "GND": ("J5.3", "U1.3"),
        },
        dnp_components=dnp,
        component_symbols={"U1": "Synthetic:GPIO_MCU", "J5": "Synthetic:GenericHeader"},
        pin_functions={
            "U1.1": "PA2",
            "U1.2": "PA3",
            "U1.3": "VSS",
            "J5.1": "Pin_1",
            "J5.2": "Pin_2",
            "J5.3": "Pin_3",
        },
        pin_electrical_types={
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "power_in",
            "J5.1": "passive",
            "J5.2": "passive",
            "J5.3": "passive",
        },
        component_pin_numbers={"U1": ("1", "2", "3"), "J5": ("1", "2", "3")},
    )


def endpoint(
    reference: str,
    *,
    tx_pin: str,
    tx_net: str,
    rx_pin: str,
    rx_net: str,
) -> SerialEndpointRequirement:
    return SerialEndpointRequirement(
        id=reference,
        reference=reference,
        symbol=f"Synthetic:{reference}",
        footprint="Synthetic:Header",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin=tx_pin, net=tx_net),
        rx=SerialPinNetRequirement(pin=rx_pin, net=rx_net),
    )


def serial_peers() -> SerialPeerAnalysis:
    left = endpoint("J1", tx_pin="J1.1", tx_net="SERIAL_A_TX", rx_pin="J1.2", rx_net="SERIAL_A_RX")
    right = endpoint("J2", tx_pin="J2.1", tx_net="SERIAL_A_RX", rx_pin="J2.2", rx_net="SERIAL_A_TX")
    return SerialPeerAnalysis(
        basis="Synthetic reviewed logic-level UART peer map",
        links=(
            SerialPeerLinkRequirement(
                id="main-console",
                basis="Synthetic paired connector endpoints",
                endpoint=left,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=right),
                reference_policy="not_applicable",
            ),
        ),
    )


def alternate_function_serial_peer_analysis() -> SerialPeerAnalysis:
    """Return the exact synthetic MCU-to-header UART map for label discovery tests."""
    mapped_endpoint = SerialEndpointRequirement(
        id="U1",
        reference="U1",
        symbol="Synthetic:GPIO_MCU",
        footprint="Synthetic:MCU",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U1.1", net="UART_TX"),
        rx=SerialPinNetRequirement(pin="U1.2", net="UART_RX"),
    )
    mapped_connector = SerialEndpointRequirement(
        id="J5",
        reference="J5",
        symbol="Synthetic:GenericHeader",
        footprint="Synthetic:Header",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="J5.2", net="UART_RX"),
        rx=SerialPinNetRequirement(pin="J5.1", net="UART_TX"),
    )
    return SerialPeerAnalysis(
        basis="Synthetic project-authored net-label endpoint map",
        links=(
            SerialPeerLinkRequirement(
                id="mcu-header",
                basis="Synthetic exact endpoint map",
                endpoint=mapped_endpoint,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=mapped_connector),
                reference_policy="not_applicable",
            ),
        ),
    )


def coach(observed: NetlistContract, netlist_sha256: str = _NETLIST_SHA256) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-serial-roster",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )


class SerialParticipantLintTests(unittest.TestCase):
    def test_unmapped_endpoints_are_deterministic_and_exact_mapped_pairs_clear(self) -> None:
        source = serial_netlist(dnp=("J4",))
        rule_id = "bus.serial_unmapped_peer"
        analysis = serial_peers()
        analysis_hash = hashlib.sha256(analysis.model_dump_json().encode("utf-8")).hexdigest()
        context = SerialPeerRosterContext(
            state="required",
            analysis=analysis,
            source_path="projects/synthetic-serial-roster/electrical.json",
            source_sha256=analysis_hash,
        )
        report = evaluate(
            "synthetic-serial-roster", coach(source), DesignLintPolicy(), serial_peer_roster=context
        )
        findings = [item for item in report.findings if item.rule_id == rule_id]
        self.assertEqual(
            tuple(item.subject for item in findings),
            (
                "J3: serial-peer map coverage (UART)",
                "U1: serial-peer map coverage (UART2)",
                "U1: serial-peer map coverage (USART1)",
            ),
        )
        self.assertEqual(findings[0].evidence["TX_pins"], ("J3.1",))
        self.assertEqual(findings[0].evidence["RX_pins"], ("J3.2",))
        self.assertEqual(findings[0].evidence["serial_peer_map_state"], ("required",))
        self.assertEqual(findings[0].evidence["electrical_contract_sha256"], (analysis_hash,))

        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered_report = evaluate(
            "synthetic-serial-roster",
            coach(reordered),
            DesignLintPolicy(),
            serial_peer_roster=context,
        )
        reordered_findings = [item for item in reordered_report.findings if item.rule_id == rule_id]
        self.assertEqual(
            tuple((item.fingerprint, item.evidence) for item in reordered_findings),
            tuple((item.fingerprint, item.evidence) for item in findings),
        )

    def test_missing_map_and_pending_states_prompt_without_asserting_intent(self) -> None:
        source = serial_netlist(dnp=("J4",))
        for context, expected_text in (
            (
                SerialPeerRosterContext(state="not_configured"),
                "no configured project serial-peer map",
            ),
            (SerialPeerRosterContext(state="pending"), "review remains pending"),
            (SerialPeerRosterContext(state="not_applicable"), "marked not applicable"),
        ):
            with self.subTest(state=context.state):
                report = evaluate(
                    "synthetic-serial-roster",
                    coach(source),
                    DesignLintPolicy(),
                    serial_peer_roster=context,
                )
                finding = next(
                    item
                    for item in report.findings
                    if item.rule_id == "bus.serial_unmapped_peer" and item.subject.startswith("J1:")
                )
                self.assertIn(expected_text, finding.message)
                self.assertIn(
                    "does not assert that a peer or connection is required", finding.message
                )

    def test_authored_external_peers_clear_singleton_uart_coverage_prompts(self) -> None:
        source = serial_netlist()
        map_path = (
            Path(__file__).parent
            / "fixtures/design_lint/serial-peer-native/peer-map-with-offboard-endpoints.json"
        )
        analysis = read_model(map_path, SerialPeerAnalysis)
        context = SerialPeerRosterContext(
            state="required",
            analysis=analysis,
            source_path=map_path.as_posix(),
            source_sha256=hashlib.sha256(map_path.read_bytes()).hexdigest(),
        )

        report = evaluate(
            "synthetic-serial-roster",
            coach(source),
            DesignLintPolicy(),
            serial_peer_roster=context,
        )

        findings = tuple(
            item for item in report.findings if item.rule_id == "bus.serial_unmapped_peer"
        )
        self.assertTrue(findings)
        self.assertFalse(
            any(item.subject.startswith(("J1:", "J2:", "J3:", "J4:")) for item in findings)
        )
        self.assertEqual(
            {item.subject for item in findings},
            {
                "U1: serial-peer map coverage (UART2)",
                "U1: serial-peer map coverage (USART1)",
            },
        )

    def test_explicit_uart_net_labels_discover_alternate_function_mcu_pins(self) -> None:
        source = alternate_function_serial_netlist()
        candidates = unmapped_serial_peers(source, SerialPeerRosterContext(state="not_configured"))

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].reference, "U1")
        self.assertEqual(candidates[0].channel, "UART")
        self.assertEqual(candidates[0].tx_pins, ("U1.1",))
        self.assertEqual(candidates[0].rx_pins, ("U1.2",))
        self.assertEqual(candidates[0].discovery_basis, "net_label")
        self.assertEqual(
            candidates[0].signal_assignments,
            ("U1.1=UART_TX", "U1.2=UART_RX"),
        )

        report = evaluate("synthetic-serial-roster", coach(source), DesignLintPolicy())
        finding = next(
            item for item in report.findings if item.rule_id == "bus.serial_unmapped_peer"
        )
        self.assertEqual(finding.mode, "review")
        self.assertEqual(finding.evidence["discovery_basis"], ("net_label",))
        self.assertIn("explicitly UART/USART-labeled TX/RX nets", finding.message)
        self.assertIn("does not assert that a peer or connection is required", finding.message)

        analysis = alternate_function_serial_peer_analysis()
        mapped = unmapped_serial_peers(
            source,
            SerialPeerRosterContext(state="required", analysis=analysis),
        )
        self.assertEqual(mapped, ())

    def test_net_label_serial_discovery_rejects_ambiguous_or_incomplete_controls(self) -> None:
        source = alternate_function_serial_netlist()
        cases = {
            "connector-is-off-board-absent": source.model_copy(
                update={"nets": {"UART_TX": ("U1.1",), "UART_RX": ("U1.2",), "GND": ("U1.3",)}}
            ),
            "channel-mismatch": source.model_copy(
                update={
                    "nets": {
                        "UART1_TX": ("J5.1", "U1.1"),
                        "UART2_RX": ("J5.2", "U1.2"),
                        "GND": ("J5.3", "U1.3"),
                    }
                }
            ),
            "dnp-connector": alternate_function_serial_netlist(dnp=("J5",)),
            "ambiguous-mcu-pin": source.model_copy(
                update={
                    "nets": {
                        **source.nets,
                        "UART_TX": ("J5.1", "U1.1", "U1.4"),
                    },
                    "pin_functions": {**source.pin_functions, "U1.4": "PA4"},
                    "component_pin_numbers": {
                        **source.component_pin_numbers,
                        "U1": ("1", "2", "3", "4"),
                    },
                }
            ),
            "bare-signal-labels": source.model_copy(
                update={
                    "nets": {
                        "TX": ("J5.1", "U1.1"),
                        "RX": ("J5.2", "U1.2"),
                        "GND": ("J5.3", "U1.3"),
                    }
                }
            ),
        }
        for name, candidate in cases.items():
            with self.subTest(name=name):
                self.assertEqual(
                    unmapped_serial_peers(
                        candidate, SerialPeerRosterContext(state="not_configured")
                    ),
                    (),
                )

    def test_net_label_discovery_is_order_stable_and_does_not_duplicate_pin_function_findings(
        self,
    ) -> None:
        source = alternate_function_serial_netlist()
        baseline = unmapped_serial_peers(source, SerialPeerRosterContext(state="not_configured"))
        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        self.assertEqual(
            unmapped_serial_peers(reordered, SerialPeerRosterContext(state="not_configured")),
            baseline,
        )

        native_roles = source.model_copy(
            update={
                "pin_functions": {
                    **source.pin_functions,
                    "U1.1": "UART_TX",
                    "U1.2": "UART_RX",
                }
            }
        )
        findings = unmapped_serial_peers(
            native_roles, SerialPeerRosterContext(state="not_configured")
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].discovery_basis, "pin_function")

    def test_rule_mode_and_exact_ignore_remain_project_configurable(self) -> None:
        source = serial_netlist(dnp=("J4",))
        review = evaluate("synthetic-serial-roster", coach(source), DesignLintPolicy())
        finding = next(
            item for item in review.findings if item.rule_id == "bus.serial_unmapped_peer"
        )
        self.assertEqual(finding.mode, "review")

        blocked = evaluate(
            "synthetic-serial-roster",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=finding.rule_id,
                        mode="block",
                        reason="Synthetic project requires each logic-level UART endpoint to be mapped",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-serial-roster",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic endpoint is intentionally unused",
                    ),
                )
            ),
        )
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == finding.rule_id and item.fingerprint == finding.fingerprint
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")

    def test_contract_loader_hash_binds_serial_peer_roster(self) -> None:
        with TemporaryDirectory(prefix="synthetic-serial-roster-") as temporary:
            root = Path(temporary).resolve()
            contract_path = root / "projects/synthetic-serial-roster/electrical.json"
            contract = ElectricalAnalysisContract(
                project_id="synthetic-serial-roster",
                ngspice_version="synthetic",
                grounding=AnalysisPending(reason="Synthetic grounding review pending."),
                power=AnalysisPending(reason="Synthetic power review pending."),
                high_frequency=AnalysisPending(reason="Synthetic frequency review pending."),
                serial_peers=serial_peers(),
            )
            contract_path.parent.mkdir(parents=True)
            write_model(contract_path, contract)
            source_sha256 = digest(contract_path)
            config = ProjectConfig(
                schema_version="1",
                kind=ProjectKind.SCHEMATIC,
                assurance_profile="development",
                not_for_manufacture=True,
                project_id="synthetic-serial-roster",
                component_identity=ComponentIdentity(required=False, part_ids=()),
                toolchain_id="synthetic-kicad-10",
                kicad_version="10.0.6",
                image="example.invalid/kicad@sha256:" + "c" * 64,
                project="projects/synthetic-serial-roster/design.kicad_pro",
                source_roots=(),
                required_inputs=(),
                validation=SchematicValidationContract(
                    kind=ProjectKind.SCHEMATIC,
                    expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
                ),
                electrical="projects/synthetic-serial-roster/electrical.json",
            )
            context = _serial_peer_roster_context(root, config)

        self.assertEqual(context.state, "required")
        self.assertEqual(context.analysis, contract.serial_peers)
        self.assertEqual(context.source_path, "projects/synthetic-serial-roster/electrical.json")
        self.assertEqual(context.source_sha256, source_sha256)

    def test_dnp_ambiguous_and_differential_function_pairs_are_excluded(self) -> None:
        observed = serial_netlist(dnp=("J4",)).model_copy(
            update={
                "nets": {
                    **serial_netlist(dnp=("J4",)).nets,
                    "AMBIGUOUS": ("J3.1",),
                }
            }
        )
        candidates = unmapped_serial_peers(
            observed, SerialPeerRosterContext(state="not_configured")
        )
        found = {(item.reference, item.channel) for item in candidates}
        self.assertNotIn(("J4", "TX/RX"), found)
        self.assertNotIn(("U1", "channel 1"), found)
        self.assertEqual(
            found,
            {("J1", "TX/RX"), ("J2", "TX/RX"), ("U1", "USART1"), ("U1", "UART2")},
        )


if __name__ == "__main__":
    unittest.main()
