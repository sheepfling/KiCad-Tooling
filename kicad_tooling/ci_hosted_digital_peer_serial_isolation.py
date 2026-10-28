"""Verify that an optical UART boundary stays outside direct-peer review."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .ci_hosted_digital_peer_context import DigitalPeerFixtureContext
from .ci_hosted_digital_peer_models import DigitalPeerFixtureCase
from .ci_hosted_native_fixture_models import NativeRun, NativeRunPair
from .hwrepo.design_lint import evaluate
from .hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract

_CASE: DigitalPeerFixtureCase = "serial-optical-isolation-control"
_RULE_ID = "bus.serial_peer_reference_review"
_SIGNAL_PAIRS = (
    ("host_tx_to_isolator", ("U1.1", "U3.1")),
    ("isolator_to_target_rx", ("U3.3", "U2.1")),
    ("target_tx_to_isolator", ("U2.2", "U3.4")),
    ("isolator_to_host_rx", ("U3.2", "U1.2")),
)
_REFERENCE_ASSIGNMENTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "GND_DEVICE": ("U2.4", "U3.8"),
        "GND_HOST": ("U1.4", "U3.6"),
    }
)
_SUPPLY_ASSIGNMENTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "VDD_DEVICE": ("U2.3", "U3.7"),
        "VDD_HOST": ("U1.3", "U3.5"),
    }
)
_PIN_FUNCTIONS: Mapping[str, str] = MappingProxyType(
    {
        "U1.1": "UART1_TX",
        "U1.2": "UART1_RX",
        "U1.3": "VDD",
        "U1.4": "GND",
        "U2.1": "UART1_RX",
        "U2.2": "UART1_TX",
        "U2.3": "VDD",
        "U2.4": "GND",
        "U3.1": "CHANNEL_A_INPUT",
        "U3.2": "CHANNEL_A_OUTPUT",
        "U3.3": "CHANNEL_B_OUTPUT",
        "U3.4": "CHANNEL_B_INPUT",
        "U3.5": "VDD_HOST",
        "U3.6": "GND_HOST",
        "U3.7": "VDD_DEVICE",
        "U3.8": "GND_DEVICE",
    }
)
_PIN_TYPES: Mapping[str, str] = MappingProxyType(
    {
        "U1.1": "output",
        "U1.2": "input",
        "U1.3": "power_in",
        "U1.4": "power_in",
        "U2.1": "input",
        "U2.2": "output",
        "U2.3": "power_in",
        "U2.4": "power_in",
        "U3.1": "input",
        "U3.2": "output",
        "U3.3": "output",
        "U3.4": "input",
        "U3.5": "power_in",
        "U3.6": "power_in",
        "U3.7": "power_in",
        "U3.8": "power_in",
    }
)
_SYMBOLS: Mapping[str, str] = MappingProxyType(
    {
        "U1": "Synthetic:UartController",
        "U2": "Synthetic:UartTarget",
        "U3": "Synthetic:UartOpticalIsolator",
    }
)
_PIN_NUMBERS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "U1": ("1", "2", "3", "4"),
        "U2": ("1", "2", "3", "4"),
        "U3": ("1", "2", "3", "4", "5", "6", "7", "8"),
    }
)


def _net_for_pin(observed: NetlistContract, pin: str) -> str:
    matches = tuple(net for net, pins in observed.nets.items() if pin in pins)
    if len(matches) != 1:
        raise ValueError(f"Optical UART fixture pin {pin} has {len(matches)} assigned nets")
    return matches[0]


def _check_pin_assignments(
    observed: NetlistContract, expected: Mapping[str, tuple[str, ...]], *, label: str
) -> None:
    actual = {net: tuple(sorted(pins)) for net, pins in observed.nets.items() if net in expected}
    normalized_expected = {net: tuple(sorted(pins)) for net, pins in expected.items()}
    if actual != normalized_expected:
        raise ValueError(f"Native optical UART export changed its {label} assignments")


def verify_serial_isolation_boundary_control(ctx: DigitalPeerFixtureContext) -> None:
    """Check exact pins, split references, stable reports, and no direct-peer prompt."""
    project_id = "synthetic-optical-uart-boundary-control"
    observed = ctx.fixture(_CASE).netlists.first.contract
    if (
        ctx.fixture(_CASE).netlists.first.normalized_sha256
        != ctx.fixture(_CASE).netlists.repeat.normalized_sha256
    ):
        raise ValueError("Native optical UART repeated exports differ after normalization")
    if (
        observed.pin_functions != _PIN_FUNCTIONS
        or observed.pin_electrical_types != _PIN_TYPES
        or observed.component_symbols != _SYMBOLS
        or observed.component_pin_numbers != _PIN_NUMBERS
    ):
        raise ValueError("Native optical UART export lost its exact symbol and pin evidence")
    _check_pin_assignments(observed, _REFERENCE_ASSIGNMENTS, label="reference")
    _check_pin_assignments(observed, _SUPPLY_ASSIGNMENTS, label="supply")
    for role, pins in _SIGNAL_PAIRS:
        if _net_for_pin(observed, pins[0]) != _net_for_pin(observed, pins[1]):
            raise ValueError(f"Native optical UART export changed signal segment {role}")
    if _net_for_pin(observed, "U1.1") == _net_for_pin(observed, "U2.1"):
        raise ValueError("Native optical UART export shorted host and target signal domains")

    def report_for(run: NativeRun):
        return evaluate(
            project_id,
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=ctx.fixture(_CASE).netlists.for_run(run).contract,
                netlist_sha256=ctx.fixture(_CASE).netlists.for_run(run).netlist_sha256,
            ),
            DesignLintPolicy(),
        )

    reports = NativeRunPair(
        first=report_for("first"),
        repeat=report_for("repeat"),
    )
    signatures = NativeRunPair(
        first=tuple(
            sorted(
                (item.fingerprint, item.rule_id, item.mode, item.evidence)
                for item in reports.first.findings
            )
        ),
        repeat=tuple(
            sorted(
                (item.fingerprint, item.rule_id, item.mode, item.evidence)
                for item in reports.repeat.findings
            )
        ),
    )
    findings = tuple(item for item in reports.first.findings if item.rule_id == _RULE_ID)
    if signatures.first != signatures.repeat or findings:
        raise ValueError("Optical UART boundary must not produce a direct-peer reference review")

    ctx.log.event(
        f"spi-participant-fixture/{_CASE}",
        "PASS",
        project=ctx.project,
        kicad_version=ctx.config.kicad_version,
        image=ctx.pinned,
        source_sha256=ctx.fixture(_CASE).source.sha256,
        netlist_sha256=ctx.fixture(_CASE).netlists.first.netlist_sha256,
        repeat_netlist_sha256=ctx.fixture(_CASE).netlists.repeat.netlist_sha256,
        normalized_netlist_sha256=ctx.fixture(_CASE).netlists.first.normalized_sha256,
        repeat_normalized_netlist_sha256=ctx.fixture(_CASE).netlists.repeat.normalized_sha256,
        peer_reference_findings="none",
        reference_assignments=";".join(
            f"{net}={','.join(pins)}" for net, pins in sorted(_REFERENCE_ASSIGNMENTS.items())
        ),
        supply_assignments=";".join(
            f"{net}={','.join(pins)}" for net, pins in sorted(_SUPPLY_ASSIGNMENTS.items())
        ),
        isolated_signal_pin_pairs=";".join(
            f"{role}={','.join(pins)}" for role, pins in _SIGNAL_PAIRS
        ),
        pin_functions=";".join(
            f"{pin}={name}" for pin, name in sorted(observed.pin_functions.items())
        ),
        pin_types=";".join(
            f"{pin}={name}" for pin, name in sorted(observed.pin_electrical_types.items())
        ),
        repeatable="true",
        repeatability_basis="normalized_native_netlist_and_design_lint_report",
        command_receipt=(ctx.scratch / "native.command.json").relative_to(ctx.root).as_posix(),
    )
