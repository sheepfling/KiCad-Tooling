"""Verify peer voltage fault, direct control, and translator control cases."""

from __future__ import annotations

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .hwrepo.design_lint import evaluate
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)


def verify_spi_peer_voltage_cases(ctx: DigitalPeerFixtureContext) -> None:
    """Verify peer voltage fault, direct control, and translator control cases."""
    peer_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="bus.spi_unmapped_participant",
                mode="off",
                reason="Isolate the synthetic peer-voltage native fixture.",
            ),
            DesignLintRuleOverride(
                rule_id="power.ic_rail_without_fitted_capacitor",
                mode="off",
                reason="Isolate peer-domain review from decoupling coverage.",
            ),
        )
    )
    for case, expected_status in (
        ("peer-control", "PASS"),
        ("peer-fault", "REVIEW"),
        ("peer-translator-control", "PASS"),
    ):
        peer_contracts = ctx.contracts[case]
        peer_observed = peer_contracts["first"]
        if ctx.normalized_hashes[case]["first"] != ctx.normalized_hashes[case]["repeat"]:
            raise ValueError(f"Native SPI {case} exports differ after typed-netlist normalization")
        if case == "peer-translator-control":
            expected_pin_functions = {
                "U1.1": "SPI1_SCLK",
                "U1.2": "VDD",
                "U1.3": "GND",
                "U2.1": "SPI1_SCLK",
                "U2.2": "VDD",
                "U2.3": "GND",
                "U3.1": "A_SCLK",
                "U3.2": "B_SCLK",
                "U3.3": "VCCA",
                "U3.4": "VCCB",
                "U3.5": "GND",
            }
            expected_pin_types = {
                "U1.1": "output",
                "U1.2": "power_in",
                "U1.3": "power_in",
                "U2.1": "input",
                "U2.2": "power_in",
                "U2.3": "power_in",
                "U3.1": "input",
                "U3.2": "output",
                "U3.3": "power_in",
                "U3.4": "power_in",
                "U3.5": "power_in",
            }
            expected_symbols = {
                "U1": "Synthetic:SPI_Controller",
                "U2": "Synthetic:SPI_Peripheral",
                "U3": "Synthetic:SPI_LevelTranslator",
            }
            expected_pin_numbers = {
                "U1": ("1", "2", "3"),
                "U2": ("1", "2", "3"),
                "U3": ("1", "2", "3", "4", "5"),
            }
        else:
            expected_pin_functions = {
                "U1.1": "SPI1_SCLK",
                "U1.2": "VDD",
                "U2.1": "SPI1_SCLK",
                "U2.2": "VDD",
            }
            expected_pin_types = {
                "U1.1": "output",
                "U1.2": "power_in",
                "U2.1": "input",
                "U2.2": "power_in",
            }
            expected_symbols = {"U1": "Synthetic:SPI_Controller", "U2": "Synthetic:SPI_Peripheral"}
            expected_pin_numbers = {"U1": ("1", "2"), "U2": ("1", "2")}
        if peer_observed.pin_functions != expected_pin_functions:
            raise ValueError(
                f"Native SPI {case} export lost the exact signal and supply pin functions: {peer_observed.pin_functions}"
            )
        if peer_observed.pin_electrical_types != expected_pin_types:
            raise ValueError(
                f"Native SPI {case} export lost the complete pin-type inventory: {peer_observed.pin_electrical_types}"
            )
        if peer_observed.component_symbols != expected_symbols:
            raise ValueError(f"Native SPI {case} export changed synthetic component identities")
        if peer_observed.component_pin_numbers != expected_pin_numbers:
            raise ValueError(f"Native SPI {case} export changed the full component pin inventory")
        expected_rails = (
            {"+3V3": ("U2.2", "U3.4"), "+5V": ("U1.2", "U3.3")}
            if case == "peer-translator-control"
            else {"+3V3": ("U1.2", "U2.2")}
            if case == "peer-control"
            else {"+3V3": ("U2.2",), "+5V": ("U1.2",)}
        )
        if {
            net: pins for (net, pins) in peer_observed.nets.items() if net in {"+3V3", "+5V"}
        } != expected_rails:
            raise ValueError(f"Native SPI {case} export changed its synthetic supply assignments")
        expected_signal_nets: dict[str, tuple[str, ...]] = {}
        if case == "peer-translator-control":
            expected_signal_nets = {"SPI_A_SIDE": ("U1.1", "U3.1"), "SPI_B_SIDE": ("U2.1", "U3.2")}
            observed_signal_nets = {
                net: pins for (net, pins) in peer_observed.nets.items() if net.startswith("SPI_")
            }
            if observed_signal_nets != expected_signal_nets:
                raise ValueError(
                    "Native SPI translator control no longer separates its A- and B-side nets"
                )
        peer_reports: dict[str, DesignLintReport] = {}
        for run in ("first", "repeat"):
            report_coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-spi-peer-voltage-{case}",
                observed=peer_contracts[run],
                netlist_sha256=ctx.hashes[case][run],
            )
            peer_reports[run] = evaluate(report_coach.project_id, report_coach, peer_policy)
        findings = tuple(
            item
            for item in peer_reports["first"].findings
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        repeated_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in peer_reports["repeat"].findings
        )
        first_findings = tuple(
            (item.fingerprint, item.rule_id, item.mode, item.evidence)
            for item in peer_reports["first"].findings
        )
        if (
            peer_reports["first"].status != expected_status
            or peer_reports["repeat"].status != expected_status
            or first_findings != repeated_findings
            or (case == "peer-control" and findings)
            or (case == "peer-fault" and len(findings) != 1)
        ):
            raise ValueError(f"Native SPI {case} no longer matches its peer-voltage review case")
        if findings and findings[0].mode != "review":
            raise ValueError("SPI peer-voltage heuristic no longer defaults to REVIEW")
        if case == "peer-fault" and dict(findings[0].evidence) != {
            "authored_voltage_map_state": ("not_configured",),
            "input_component": ("U2",),
            "input_supply_label_value": ("3.3 V",),
            "input_supply_net": ("+3V3",),
            "output_component": ("U1",),
            "output_supply_label_value": ("5 V",),
            "output_supply_net": ("+5V",),
            "shared_SPI_pin_assignments": (
                "SPI_SCK: U1.1 (SPI1_SCLK, output) -> U2.1 (SPI1_SCLK, input)",
            ),
        }:
            raise ValueError("Native SPI peer-voltage finding lost exact rail or pin evidence")
        ctx.log.event(
            f"spi-participant-fixture/{case}",
            "PASS",
            project=ctx.project,
            kicad_version=ctx.config.kicad_version,
            image=ctx.pinned,
            source_sha256=ctx.peer_source_hashes[case],
            netlist_sha256=ctx.hashes[case]["first"],
            repeat_netlist_sha256=ctx.hashes[case]["repeat"],
            normalized_netlist_sha256=ctx.normalized_hashes[case]["first"],
            repeat_normalized_netlist_sha256=ctx.normalized_hashes[case]["repeat"],
            lint_status=peer_reports["first"].status,
            peer_voltage_findings=";".join(item.rule_id for item in findings) or "none",
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
            signal_assignments=";".join(
                f"{net}={','.join(peer_observed.nets[net])}" for net in sorted(expected_signal_nets)
            )
            or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_design_lint_report",
            command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
        )
