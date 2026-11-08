"""Synthetic exact-symbol connector peers with numeric-only pin functions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def numeric_open_connector_peers(
    *,
    references: tuple[str, ...] = ("J1", "J2", "J3"),
    open_references: tuple[str, ...] = ("J3",),
    dnp_references: tuple[str, ...] = (),
    anchor_nets: tuple[str, ...] | None = None,
) -> NetlistContract:
    """Build full-inventory peers, one common anchor, and a numeric open outlier."""
    anchor_nets = anchor_nets or ("+3V3",) * len(references)
    nets: dict[str, tuple[str, ...]] = {}
    for reference, net in zip(references, anchor_nets, strict=True):
        nets[net] = (*nets.get(net, ()), f"{reference}.1")
    connected_targets = tuple(
        reference for reference in references if reference not in open_references
    )
    if connected_targets:
        nets["GND"] = tuple(f"{reference}.2" for reference in connected_targets)
    for index, reference in enumerate(references, start=1):
        nets[f"PORT_{index}"] = (f"{reference}.3",)
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="Conn_01x03",
                footprint="Connector_Generic:Conn_01x03",
            )
            for reference in references
        },
        nets=nets,
        dnp_components=dnp_references,
        component_symbols={reference: "Connector_Generic:Conn_01x03" for reference in references},
        component_pin_numbers={reference: ("1", "2", "3") for reference in references},
        pin_functions={
            f"{reference}.{number}": number
            for reference in references
            for number in ("1", "2", "3")
        },
        pin_electrical_types={
            f"{reference}.{number}": "passive"
            for reference in references
            for number in ("1", "2", "3")
        },
    )


def numeric_open_connector_part_id_aliases(
    *,
    open_references: tuple[str, ...] = ("J3",),
    part_ids: tuple[str | None, ...] = ("SYNTHETIC-CONNECTOR-PEER",) * 3,
    anchor_nets: tuple[str, ...] = ("+3V3",) * 3,
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build numeric-only aliases whose shared PART_ID spans two symbols."""
    references = ("J1", "J2", "J3")
    source = numeric_open_connector_peers(
        references=references,
        open_references=open_references,
        anchor_nets=anchor_nets,
        dnp_references=dnp_references,
    )
    components = {
        reference: source.components[reference].model_copy(update={"part_id": part_id})
        for reference, part_id in zip(references, part_ids, strict=True)
    }
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": {
                "J1": "Connector_Alias_A",
                "J2": "Connector_Alias_A",
                "J3": "Connector_Alias_B",
            },
        }
    )
