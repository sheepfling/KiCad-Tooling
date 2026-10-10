"""Verify connector-level serial reference-domain review cases."""

from __future__ import annotations

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .hwrepo.design_lint import evaluate
from .hwrepo.models import ContractCoachReport, DesignLintPolicy, DesignLintReport


def verify_serial_connector_reference_cases(
    ctx: DigitalPeerFixtureContext, serial_peer_policy: DesignLintPolicy
):
    """Verify connector-level serial reference-domain review cases."""
    for case in ("serial-connector-control", "serial-connector-fault"):
        peer_contracts = ctx.contracts[case]
        peer_observed = peer_contracts["first"]
        if ctx.normalized_hashes[case]["first"] != ctx.normalized_hashes[case]["repeat"]:
            raise ValueError(
                f"Native UART connector {case} exports differ after typed-netlist normalization"
            )
        expected_functions = {
            "J1.1": "UART1_RX",
            "J1.2": "UART1_TX",
            "J1.3": "VDD",
            "J1.4": "GND",
            "U1.1": "UART1_TX",
            "U1.2": "UART1_RX",
            "U1.3": "VDD",
            "U1.4": "GND",
        }
        expected_pin_types = {
            "J1.1": "input",
            "J1.2": "output",
            "J1.3": "passive",
            "J1.4": "passive",
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
        }
        expected_symbols = {"J1": "Synthetic:UartHeader", "U1": "Synthetic:UartController"}
        expected_pin_numbers = {"J1": ("1", "2", "3", "4"), "U1": ("1", "2", "3", "4")}
        expected_references = (
            {"GND_A": ("J1.4", "U1.4")}
            if case == "serial-connector-control"
            else {"GND_A": ("U1.4",), "GND_B": ("J1.4",)}
        )
        if (
            peer_observed.pin_functions != expected_functions
            or peer_observed.pin_electrical_types != expected_pin_types
            or peer_observed.component_symbols != expected_symbols
            or (peer_observed.component_pin_numbers != expected_pin_numbers)
        ):
            raise ValueError(f"Native UART connector {case} export lost exact symbol pin evidence")
        if {
            net: pins for (net, pins) in peer_observed.nets.items() if net.startswith("GND")
        } != expected_references:
            raise ValueError(
                f"Native UART connector {case} export changed its reference assignments"
            )
        expected_signal_nets = {"UART_RX": ("J1.2", "U1.2"), "UART_TX": ("J1.1", "U1.1")}
        if {
            net: pins for (net, pins) in peer_observed.nets.items() if net.startswith("UART_")
        } != expected_signal_nets:
            raise ValueError(f"Native UART connector {case} export changed its TX/RX assignments")
        reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            report_coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-uart-connector-reference-{case}",
                observed=peer_contracts[run],
                netlist_sha256=ctx.hashes[case][run],
            )
            reports[run] = evaluate(report_coach.project_id, report_coach, serial_peer_policy)
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
        expected_reference_count = 0 if case == "serial-connector-control" else 1
        if (
            first_signature != repeated_signature
            or reports["first"].status != "REVIEW"
            or reports["repeat"].status != "REVIEW"
            or (len(reference_findings) != expected_reference_count)
        ):
            raise ValueError(
                f"Native UART connector {case} no longer matches its reference review case"
            )
        if reference_findings and (
            reference_findings[0].mode != "review"
            or reference_findings[0].subject != "J1 / U1: serial reference-domain review"
            or dict(reference_findings[0].evidence)
            != {
                "first_component": ("J1",),
                "first_reference_net": ("GND_B",),
                "first_reference_pin_assignments": ("J1.4 (GND, passive)=GND_B",),
                "second_component": ("U1",),
                "second_reference_net": ("GND_A",),
                "second_reference_pin_assignments": ("U1.4 (GND, power_in)=GND_A",),
                "shared_serial_pin_assignments": (
                    "UART_RX: J1.2 (UART1_TX, output) -> U1.2 (UART1_RX, input)",
                    "UART_TX: U1.1 (UART1_TX, output) -> J1.1 (UART1_RX, input)",
                ),
                "serial_peer_map_state": ("not_configured",),
            }
        ):
            raise ValueError("Native UART connector reference finding lost exact pin/net evidence")
        ctx.log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            source_sha256=ctx.serial_connector_reference_source_hashes[case],
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
