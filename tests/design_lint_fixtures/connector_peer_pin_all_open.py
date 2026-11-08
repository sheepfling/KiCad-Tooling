"""Synthetic netlists for generic all-open connector peer-pin checks."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintRuleOverride,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)

_REFERENCES = ("J1", "J2", "J3")


def generic_open_peer_netlist(
    *,
    references: tuple[str, ...] = _REFERENCES,
    open_pin_assignments: bool = True,
    anchor_nets: tuple[str, ...] | None = None,
    dnp_references: tuple[str, ...] = (),
    target_pin_type: str = "passive",
) -> NetlistContract:
    """Create exact-symbol peers with an optional all-open target contact."""
    anchor_nets = anchor_nets or ("+5V",) * len(references)
    nets: dict[str, tuple[str, ...]] = {}
    for reference, net in zip(references, anchor_nets, strict=True):
        nets[net] = (*nets.get(net, ()), f"{reference}.1")
    if not open_pin_assignments:
        nets["GND"] = tuple(f"{reference}.2" for reference in references)
    symbol = "Lint:PassiveGenericPort" if target_pin_type == "passive" else "Lint:GenericSignalPort"
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic peer port", footprint="")
            for reference in references
        },
        nets=nets,
        dnp_components=dnp_references,
        component_symbols={reference: symbol for reference in references},
        component_pin_numbers={reference: ("1", "2") for reference in references},
        pin_functions={
            f"{reference}.{number}": f"Pin_{number}"
            for reference in references
            for number in ("1", "2")
        },
        pin_electrical_types={
            f"{reference}.{number}": ("passive" if number == "1" else target_pin_type)
            for reference in references
            for number in ("1", "2")
        },
    )


def generic_open_part_id_peer_netlist(
    *,
    references: tuple[str, ...] = ("J1", "J2", "J3", "J4"),
    symbols: Mapping[str, str] | None = None,
    target_pin_type: str = "passive",
    anchor_nets: tuple[str, ...] | None = None,
) -> NetlistContract:
    """Create cross-symbol peers with one guarded native PART_ID."""
    left_symbol_count = max(1, (len(references) + 1) // 2)
    symbol_prefix = (
        "Lint:PassiveGenericPort" if target_pin_type == "passive" else "Lint:GenericSignalPort"
    )
    symbols = symbols or {
        reference: f"{symbol_prefix}Left" if index < left_symbol_count else f"{symbol_prefix}Right"
        for index, reference in enumerate(references)
    }
    source = generic_open_peer_netlist(
        references=references,
        anchor_nets=anchor_nets,
        target_pin_type=target_pin_type,
    )
    return source.model_copy(
        update={
            "components": {
                reference: ComponentContract(
                    value="Synthetic peer port",
                    footprint="Synthetic:GenericPeerPort",
                    part_id=(
                        "SYNTHETIC-PASSIVE-PORT-001"
                        if target_pin_type == "passive"
                        else "SYNTHETIC-GENERIC-SIGNAL-001"
                    ),
                )
                for reference in references
            },
            "component_symbols": symbols,
        }
    )


def generic_open_peer_coverage(
    observed: NetlistContract,
    *,
    groups: tuple[str, ...],
) -> ConnectorCoverageReport:
    """Build current connector-map evidence for generic peer-pin tests."""
    references = tuple(observed.component_symbols)
    if len(references) != len(groups):
        raise ValueError("Each synthetic connector needs one peer-assignment group")
    interface_ids = tuple(f"synthetic-port-{index}" for index in range(len(references)))
    interfaces = {
        interface_id: InterfaceRecord(
            id=interface_id,
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal="GND",
                    role="return",
                    direction="passive",
                    voltage_domain="signal-return",
                    mating="GND",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="2",
                    signal="AUX",
                    role="signal",
                    direction="bidirectional",
                    voltage_domain="logic-signal",
                    mating="AUX",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        )
        for interface_id in interface_ids
    }
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis=f"Reviewed synthetic interface {interface_id}",
            interface_id=interface_id,
            pin_map={"1": "1", "2": "2"},
            peer_assignment_group=group,
            peer_assignment_basis=f"Reviewed {reference} in peer group {group}",
        )
        for reference, interface_id, group in zip(
            references, interface_ids, groups, strict=True
        )
    )
    return evaluate_connector_coverage(
        observed,
        interface_ids,
        reviews,
        interfaces=interfaces,
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="a" * 64,
        inventory_review=ConnectorInventoryReview(
            basis="Reviewed all synthetic connector inventory entries"
        ),
    )


def review_generic_peer_pin_policy() -> DesignLintPolicy:
    """Enable the default-off all-open peer review in a synthetic project."""
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="connector.generic_peer_pin_all_open",
                mode="review",
                reason="Synthetic project asks reviewers to disposition all-open generic peer contacts",
            ),
        )
    )
