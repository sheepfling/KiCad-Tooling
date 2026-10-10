"""Verify UART peer voltage and reference-domain cases."""

from __future__ import annotations

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .hwrepo.design_lint import evaluate
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)


def verify_serial_peer_voltage_cases(ctx: DigitalPeerFixtureContext) -> DesignLintPolicy:
    """Verify UART peer voltage and reference-domain cases."""
    serial_peer_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="power.ic_rail_without_fitted_capacitor",
                mode="off",
                reason="Isolate the synthetic serial peer-voltage fixture.",
            ),
        )
    )
    for case, expected_status in (
        ("serial-control", "PASS"),
        ("serial-fault", "REVIEW"),
        ("serial-reference-fault", "REVIEW"),
    ):
        peer_observed = ctx.contracts[case]["first"]
        if ctx.normalized_hashes[case]["first"] != ctx.normalized_hashes[case]["repeat"]:
            raise ValueError(f"Native UART {case} exports differ after typed-netlist normalization")
        expected_functions = {
            "U1.1": "UART1_TX",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "UART1_RX",
            "U2.2": "VDD",
            "U2.3": "GND",
        }
        expected_pin_types = {
            "U1.1": "output",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "input",
            "U2.2": "power_in",
            "U2.3": "power_in",
        }
        expected_symbols = {"U1": "Synthetic:UartTransmitter", "U2": "Synthetic:UartReceiver"}
        if peer_observed.pin_functions != expected_functions:
            raise ValueError(
                f"Native UART {case} export lost exact signal or supply functions: {peer_observed.pin_functions}"
            )
        if peer_observed.pin_electrical_types != expected_pin_types:
            raise ValueError(
                f"Native UART {case} export lost complete native pin types: {peer_observed.pin_electrical_types}"
            )
        if peer_observed.component_symbols != expected_symbols:
            raise ValueError(f"Native UART {case} export changed synthetic component identities")
        if peer_observed.component_pin_numbers != {"U1": ("1", "2", "3"), "U2": ("1", "2", "3")}:
            raise ValueError(
                f"Native UART {case} export changed complete component pin inventories"
            )
        expected_rails = (
            {"+3V3": ("U1.2", "U2.2")}
            if case in {"serial-control", "serial-reference-fault"}
            else {"+5V": ("U1.2",), "+3V3": ("U2.2",)}
        )
        if {
            net: pins for (net, pins) in peer_observed.nets.items() if net in {"+3V3", "+5V"}
        } != expected_rails:
            raise ValueError(f"Native UART {case} export changed exact supply assignments")
        expected_references = (
            {"GND": ("U1.3", "U2.3")}
            if case in {"serial-control", "serial-fault"}
            else {"GND_A": ("U1.3",), "GND_B": ("U2.3",)}
        )
        if {
            net: pins
            for (net, pins) in peer_observed.nets.items()
            if net in {"GND", "GND_A", "GND_B"}
        } != expected_references:
            raise ValueError(f"Native UART {case} export changed exact reference assignments")
        reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            report_coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-uart-peer-voltage-{case}",
                observed=ctx.contracts[case][run],
                netlist_sha256=ctx.hashes[case][run],
            )
            reports[run] = evaluate(report_coach.project_id, report_coach, serial_peer_policy)
        findings = tuple(
            item
            for item in reports["first"].findings
            if item.rule_id == "bus.serial_peer_voltage_review"
        )
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
        if (
            reports["first"].status != expected_status
            or reports["repeat"].status != expected_status
            or first_signature != repeated_signature
            or (case in {"serial-control", "serial-reference-fault"} and findings)
            or (case == "serial-fault" and len(findings) != 1)
            or (case in {"serial-control", "serial-fault"} and reference_findings)
            or (case == "serial-reference-fault" and len(reference_findings) != 1)
        ):
            raise ValueError(f"Native UART {case} no longer matches its peer-review cases")
        if findings and (
            findings[0].mode != "review"
            or dict(findings[0].evidence)
            != {
                "authored_voltage_map_state": ("not_configured",),
                "input_component": ("U2",),
                "input_supply_label_value": ("3.3 V",),
                "input_supply_net": ("+3V3",),
                "output_component": ("U1",),
                "output_supply_label_value": ("5 V",),
                "output_supply_net": ("+5V",),
                "shared_serial_pin_assignments": (
                    "UART_TX: U1.1 (UART1_TX, output) -> U2.1 (UART1_RX, input)",
                ),
            }
        ):
            raise ValueError("Native UART peer-voltage finding lost exact review evidence")
        if reference_findings and (
            reference_findings[0].mode != "review"
            or dict(reference_findings[0].evidence)
            != {
                "first_component": ("U1",),
                "first_reference_net": ("GND_A",),
                "first_reference_pin_assignments": ("U1.3 (GND, power_in)=GND_A",),
                "second_component": ("U2",),
                "second_reference_net": ("GND_B",),
                "second_reference_pin_assignments": ("U2.3 (GND, power_in)=GND_B",),
                "shared_serial_pin_assignments": (
                    "UART_TX: U1.1 (UART1_TX, output) -> U2.1 (UART1_RX, input)",
                ),
                "serial_peer_map_state": ("not_configured",),
            }
        ):
            raise ValueError("Native UART peer-reference finding lost exact pin/net evidence")
        ctx.log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            source_sha256=ctx.serial_peer_source_hashes[case],
            netlist_sha256=ctx.hashes[case]["first"],
            repeat_netlist_sha256=ctx.hashes[case]["repeat"],
            normalized_netlist_sha256=ctx.normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=ctx.normalized_hashes[case]["repeat"],
            lint_status=reports["first"].status,
            peer_voltage_findings=";".join(item.rule_id for item in findings) or "none",
            peer_reference_findings=";".join(item.rule_id for item in reference_findings) or "none",
            pin_functions=";".join(
                f"{pin}={name}" for (pin, name) in sorted(peer_observed.pin_functions.items())
            ),
            pin_types=";".join(
                f"{pin}={name}"
                for (pin, name) in sorted(peer_observed.pin_electrical_types.items())
            ),
            rail_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_rails)
            ),
            reference_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_references)
            ),
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )
    return serial_peer_policy
