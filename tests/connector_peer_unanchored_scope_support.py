"""Shared reviewed-map fixture for unanchored connector peer-scope tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.connector_coverage_models import ConnectorCoverageReport
from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    InterfacePin,
    InterfaceRecord,
)
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract
from tests.connector_footprint_peer_support import NETLIST_SHA256

PEER_GROUP = "synthetic-peer-connectors"
PEER_BASIS = "Synthetic connector pinouts were reviewed as one peer set"


def reviewed_coverage(
    observed: NetlistContract,
    groups: tuple[str | None, ...] | None = None,
    *,
    inventory_reviewed: bool = True,
    pin_maps_complete: bool = True,
) -> ConnectorCoverageReport:
    """Build complete source-matched two-pin maps with configurable peer scope."""
    references = tuple(sorted(observed.components, key=lambda value: (value.casefold(), value)))
    peer_groups = (PEER_GROUP,) * len(references) if groups is None else groups
    if len(peer_groups) != len(references):
        raise ValueError("Synthetic peer groups must match the observed connector references")
    interface = InterfaceRecord(
        id="synthetic-generic-port",
        revision="synthetic-1",
        pins=tuple(
            InterfacePin(
                number=str(number),
                signal=f"contact-{number}",
                direction="bidirectional",
                voltage_domain="synthetic-domain",
                mating="synthetic peer",
                orientation="straight",
                mechanical_clearance="synthetic",
            )
            for number in (1, 2)
        ),
    )
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis="Synthetic exact pin mapping",
            interface_id="synthetic-generic-port",
            pin_map=({"1": "1", "2": "2"} if pin_maps_complete else {"1": "1"}),
            peer_assignment_group=group,
            peer_assignment_basis=None if group is None else PEER_BASIS,
        )
        for reference, group in zip(references, peer_groups, strict=True)
    )
    return evaluate_connector_coverage(
        observed,
        ("synthetic-generic-port",),
        reviews,
        interfaces={"synthetic-generic-port": interface},
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="f" * 64,
        inventory_review=(
            ConnectorInventoryReview(basis="Synthetic connector inventory was reviewed")
            if inventory_reviewed
            else None
        ),
    )


def three_peer_partial_open_netlist(
    *, common_anchor: bool = False, assigned_peers_agree: bool = False
) -> NetlistContract:
    """Build two divergent generic pins with a third alias left open."""
    references = ("J1", "J2", "J3")
    components = {
        reference: ComponentContract(
            value="Synthetic two-contact connector", footprint="Synthetic:Connector_2x1"
        )
        for reference in references
    }
    component_symbols = {
        reference: f"Synthetic:GenericPortAlias{index}"
        for index, reference in enumerate(references, start=1)
    }
    pin_numbers = {reference: ("1", "2") for reference in references}
    pin_functions = {
        f"{reference}.{number}": f"Pin_{number}"
        for reference in references
        for number in pin_numbers[reference]
    }
    nets: dict[str, tuple[str, ...]] = {}
    for number, assignments in (
        (
            "1",
            ("SHARED_RETURN",) * 3
            if common_anchor
            else ("PORT_A", "PORT_A" if assigned_peers_agree else "PORT_B", None),
        ),
        ("2", ("DATA_A", "DATA_A" if assigned_peers_agree else "DATA_B", None)),
    ):
        for reference, net in zip(references, assignments, strict=True):
            if net is not None:
                nets[net] = (*nets.get(net, ()), f"{reference}.{number}")
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=component_symbols,
        component_pin_numbers=pin_numbers,
        pin_functions=pin_functions,
        pin_electrical_types={pin: "passive" for pin in pin_functions},
    )


def lint_report(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None = None,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    """Run the common typed lint service against a synthetic connector netlist."""
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-peer-unanchored-assignment",
        observed=observed,
        netlist_sha256=NETLIST_SHA256,
    )
    return evaluate_design_lint(
        coach.project_id,
        coach,
        policy or DesignLintPolicy(),
        connector_coverage=coverage,
    )


def four_peer_alias_netlist(*, common_net_anchor: bool) -> NetlistContract:
    """Build a synthetic four-connector alias split or common-net control."""
    references = ("J1", "J2", "J3", "J4")
    components = {
        reference: ComponentContract(
            value="Synthetic two-contact port", footprint="Synthetic:Port_2x1"
        )
        for reference in references
    }
    component_symbols = {
        reference: f"Synthetic:GenericPortAlias{index}"
        for index, reference in enumerate(references, start=1)
    }
    component_pin_numbers = {reference: ("1", "2") for reference in references}
    pin_functions = {
        f"{reference}.{number}": f"Pin_{number}"
        for reference in references
        for number in ("1", "2")
    }
    pin_electrical_types = {pin: "passive" for pin in pin_functions}
    if common_net_anchor:
        nets: dict[str, tuple[str, ...]] = {
            "SYNTHETIC_COMMON": tuple(f"{reference}.1" for reference in references)
        }
    else:
        nets = {
            f"SYNTHETIC_NET_{index}": (f"{reference}.1",)
            for index, reference in enumerate(references, start=1)
        }
    nets.update(
        {
            f"SYNTHETIC_DATA_{index}": (f"{reference}.2",)
            for index, reference in enumerate(references, start=1)
        }
    )
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=component_symbols,
        component_pin_numbers=component_pin_numbers,
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
    )
