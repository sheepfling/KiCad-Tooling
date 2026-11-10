"""Synthetic inputs for reviewed connector power-input split regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
)
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
)
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract

NETLIST_SHA256 = "e" * 64
PEER_GROUP = "reviewed-synthetic-power-peers"
PEER_BASIS = "Synthetic USB and serial connector contacts were reviewed as peers"


def power_input_netlist(
    *,
    power_assignments: tuple[str | None, str | None] = ("USB_5V", "SERIAL_5V"),
    function: str = "Pin_1",
    functions: tuple[str, str] | None = None,
    electrical_type: str = "power_in",
    symbols: tuple[str, str] = ("Synthetic:UsbPort", "Synthetic:SerialPort"),
    values: tuple[str, str] = ("USB receptacle", "Serial connector"),
    footprints: tuple[str, str] = ("Synthetic:USB", "Synthetic:DB9"),
    part_ids: tuple[str | None, str | None] = (None, None),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build two unlike connector peers with configurable power-pin functions."""
    components = {
        reference: ComponentContract(value=value, footprint=footprint, part_id=part_id)
        for reference, value, footprint, part_id in zip(
            ("J1", "J2"), values, footprints, part_ids, strict=True
        )
    }
    nets: dict[str, tuple[str, ...]] = {"SYNTHETIC_COMMON": ("J1.2", "J2.2")}
    for reference, net in zip(("J1", "J2"), power_assignments, strict=True):
        if net is not None:
            nets[net] = (*nets.get(net, ()), f"{reference}.1")
    pin_functions = functions if functions is not None else (function, function)
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=dict(zip(("J1", "J2"), symbols, strict=True)),
        component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
        pin_functions={
            "J1.1": pin_functions[0],
            "J2.1": pin_functions[1],
            "J1.2": "Pin_2",
            "J2.2": "Pin_2",
        },
        pin_electrical_types={
            "J1.1": electrical_type,
            "J2.1": electrical_type,
            "J1.2": "passive",
            "J2.2": "passive",
        },
    )


def power_input_coverage(
    observed: NetlistContract,
    *,
    peer_groups: tuple[str | None, str | None] = (PEER_GROUP, PEER_GROUP),
    interface_signals: tuple[str, str] = ("POWER_INPUT", "POWER_INPUT"),
    voltage_domains: tuple[str, str] = ("external-5v", "external-5v"),
    roles: tuple[str | None, str | None] = (None, None),
    directions: tuple[str, str] = ("input", "input"),
    unconnected_pin_reasons: tuple[str | None, str | None] = (None, None),
    complete_maps: bool = True,
    inventory_reviewed: bool = True,
) -> ConnectorCoverageReport:
    """Create complete source-bound maps for two distinct interface records."""
    catalog, project_interfaces, reviews = power_input_project_documents(
        peer_groups=peer_groups,
        interface_signals=interface_signals,
        voltage_domains=voltage_domains,
        roles=roles,
        directions=directions,
        unconnected_pin_reasons=unconnected_pin_reasons,
        complete_maps=complete_maps,
    )
    return evaluate_connector_coverage(
        observed,
        project_interfaces,
        reviews,
        interfaces={item.id: item for item in catalog.interfaces},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="d" * 64,
        inventory_review=(
            ConnectorInventoryReview(basis="Synthetic complete connector inventory review")
            if inventory_reviewed
            else None
        ),
    )


def power_input_project_documents(
    *,
    peer_groups: tuple[str | None, str | None] = (PEER_GROUP, PEER_GROUP),
    interface_signals: tuple[str, str] = ("POWER_INPUT", "POWER_INPUT"),
    voltage_domains: tuple[str, str] = ("external-5v", "external-5v"),
    roles: tuple[str | None, str | None] = (None, None),
    directions: tuple[str, str] = ("input", "input"),
    unconnected_pin_reasons: tuple[str | None, str | None] = (None, None),
    complete_maps: bool = True,
) -> tuple[InterfacesCatalog, tuple[str, ...], tuple[ConnectorInterfaceReview, ...]]:
    """Return the synthetic shared catalog and per-connector pinout reviews."""
    interfaces: list[InterfaceRecord] = []
    reviews: list[ConnectorInterfaceReview] = []
    project_interfaces: list[str] = []
    for index, (
        reference,
        interface_id,
        peer_group,
        signal,
        domain,
        role,
        direction,
        open_reason,
    ) in enumerate(
        zip(
            ("J1", "J2"),
            ("usb-port", "serial-port"),
            peer_groups,
            interface_signals,
            voltage_domains,
            roles,
            directions,
            unconnected_pin_reasons,
            strict=True,
        ),
        start=1,
    ):
        interfaces.append(
            InterfaceRecord(
                id=interface_id,
                revision="synthetic-1",
                pins=(
                    InterfacePin(
                        number="1",
                        signal=signal,
                        role=role,
                        direction=direction,
                        voltage_domain=domain,
                        mating="synthetic fixture",
                        orientation="straight",
                        mechanical_clearance="synthetic",
                    ),
                    InterfacePin(
                        number="2",
                        signal=f"SIGNAL_{index}",
                        direction="bidirectional",
                        voltage_domain="logic-3v3",
                        mating="synthetic fixture",
                        orientation="straight",
                        mechanical_clearance="synthetic",
                    ),
                ),
            )
        )
        project_interfaces.append(interface_id)
        reviews.append(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                basis=f"Synthetic current pin map for {reference}",
                interface_id=interface_id,
                pin_map=({"1": "1", "2": "2"} if complete_maps else {"1": "1"}),
                peer_assignment_group=peer_group,
                peer_assignment_basis=None if peer_group is None else PEER_BASIS,
                unconnected_pin_reasons={} if open_reason is None else {"1": open_reason},
            )
        )
    return (
        InterfacesCatalog(schema_version="1", interfaces=tuple(interfaces)),
        tuple(project_interfaces),
        tuple(reviews),
    )


def lint_report(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    """Run the shared typed design-lint service on synthetic connector evidence."""
    project_id = "synthetic-reviewed-peer-power-input"
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        observed=observed,
        netlist_sha256=NETLIST_SHA256,
    )
    return evaluate_design_lint(
        project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )
