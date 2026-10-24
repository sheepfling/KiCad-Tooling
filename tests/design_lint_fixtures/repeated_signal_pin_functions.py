"""Small synthetic netlists for repeated signal-function regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def repeated_signal_pin_component(
    *,
    split: bool = True,
    reference: str = "U1",
    symbol: str = "Lint:RepeatedSignalPins",
    dnp: bool = False,
    functions: dict[str, str] | None = None,
    electrical_types: dict[str, str] | None = None,
    pin_numbers: tuple[str, ...] = ("1", "2", "3", "4"),
) -> NetlistContract:
    """Build one fitted component with duplicated explicit signal metadata."""
    functions = functions or {
        f"{reference}.1": "READY",
        f"{reference}.2": "READY",
        f"{reference}.3": "STATUS",
        f"{reference}.4": "Pin_4",
    }
    electrical_types = electrical_types or {
        f"{reference}.1": "input",
        f"{reference}.2": "input",
        f"{reference}.3": "input",
        f"{reference}.4": "passive",
    }
    nets: dict[str, tuple[str, ...]] = (
        {"SIGNAL_A": (f"{reference}.1",), "SIGNAL_B": (f"{reference}.2",)}
        if split
        else {"SIGNAL": (f"{reference}.1", f"{reference}.2")}
    )
    nets["STATUS"] = (f"{reference}.3",)
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic signal component", footprint="Lint:IC")
        },
        nets=nets,
        component_symbols={reference: symbol},
        dnp_components=(reference,) if dnp else (),
        component_pin_numbers={reference: pin_numbers},
        pin_functions=functions,
        pin_electrical_types=electrical_types,
    )
