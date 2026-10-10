"""Verify labeled serial signal and reference-domain review cases."""

from __future__ import annotations

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .hwrepo.contracts import read_model
from .hwrepo.design_lint import evaluate
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    SerialLabelFixtureExpectedNets,
)


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
    for case in ("serial-label-control", "serial-label-fault"):
        peer_contracts = ctx.contracts[case]
        peer_observed = peer_contracts["first"]
        if ctx.normalized_hashes[case]["first"] != ctx.normalized_hashes[case]["repeat"]:
            raise ValueError(
                f"Native UART label {case} exports differ after typed-netlist normalization"
            )
        expected_functions = {
            "U1.1": "B2",
            "U1.2": "B1",
            "U1.3": "VDD",
            "U1.4": "GND",
            "U2.1": "ADBUS0",
            "U2.2": "ADBUS1",
            "U2.3": "VDD",
            "U2.4": "GND",
        }
        expected_pin_types = {
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
            "U2.1": "input",
            "U2.2": "output",
            "U2.3": "passive",
            "U2.4": "passive",
        }
        expected_symbols = {"U1": "Synthetic:UartController", "U2": "Synthetic:UartBridge"}
        expected_pin_numbers = {"U1": ("1", "2", "3", "4"), "U2": ("1", "2", "3", "4")}
        expected_references = (
            {"GND_A": ("U1.4", "U2.4")}
            if case == "serial-label-control"
            else {"GND_A": ("U1.4",), "GND_B": ("U2.4",)}
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
        reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            report_coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-uart-label-reference-{case}",
                observed=peer_contracts[run],
                netlist_sha256=ctx.hashes[case][run],
            )
            reports[run] = evaluate(report_coach.project_id, report_coach, DesignLintPolicy())
        reference_findings = tuple(
            item
            for item in reports["first"].findings
            if item.rule_id == "bus.serial_peer_reference_review"
        )
        first_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["first"].findings
        )
        repeated_signature = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in reports["repeat"].findings
        )
        expected_reference_count = 0 if case == "serial-label-control" else 1
        if (
            first_signature != repeated_signature
            or reports["first"].status != "REVIEW"
            or reports["repeat"].status != "REVIEW"
            or (len(reference_findings) != expected_reference_count)
        ):
            raise ValueError(
                f"Native UART label {case} no longer matches its reference review case"
            )
        if reference_findings and (
            reference_findings[0].mode != "review"
            or reference_findings[0].subject != "U1 / U2: serial reference-domain review"
            or dict(reference_findings[0].evidence)
            != {
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
        ):
            raise ValueError("Native UART label reference finding lost exact pin/net evidence")
        ctx.log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            source_sha256=ctx.serial_label_reference_source_hashes[case],
            netlist_sha256=ctx.hashes[case]["first"],
            repeat_netlist_sha256=ctx.hashes[case]["repeat"],
            normalized_netlist_sha256=ctx.normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=ctx.normalized_hashes[case]["repeat"],
            lint_status=reports["first"].status,
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
