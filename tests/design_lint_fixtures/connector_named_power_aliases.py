"""Synthetic netlists for named connector power-pin alias regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def named_connector_power_alias_netlist(
    *,
    assignments: tuple[str | None, str | None] = ("SYNTHETIC_BIAS", None),
    symbols: tuple[str, str] = ("Synthetic:PortA", "Synthetic:PortB"),
    part_ids: tuple[str | None, str | None] = (
        "SYNTHETIC-NAMED-INPUT-001",
        "SYNTHETIC-NAMED-INPUT-001",
    ),
    values: tuple[str, str] = ("Synthetic peer", "Synthetic peer"),
    footprints: tuple[str, str] = ("Synthetic:2Pin", "Synthetic:2Pin"),
    target_functions: tuple[str, str] = ("BIAS_IN", "BIAS_IN"),
    target_types: tuple[str, str] = ("power_in", "power_in"),
    inventories: tuple[tuple[str, ...], tuple[str, ...]] = (("1", "2"), ("1", "2")),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build two distinct connector aliases with one exact shared passive pin."""
    references = ("J1", "J2")
    nets: dict[str, tuple[str, ...]] = {"SYNTHETIC_SIGNAL": ("J1.2", "J2.2")}
    for reference, net in zip(references, assignments, strict=True):
        if net is not None:
            nets[net] = (*nets.get(net, ()), f"{reference}.1")
    return NetlistContract(
        components={
            reference: ComponentContract(value=value, footprint=footprint, part_id=part_id)
            for reference, value, footprint, part_id in zip(
                references, values, footprints, part_ids, strict=True
            )
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols=dict(zip(references, symbols, strict=True)),
        component_pin_numbers=dict(zip(references, inventories, strict=True)),
        pin_functions={
            "J1.1": target_functions[0],
            "J2.1": target_functions[1],
            "J1.2": "Pin_2",
            "J2.2": "Pin_2",
        },
        pin_electrical_types={
            "J1.1": target_types[0],
            "J2.1": target_types[1],
            "J1.2": "passive",
            "J2.2": "passive",
        },
    )
