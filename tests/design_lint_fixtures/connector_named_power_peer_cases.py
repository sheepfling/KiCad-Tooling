"""Synthetic netlist contracts for named connector power-peer fixtures."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def named_connector_power_peer_cases() -> dict[str, NetlistContract]:
    """Mirror native input/output peer faults, controls, and open-pin variants."""
    cases: dict[str, NetlistContract] = {}
    for direction, function, electrical_type, part_id in (
        ("input", "BIAS_IN", "power_in", "SYNTHETIC-CONNECTOR-NAMED-INPUT-001"),
        ("output", "BIAS_OUT", "power_out", "SYNTHETIC-CONNECTOR-NAMED-OUTPUT-001"),
    ):
        assignments_by_case = {
            "open-fault": ("+3V3", None),
            "open-control": ("+3V3", "+3V3"),
            "all-open-fault": (None, None),
            "divergent-fault": ("+3V3", "+5V"),
        }
        references = ("J1", "J2")
        for suffix, assignments in assignments_by_case.items():
            nets: dict[str, tuple[str, ...]] = {"SIGNAL": ("J1.2", "J2.2")}
            for reference, net in zip(references, assignments, strict=True):
                if net is not None:
                    nets[net] = (*nets.get(net, ()), f"{reference}.1")
            case = f"connector-named-power-{direction}-{suffix}"
            cases[case] = NetlistContract(
                components={
                    reference: ComponentContract(
                        value="Synthetic named connector peer",
                        footprint="Synthetic:Connector_2x1",
                        part_id=part_id,
                    )
                    for reference in references
                },
                nets=nets,
                component_symbols={
                    "J1": f"Lint:NamedPeerPower{direction.title()}A",
                    "J2": f"Lint:NamedPeerPower{direction.title()}B",
                },
                component_pin_numbers={reference: ("1", "2") for reference in references},
                pin_functions={
                    **{f"{reference}.1": function for reference in references},
                    **{f"{reference}.2": "GND" for reference in references},
                },
                pin_electrical_types={
                    **{f"{reference}.1": electrical_type for reference in references},
                    **{f"{reference}.2": "passive" for reference in references},
                },
            )
    return cases
