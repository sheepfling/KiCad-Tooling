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

PeerList: TypeAlias = tuple[str, ...]
PeerGroupList: TypeAlias = tuple[str | None, ...]
OpenReasonList: TypeAlias = tuple[str | None, ...]
INTERFACE_CATALOG_PATH = "catalog/interfaces.json"
PEER_REFERENCES = ("J1", "J2")
PEER_PINS = ("J1.2", "J2.7")


def peer_signal_netlist(
    *,
    nets: PeerList = ("USB_RX_NET", "SERIAL_RX_NET"),
    symbols: PeerList = ("Synthetic:UsbPort", "Synthetic:SerialPort"),
    functions: PeerList = ("2", "7"),
    dnp: tuple[str, ...] = (),
    open_pins: tuple[str, ...] = (),
    references: PeerList = PEER_REFERENCES,
    pins: PeerList = PEER_PINS,
) -> NetlistContract:
    """Return synthetic generic signal contacts with independent net assignments."""
    pins_by_net: dict[str, list[str]] = {}
    for pin, net in zip(pins, nets, strict=True):
        if pin not in open_pins:
            pins_by_net.setdefault(net, []).append(pin)
    values = {"J1": "Synthetic USB port", "J2": "Synthetic serial port"}
    footprints = {"J1": "Synthetic:USB", "J2": "Synthetic:DB9"}
    return NetlistContract(
        components={
            reference: ComponentContract(
                value=values.get(reference, f"Synthetic connector {reference}"),
                footprint=footprints.get(reference, "Synthetic:Connector"),
            )
            for reference in references
        },
        nets={name: tuple(pins) for name, pins in pins_by_net.items()},
        dnp_components=dnp,
        component_symbols=dict(zip(references, symbols, strict=True)),
        component_pin_numbers={
            reference: (pin.rsplit(".", maxsplit=1)[1],)
            for reference, pin in zip(references, pins, strict=True)
        },
        pin_functions=dict(zip(pins, functions, strict=True)),
        pin_electrical_types={pin: "passive" for pin in pins},
    )


def peer_signal_coverage(
    observed: NetlistContract,
    *,
    signals: PeerList | None = None,
    voltage_domains: PeerList | None = None,
    peer_groups: PeerGroupList | None = None,
    roles: tuple[ConnectorPinRole, ...] | None = None,
    unconnected_reasons: OpenReasonList | None = None,
    peer_bases: PeerList | None = None,
    references: PeerList = PEER_REFERENCES,
    pins: PeerList = PEER_PINS,
) -> ConnectorCoverageReport:
    """Build complete, source-matched maps for the synthetic connectors."""
    signal_values = signals if signals is not None else ("UART_RX",) * len(references)
    domain_values = (
        voltage_domains if voltage_domains is not None else ("logic-3v3",) * len(references)
    )
    group_values = peer_groups if peer_groups is not None else ("serial-peers",) * len(references)
    role_values = roles if roles is not None else ("signal",) * len(references)
    reason_values = (
        unconnected_reasons if unconnected_reasons is not None else (None,) * len(references)
    )
    basis_values = (
        peer_bases
        if peer_bases is not None
        else ("Synthetic reviewed connectors belong to one peer group",) * len(references)
    )
    configurations = tuple(
        zip(
            references,
            pins,
            signal_values,
            domain_values,
            group_values,
            role_values,
            reason_values,
            basis_values,
            strict=True,
        )
    )
    interfaces_by_key: dict[tuple[str, str], InterfaceRecord] = {}
    reviews: list[ConnectorInterfaceReview] = []
    for (
        reference,
        pin,
        signal,
        domain,
        peer_group,
        role,
        unconnected_reason,
        peer_basis,
    ) in configurations:
        interface_key = (signal, domain)
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
                pin_map={"1": pin.split(".", 1)[1]},
                peer_assignment_group=peer_group,
                peer_assignment_basis=peer_basis if peer_group is not None else None,
                unconnected_pin_reasons=(
                    {} if unconnected_reason is None else {pin.split(".", 1)[1]: unconnected_reason}
                ),
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
