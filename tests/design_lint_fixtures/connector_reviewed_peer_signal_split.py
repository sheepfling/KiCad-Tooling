"""Synthetic reviewed connector peers with generic split signal contacts."""

from __future__ import annotations

from hashlib import sha256
from typing import TypeAlias

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
)
from kicad_tooling.hwrepo.connector_peer_pin_models import ConnectorPinRole
from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    NetlistContract,
)

PeerPair: TypeAlias = tuple[str, str]
INTERFACE_CATALOG_PATH = "catalog/interfaces.json"
PEER_REFERENCES = ("J1", "J2")
PEER_PINS = ("J1.2", "J2.7")


def peer_signal_netlist(
    *,
    nets: PeerPair = ("USB_RX_NET", "SERIAL_RX_NET"),
    symbols: PeerPair = ("Synthetic:UsbPort", "Synthetic:SerialPort"),
    functions: PeerPair = ("2", "7"),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Return a two-connector source with independently assigned signal nets."""
    pins_by_net: dict[str, list[str]] = {}
    for pin, net in zip(PEER_PINS, nets, strict=True):
        pins_by_net.setdefault(net, []).append(pin)
    return NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic USB port", footprint="Synthetic:USB"),
            "J2": ComponentContract(value="Synthetic serial port", footprint="Synthetic:DB9"),
        },
        nets={name: tuple(pins) for name, pins in pins_by_net.items()},
        dnp_components=dnp,
        component_symbols=dict(zip(PEER_REFERENCES, symbols, strict=True)),
        component_pin_numbers={"J1": ("2",), "J2": ("7",)},
        pin_functions=dict(zip(PEER_PINS, functions, strict=True)),
        pin_electrical_types={pin: "passive" for pin in PEER_PINS},
    )


def peer_signal_coverage(
    observed: NetlistContract,
    *,
    signals: PeerPair = ("UART_RX", "UART_RX"),
    voltage_domains: PeerPair = ("logic-3v3", "logic-3v3"),
    peer_groups: PeerPair = ("serial-peers", "serial-peers"),
    roles: tuple[ConnectorPinRole, ConnectorPinRole] = ("signal", "signal"),
    peer_bases: PeerPair = (
        "Synthetic USB and serial connectors are reviewed peers",
        "Synthetic USB and serial connectors are reviewed peers",
    ),
) -> ConnectorCoverageReport:
    """Build complete, source-matched maps for the two synthetic connectors."""
    interfaces_by_key: dict[tuple[str, str], InterfaceRecord] = {}
    reviews: list[ConnectorInterfaceReview] = []
    for index, reference in enumerate(PEER_REFERENCES):
        signal = signals[index]
        domain = voltage_domains[index]
        role = roles[index]
        interface_key = (signal.casefold(), domain.casefold())
        interface = interfaces_by_key.get(interface_key)
        if interface is None:
            interface_id = f"synthetic-peer-interface-{len(interfaces_by_key) + 1}"
            interface = InterfaceRecord(
                id=interface_id,
                revision="synthetic-1",
                pins=(
                    InterfacePin(
                        number="1",
                        signal=signal,
                        role=role,
                        direction="input" if role == "signal" else "passive",
                        voltage_domain=domain,
                        mating=signal,
                        orientation="straight",
                        mechanical_clearance="synthetic",
                    ),
                ),
            )
            interfaces_by_key[interface_key] = interface
        reviews.append(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                basis=f"Synthetic reviewed pinout for {reference}",
                interface_id=interface.id,
                pin_map={"1": PEER_PINS[index].split(".", 1)[1]},
                peer_assignment_group=peer_groups[index],
                peer_assignment_basis=peer_bases[index],
            )
        )

    interfaces = tuple(interfaces_by_key.values())
    catalog = InterfacesCatalog(schema_version="1", interfaces=interfaces)
    catalog_sha256 = sha256(model_json_bytes(catalog)).hexdigest()
    return evaluate_connector_coverage(
        observed,
        tuple(interface.id for interface in interfaces),
        tuple(reviews),
        interfaces={interface.id: interface for interface in catalog.interfaces},
        interface_catalog_path=INTERFACE_CATALOG_PATH,
        interface_catalog_sha256=catalog_sha256,
        inventory_review=ConnectorInventoryReview(
            basis="Synthetic review covered the complete connector inventory"
        ),
    )


def peer_signal_report(
    observed: NetlistContract,
    *,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    """Evaluate source and maps through the typed design-lint service."""
    current_coverage = coverage or peer_signal_coverage(observed)
    project_id = "synthetic-reviewed-peer-signal-split"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        observed=observed,
        netlist_sha256=sha256(model_json_bytes(observed)).hexdigest(),
    )
    return evaluate_design_lint(
        project_id,
        coach,
        policy if policy is not None else DesignLintPolicy(),
        connector_coverage=current_coverage,
    )
