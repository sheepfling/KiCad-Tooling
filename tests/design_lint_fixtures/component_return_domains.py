"""Native-shaped contracts for component return-domain lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def component_return_pin_domains(*, split: bool = True, dnp: bool = False) -> NetlistContract:
    """Build a fitted two-return component with split or common assignments."""
    nets = (
        {"RETURN_A": ("U1.1",), "RETURN_B": ("U1.2",)}
        if split
        else {"RETURN": ("U1.1", "U1.2")}
    )
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic two-return component", footprint="Synthetic:Component"
            )
        },
        nets=nets,
        component_symbols={"U1": "Lint:MultiReturnComponent"},
        dnp_components=("U1",) if dnp else (),
        component_pin_numbers={"U1": ("1", "2")},
        pin_functions={"U1.1": "GND", "U1.2": "AGND"},
    )
