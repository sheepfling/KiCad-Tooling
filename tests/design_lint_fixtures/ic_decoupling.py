"""Compact synthetic netlists and contracts for mapped IC decoupling checks."""

from __future__ import annotations

from collections.abc import Iterable

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.ic_decoupling_models import (
    IcDecouplingCapacitorRequirement,
    IcDecouplingMap,
    IcDecouplingRequirement,
)
from kicad_tooling.hwrepo.models import ComponentContract, DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures import coach


def ic_decoupling_netlist(
    capacitor_values: tuple[str, ...] = ("47nF",),
    *,
    return_net: str = "GND",
    dnp_references: tuple[str, ...] = (),
    ic_value: str = "Synthetic IC",
    ic_symbol: str = "Synthetic:Logic",
    ic_footprint: str = "Synthetic:QFN",
    capacitor_symbol: str = "Device:C",
    capacitor_footprint: str = "Synthetic:0603",
) -> NetlistContract:
    components = {"U1": ComponentContract(value=ic_value, footprint=ic_footprint)}
    symbols = {"U1": ic_symbol}
    pin_numbers = {"U1": ("1", "2")}
    pin_functions = {"U1.1": "VDD", "U1.2": "GND"}
    pin_types = {"U1.1": "power_in", "U1.2": "passive"}
    power_pins = ["U1.1"]
    return_pins = ["U1.2"]
    for index, value in enumerate(capacitor_values, start=1):
        reference = f"C{index}"
        components[reference] = ComponentContract(value=value, footprint=capacitor_footprint)
        symbols[reference] = capacitor_symbol
        pin_numbers[reference] = ("1", "2")
        power_pins.append(f"{reference}.1")
        return_pins.append(f"{reference}.2")
        pin_types.update({f"{reference}.1": "passive", f"{reference}.2": "passive"})
    return NetlistContract(
        components=components,
        nets={"+3V3": tuple(power_pins), return_net: tuple(return_pins)},
        dnp_components=dnp_references,
        component_symbols=symbols,
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers=pin_numbers,
    )


def ic_decoupling_map(
    capacitor_references: Iterable[str] = ("C1",),
    *,
    minimum_total_pf: float = 100_000.0,
) -> IcDecouplingMap:
    capacitors = tuple(
        IcDecouplingCapacitorRequirement(
            reference=reference,
            expected_symbol="Device:C",
            expected_footprint="Synthetic:0603",
            power_pin=f"{reference}.1",
            return_pin=f"{reference}.2",
        )
        for reference in capacitor_references
    )
    return IcDecouplingMap(
        requirements=(
            IcDecouplingRequirement(
                id="u1-vdd-decoupling",
                basis="Synthetic test requirement: minimum total nominal capacitance is 100 nF",
                ic_reference="U1",
                expected_ic_value="Synthetic IC",
                expected_ic_symbol="Synthetic:Logic",
                expected_ic_footprint="Synthetic:QFN",
                power_pin="U1.1",
                power_net="+3V3",
                return_net="GND",
                minimum_total_capacitance_pf=minimum_total_pf,
                capacitors=capacitors,
            ),
        )
    )


def catalog_reachability_rule_ids() -> set[str]:
    """Return rule IDs reached by the synthetic below-minimum requirement."""
    report = evaluate(
        "synthetic-catalog-ic-decoupling",
        coach(ic_decoupling_netlist(("47nF",))),
        DesignLintPolicy(ic_decoupling_map=ic_decoupling_map()),
    )
    return {item.rule_id for item in report.findings}
