"""Synthetic native-shaped netlists for partial RS-485 A/B line review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def rs485_unconnected_line_netlist(
    *,
    open_role: str | None = "a",
    functions: tuple[str, str] = ("A", "B"),
    identity: str = "RS-485 transceiver",
    symbol: str = "Synthetic:Rs485Transceiver",
    reference: str = "U1",
    dnp: bool = False,
) -> NetlistContract:
    """Create one identified IC with complete A/B pin-function evidence."""
    assignments: dict[str, tuple[str, ...]] = {
        "RS485_A": (f"{reference}.1",),
        "RS485_B": (f"{reference}.2",),
    }
    if open_role is not None:
        open_role = open_role.casefold()
        if open_role not in {"a", "b"}:
            raise ValueError("open_role must be 'a', 'b', or None")
        net = f"RS485_{open_role.upper()}"
        assignments.pop(net)
    return NetlistContract(
        components={reference: ComponentContract(value=identity, footprint="Synthetic:IC")},
        nets=assignments,
        unconnected_nets={
            "unconnected": ()
            if open_role is None
            else (f"{reference}.{1 if open_role == 'a' else 2}",)
        },
        dnp_components=(reference,) if dnp else (),
        component_symbols={reference: symbol},
        pin_functions={f"{reference}.1": functions[0], f"{reference}.2": functions[1]},
        component_pin_numbers={reference: ("1", "2")},
    )
