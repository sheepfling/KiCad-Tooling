"""Compare explicit positive-voltage net labels with authored IC pin ranges."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .component_supply_range_models import (
    ComponentSupplyVoltageRangeMap,
    ComponentSupplyVoltageRangeRequirement,
    component_supply_voltage_range_map_sha256,
)
from .netlist_contract_models import NetlistContract
from .power_rails import explicit_voltage_rail_value

RULE_ID = "power.component_supply_voltage_outside_range"


@dataclass(frozen=True, slots=True)
class ComponentSupplyVoltageRangeIssue:
    """One mapped pin whose native evidence is incomplete or outside its range."""

    requirement: ComponentSupplyVoltageRangeRequirement
    map_sha256: str
    actual_net: str | None
    actual_voltage_v: Decimal | None
    issues: tuple[str, ...]


def component_supply_voltage_range_issues(
    observed: NetlistContract,
    requirements: ComponentSupplyVoltageRangeMap | None,
) -> tuple[ComponentSupplyVoltageRangeIssue, ...]:
    """Return supply pins needing review; matching label values stay quiet.

    An explicit voltage in a schematic net label is only a nominal clue. The
    project map supplies the reviewed part-specific range; this comparison
    does not establish actual net voltage or component suitability.
    """
    if requirements is None:
        return ()

    map_sha256 = component_supply_voltage_range_map_sha256(requirements)
    components = {
        reference.casefold(): (reference, value) for reference, value in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    pin_functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    pin_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    pin_inventories = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    pin_nets: dict[str, list[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), []).append(net)
    dnp = {reference.casefold() for reference in observed.dnp_components}

    findings: list[ComponentSupplyVoltageRangeIssue] = []
    for requirement in requirements.requirements:
        reference_key = requirement.reference.casefold()
        pin_key = requirement.pin.casefold()
        actual_component = components.get(reference_key)
        issues: list[str] = []
        if actual_component is None:
            issues.append(f"{requirement.reference} is absent from the native netlist")
        else:
            actual_reference, component = actual_component
            if reference_key in dnp:
                issues.append(f"{actual_reference} is marked DNP")
            actual_symbol = symbols.get(reference_key)
            if actual_symbol != requirement.expected_symbol:
                issues.append(
                    f"symbol is {actual_symbol or 'unknown'}; expected {requirement.expected_symbol}"
                )
            if component.footprint != requirement.expected_footprint:
                issues.append(
                    f"footprint is {component.footprint or 'empty'}; "
                    f"expected {requirement.expected_footprint}"
                )
            if component.part_id != requirement.expected_part_id:
                issues.append(
                    f"PART_ID is {component.part_id or 'missing'}; "
                    f"expected {requirement.expected_part_id}"
                )

        pin_number = requirement.pin.rsplit(".", maxsplit=1)[1].casefold()
        inventory = pin_inventories.get(reference_key)
        if inventory is None or pin_number not in inventory:
            issues.append(f"{requirement.pin} is absent from the native pin inventory")
        actual_function = pin_functions.get(pin_key)
        if (
            actual_function is None
            or actual_function.casefold() != requirement.expected_pin_function.casefold()
        ):
            issues.append(
                f"pin function is {actual_function or 'unknown'}; "
                f"expected {requirement.expected_pin_function}"
            )
        actual_type = pin_types.get(pin_key)
        if actual_type != "power_in":
            issues.append(f"pin electrical type is {actual_type or 'unknown'}; expected power_in")

        actual_nets = tuple(sorted(pin_nets.get(pin_key, ())))
        actual_net = actual_nets[0] if len(actual_nets) == 1 else None
        actual_voltage = explicit_voltage_rail_value(actual_net) if actual_net is not None else None
        if not actual_nets:
            issues.append(f"{requirement.pin} is unassigned")
        elif len(actual_nets) != 1:
            issues.append(f"{requirement.pin} has ambiguous nets: {', '.join(actual_nets)}")
        elif actual_voltage is None:
            issues.append(f"net {actual_net} has no supported explicit nominal-voltage label")
        elif not issues and not (
            Decimal(str(requirement.minimum_voltage_v))
            <= actual_voltage
            <= Decimal(str(requirement.maximum_voltage_v))
        ):
            issues.append(
                f"net label indicates {actual_voltage:g} V outside the reviewed inclusive range "
                f"[{requirement.minimum_voltage_v:g}, {requirement.maximum_voltage_v:g}] V"
            )

        if issues:
            findings.append(
                ComponentSupplyVoltageRangeIssue(
                    requirement=requirement,
                    map_sha256=map_sha256,
                    actual_net=actual_net,
                    actual_voltage_v=actual_voltage,
                    issues=tuple(issues),
                )
            )
    return tuple(
        sorted(findings, key=lambda item: (item.requirement.pin.casefold(), item.requirement.pin))
    )
