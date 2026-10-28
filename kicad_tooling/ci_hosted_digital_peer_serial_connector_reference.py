"""Verify connector-level serial reference-domain review cases."""

from __future__ import annotations

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .ci_hosted_digital_peer_models import (
    SERIAL_CONNECTOR_REVIEW_CASES,
    DigitalPeerFixtureCase,
)
from .ci_hosted_native_fixture_models import NativeRun, NativeRunPair
from .ci_hosted_support import tooling_checkout_root
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_connectivity_snapshot import capture_connectivity_snapshot
from .hwrepo.design_lint_connectivity_snapshot_models import (
    DesignLintConnectivitySnapshot,
    NativePinMetadata,
)
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
)


def _connectivity_snapshot(
    ctx: DigitalPeerFixtureContext, case: DigitalPeerFixtureCase, run: NativeRun
) -> DesignLintConnectivitySnapshot:
    """Capture pin-role metadata from one exact-version native export."""
    source_path = ctx.fixture(case).source.path
    source_key = source_path.relative_to(tooling_checkout_root()).as_posix()
    return capture_connectivity_snapshot(
        project_id="serial-reference-fixture",
        observed=ctx.fixture(case).netlists.for_run(run).contract,
        source_hashes={source_key: ctx.fixture(case).source.sha256},
        netlist_sha256=ctx.fixture(case).netlists.for_run(run).netlist_sha256,
        kicad_version=ctx.config.kicad_version,
        toolchain_image=ctx.pinned,
    )


def verify_serial_connector_reference_cases(
    ctx: DigitalPeerFixtureContext, serial_peer_policy: DesignLintPolicy
):
    """Verify connector-level serial reference-domain review cases."""
    for case in SERIAL_CONNECTOR_REVIEW_CASES:
        peer_contracts = ctx.fixture(case).netlists
        peer_observed = peer_contracts.first.contract
        if (
            ctx.fixture(case).netlists.first.normalized_sha256
            != ctx.fixture(case).netlists.repeat.normalized_sha256
        ):
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
        expected_pin_metadata = {
            pin: NativePinMetadata(function=function, electrical_type=expected_pin_types[pin])
            for pin, function in expected_functions.items()
        }
        snapshot = _connectivity_snapshot(ctx, case, "first")
        repeated_snapshot = _connectivity_snapshot(ctx, case, "repeat")
        if (
            snapshot.schema_version != "2"
            or snapshot.coverage != "COMPLETE"
            or snapshot.pin_metadata_coverage != "COMPLETE"
            or dict(snapshot.pin_metadata) != expected_pin_metadata
            or dict(repeated_snapshot.pin_metadata) != expected_pin_metadata
            or snapshot.pin_states != repeated_snapshot.pin_states
        ):
            raise ValueError(
                f"Native UART {case} export did not retain repeatable complete pin-role metadata"
            )
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

        def report_for(run: NativeRun, fixture_case: DigitalPeerFixtureCase) -> DesignLintReport:
            report_coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-uart-connector-reference-{fixture_case}",
                observed=ctx.fixture(fixture_case).netlists.for_run(run).contract,
                netlist_sha256=ctx.fixture(fixture_case).netlists.for_run(run).netlist_sha256,
            )
            return evaluate(report_coach.project_id, report_coach, serial_peer_policy)

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
        expected_reference_count = 0 if case == "serial-connector-control" else 1
        if (
            first_signature != repeated_signature
            or reports.first.status != "REVIEW"
            or reports.repeat.status != "REVIEW"
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
            connectivity_snapshot_schema_version=snapshot.schema_version,
            pin_metadata_coverage=snapshot.pin_metadata_coverage,
            pin_role_metadata=";".join(
                f"{pin}={metadata.function}/{metadata.electrical_type}"
                for pin, metadata in sorted(snapshot.pin_metadata.items())
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
