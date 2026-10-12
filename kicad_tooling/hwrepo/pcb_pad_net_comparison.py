"""Compare assigned schematic pin nets with source-bound native PCB pad nets."""

from __future__ import annotations

from .models import NetlistContract
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_pad_net_models import PcbSchematicBoardPadNetMismatch

_SUPPORTED_SNAPSHOT_SCHEMAS = {"12", "13"}


def compare_schematic_pcb_pad_nets(
    netlist: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbSchematicBoardPadNetMismatch, ...]:
    """Report exact schematic/PCB pad-net assignment differences for matching footprints.

    This compares source assignments by reference and pin number. It does not infer
    that peer pins or similarly named nets should be connected, and it does not
    establish physical copper continuity.
    """
    if snapshot.schema_version not in _SUPPORTED_SNAPSHOT_SCHEMAS:
        raise ValueError("PCB pad net comparison requires native snapshot schema 12 or 13")

    components: dict[str, tuple[str, str]] = {}
    for reference, component in netlist.components.items():
        key = reference.casefold()
        if key in components:
            raise ValueError("Native netlist has duplicate case-insensitive component references")
        components[key] = (reference, component.footprint.strip())

    footprints: dict[str, tuple[str, str]] = {}
    for footprint in snapshot.footprints:
        key = footprint.reference.casefold()
        if key in footprints:
            raise ValueError("Native PCB has duplicate case-insensitive footprint references")
        footprints[key] = (footprint.reference, footprint.footprint.strip())

    schematic_nets: dict[tuple[str, str], str | None] = {}
    for net, pins in netlist.nets.items():
        for pin in pins:
            key = _pin_key(pin, components)
            if key in schematic_nets:
                raise ValueError("Native netlist assigns one pin to multiple electrical states")
            schematic_nets[key] = net
    for pins in netlist.unconnected_nets.values():
        for pin in pins:
            key = _pin_key(pin, components)
            if key in schematic_nets:
                raise ValueError("Native netlist marks an assigned pin as unconnected")
            schematic_nets[key] = None

    board_pads = {item.pad.casefold(): item for item in snapshot.pads}
    mismatches: list[PcbSchematicBoardPadNetMismatch] = []
    for (reference_key, pin_number), schematic_net in sorted(
        schematic_nets.items(), key=lambda item: (item[0][0], item[0][1])
    ):
        component = components.get(reference_key)
        if component is None or not component[1]:
            continue
        board_footprint = footprints.get(reference_key)
        if board_footprint is None or board_footprint[1] != component[1]:
            continue

        reference = component[0]
        pad_reference = f"{reference}.{pin_number}"
        board_pad = board_pads.get(pad_reference.casefold())
        if board_pad is None:
            if schematic_net is not None:
                mismatches.append(
                    PcbSchematicBoardPadNetMismatch(
                        reference=reference,
                        pin=pin_number,
                        mismatch="board_pad_missing",
                        schematic_net=schematic_net,
                        board_net=None,
                    )
                )
            continue

        board_net = board_pad.net
        if schematic_net is None:
            if board_net is not None:
                mismatches.append(
                    PcbSchematicBoardPadNetMismatch(
                        reference=reference,
                        pin=pin_number,
                        mismatch="schematic_unconnected_board_assigned",
                        schematic_net=None,
                        board_net=board_net,
                    )
                )
        elif board_net is None:
            mismatches.append(
                PcbSchematicBoardPadNetMismatch(
                    reference=reference,
                    pin=pin_number,
                    mismatch="board_pad_unassigned",
                    schematic_net=schematic_net,
                    board_net=None,
                )
            )
        elif board_net != schematic_net:
            mismatches.append(
                PcbSchematicBoardPadNetMismatch(
                    reference=reference,
                    pin=pin_number,
                    mismatch="net_assignment_differs",
                    schematic_net=schematic_net,
                    board_net=board_net,
                )
            )

    return tuple(mismatches)


def _pin_key(
    pin: str,
    components: dict[str, tuple[str, str]],
) -> tuple[str, str]:
    reference, separator, pin_number = pin.rpartition(".")
    key = reference.casefold()
    if not separator or not reference or not pin_number or key not in components:
        raise ValueError("Native netlist pin assignment has an invalid component pin reference")
    return key, pin_number
