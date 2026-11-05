"""Verify labeled serial signal and reference-domain review cases."""

from __future__ import annotations

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .ci_hosted_digital_peer_models import (
    SERIAL_LABEL_REFERENCE_CASES,
    DigitalPeerFixtureCase,
)
from .ci_hosted_native_fixture_models import NativeRun, NativeRunPair
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.contracts import read_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.models import DesignLintPolicy
from .hwrepo.serial_logic_models import SerialLabelFixtureExpectedNets


def verify_serial_label_reference_cases(ctx: DigitalPeerFixtureContext):
    """Verify labeled serial signal and reference-domain review cases."""
    expected_signal_data = read_model(
        ctx.fixture_root / "serial-peer-connector-reference-native/serial-label-expected-nets.json",
        SerialLabelFixtureExpectedNets,
    )
    expected_signal_nets = {
        "UART.0.RX": expected_signal_data.rx,
        "UART.0.TX": expected_signal_data.tx,
    }
    for case in SERIAL_LABEL_REFERENCE_CASES:
        connector_case = case.startswith("serial-label-connector-")
        peer_reference = "J1" if connector_case else "U2"
        peer_contracts = ctx.fixture(case).netlists
        peer_observed = peer_contracts.first.contract
        if (
            ctx.fixture(case).netlists.first.normalized_sha256
            != ctx.fixture(case).netlists.repeat.normalized_sha256
        ):
            raise ValueError(
                f"Native UART label {case} exports differ after typed-netlist normalization"
            )
        expected_functions = {
            "U1.1": "B2",
            "U1.2": "B1",
            "U1.3": "VDD",
            "U1.4": "GND",
            f"{peer_reference}.1": "ADBUS0",
            f"{peer_reference}.2": "ADBUS1",
            f"{peer_reference}.3": "VDD",
            f"{peer_reference}.4": "GND",
        }
        expected_pin_types = {
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
            f"{peer_reference}.1": "input",
            f"{peer_reference}.2": "output",
            f"{peer_reference}.3": "passive",
            f"{peer_reference}.4": "passive",
        }
        expected_symbols = {
            "U1": "Synthetic:UartController",
            peer_reference: "Synthetic:UartBridge",
        }
        expected_pin_numbers = {
            "U1": ("1", "2", "3", "4"),
            peer_reference: ("1", "2", "3", "4"),
        }
        expected_signal_nets = {
            net: tuple(sorted(pin.replace("U2.", f"{peer_reference}.", 1) for pin in pins))
            for net, pins in {
                "UART.0.RX": expected_signal_data.rx,
                "UART.0.TX": expected_signal_data.tx,
            }.items()
        }
        control_case = case in {"serial-label-control", "serial-label-connector-control"}
        expected_references = (
            {"GND_A": tuple(sorted(("U1.4", f"{peer_reference}.4")))}
            if control_case
            else {"GND_A": ("U1.4",), "GND_B": (f"{peer_reference}.4",)}
        )
        if (
            peer_observed.pin_functions != expected_functions
            or peer_observed.pin_electrical_types != expected_pin_types
            or peer_observed.component_symbols != expected_symbols
            or (peer_observed.component_pin_numbers != expected_pin_numbers)
        ):
            raise ValueError(f"Native UART label {case} export lost exact generic pin evidence")
        if {
            net: pins for (net, pins) in peer_observed.nets.items() if net.startswith("GND")
        } != expected_references:
            raise ValueError(f"Native UART label {case} export changed its reference assignments")
        if {
            net: pins for (net, pins) in peer_observed.nets.items() if net.startswith("UART.")
        } != expected_signal_nets:
            raise ValueError(f"Native UART label {case} export changed its labeled TX/RX nets")

        def report_for(run: NativeRun, fixture_case: DigitalPeerFixtureCase) -> DesignLintReport:
            report_coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-uart-label-reference-{fixture_case}",
                observed=ctx.fixture(fixture_case).netlists.for_run(run).contract,
                netlist_sha256=ctx.fixture(fixture_case).netlists.for_run(run).netlist_sha256,
            )
            return evaluate(report_coach.project_id, report_coach, DesignLintPolicy())

        reports = NativeRunPair(
            first=report_for("first", case),
            repeat=report_for("repeat", case),
        )
        reference_findings = tuple(
            item
            for item in reports.first.findings
            if item.rule_id == "bus.serial_peer_reference_review"
        )
        first_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports.first.findings
        )
        repeated_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports.repeat.findings
        )
        expected_reference_count = 0 if control_case else 1
        if (
            first_signature != repeated_signature
            or reports.first.status != "REVIEW"
            or reports.repeat.status != "REVIEW"
            or (len(reference_findings) != expected_reference_count)
        ):
            raise ValueError(
                f"Native UART label {case} no longer matches its reference review case"
            )
        if connector_case:
            expected_subject = "J1 / U1: serial reference-domain review"
            expected_evidence = {
                "discovery_basis": ("net_label",),
                "first_component": ("J1",),
                "first_reference_net": ("GND_B",),
                "first_reference_pin_assignments": ("J1.4 (GND, passive)=GND_B",),
                "second_component": ("U1",),
                "second_reference_net": ("GND_A",),
                "second_reference_pin_assignments": ("U1.4 (GND, power_in)=GND_A",),
                "serial_label_link_assignments": (
                    "uart0: TX UART.0.TX (J1.1, U1.1); RX UART.0.RX (J1.2, U1.2)",
                ),
                "serial_peer_map_state": ("not_configured",),
            }
        else:
            expected_subject = "U1 / U2: serial reference-domain review"
            expected_evidence = {
                "discovery_basis": ("net_label",),
                "first_component": ("U1",),
                "first_reference_net": ("GND_A",),
                "first_reference_pin_assignments": ("U1.4 (GND, power_in)=GND_A",),
                "second_component": ("U2",),
                "second_reference_net": ("GND_B",),
                "second_reference_pin_assignments": ("U2.4 (GND, passive)=GND_B",),
                "serial_label_link_assignments": (
                    "uart0: TX UART.0.TX (U1.1, U2.1); RX UART.0.RX (U1.2, U2.2)",
                ),
                "serial_peer_map_state": ("not_configured",),
            }
        if reference_findings and (
            reference_findings[0].mode != "review"
            or reference_findings[0].subject != expected_subject
            or dict(reference_findings[0].evidence) != expected_evidence
        ):
            raise ValueError("Native UART label reference finding lost exact pin/net evidence")
        ctx.log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            source_sha256=ctx.fixture(case).source.sha256,
            netlist_sha256=ctx.fixture(case).netlists.first.netlist_sha256,
            repeat_netlist_sha256=ctx.fixture(case).netlists.repeat.netlist_sha256,
            normalized_netlist_sha256=ctx.fixture(case).netlists.first.normalized_sha256,
            repeat_normalized_netlist_sha256=ctx.fixture(case).netlists.repeat.normalized_sha256,
            lint_status=reports.first.status,
            peer_reference_findings=";".join(item.rule_id for item in reference_findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}" for (pin, name) in sorted(peer_observed.pin_functions.items())
            ),
            pin_types=";".join(
                f"{pin}={name}"
                for (pin, name) in sorted(peer_observed.pin_electrical_types.items())
            ),
            signal_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_signal_nets)
            ),
            reference_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_references)
            ),
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )
