"""Source-bound local capacitance scope checks for I2C pull-up requirements."""

from __future__ import annotations

from decimal import Decimal

from .capacitance_values import parse_capacitance_pf
from .component_references import is_capacitor_reference
from .i2c_pullup_models import I2cPullupElectricalWindow
from .models import ComponentContract, ElectricalCheck, NetlistContract


def i2c_pullup_capacitance_check(
    bus_id: str,
    line_name: str,
    line_net: str,
    window: I2cPullupElectricalWindow,
    observed: NetlistContract,
) -> ElectricalCheck | None:
    """Check scoped fitted capacitors and residual bounds against one bus line."""
    scope = window.capacitance_scope
    if scope is None:
        return None

    dnp = {reference.casefold() for reference in observed.dnp_components}
    candidates: dict[str, str] = {}
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
            reference = pin.rsplit(".", 1)[0]
            if (
                net == line_net
                and is_capacitor_reference(reference)
                and reference.casefold() not in dnp
            ):
                candidates.setdefault(reference.casefold(), reference)

    requirements = {item.reference.casefold(): item for item in scope.contributors}
    issues: list[str] = []
    unreviewed = sorted(set(candidates) - set(requirements))
    attached_references = {
        pin.rsplit(".", 1)[0].casefold() for pin in observed.nets.get(line_net, ())
    }
    unobserved = sorted(key for key in requirements if key not in attached_references or key in dnp)
    if unreviewed:
        issues.append(
            f"unmapped fitted capacitors on {line_net}: "
            + ", ".join(candidates[key] for key in unreviewed)
        )
    if unobserved:
        issues.append(
            "mapped capacitors are absent, DNP, or not attached to the line: "
            + ", ".join(requirements[key].reference for key in unobserved)
        )

    components_by_reference: dict[str, list[tuple[str, ComponentContract]]] = {}
    for reference, component in observed.components.items():
        components_by_reference.setdefault(reference.casefold(), []).append((reference, component))
    symbols_by_reference: dict[str, list[str]] = {}
    for reference, symbol in observed.component_symbols.items():
        symbols_by_reference.setdefault(reference.casefold(), []).append(symbol)

    for requirement in scope.contributors:
        key = requirement.reference.casefold()
        if requirement.return_net == line_net:
            issues.append(
                f"{requirement.reference} return net must differ from I2C line {line_net}"
            )
        entries = components_by_reference.get(key, [])
        if len(entries) != 1:
            issues.append(
                f"{requirement.reference} is "
                + ("absent" if not entries else "ambiguous")
                + " in the native component inventory"
            )
            continue
        actual_reference, component = entries[0]
        if key in dnp:
            issues.append(f"{actual_reference} is DNP but required as a capacitance contributor")
        if component.footprint != requirement.expected_footprint:
            issues.append(
                f"{actual_reference} footprint is {component.footprint or 'empty'}; "
                f"expected {requirement.expected_footprint}"
            )
        if (
            requirement.expected_part_id is not None
            and component.part_id != requirement.expected_part_id
        ):
            issues.append(
                f"{actual_reference} PART_ID is {component.part_id or 'missing'}; "
                f"expected {requirement.expected_part_id}"
            )
        symbols = symbols_by_reference.get(key, [])
        if len(symbols) != 1 or symbols[0] != requirement.expected_symbol:
            actual_symbol = symbols[0] if len(symbols) == 1 else "unknown"
            issues.append(
                f"{actual_reference} symbol is {actual_symbol}; "
                f"expected {requirement.expected_symbol}"
            )

        inventory = observed.component_pin_numbers.get(actual_reference)
        expected_pins = {
            requirement.signal_pin.rsplit(".", 1)[1].casefold(),
            requirement.return_pin.rsplit(".", 1)[1].casefold(),
        }
        if inventory is None:
            issues.append(f"{actual_reference} has no native pin inventory")
        elif {pin.casefold() for pin in inventory} != expected_pins:
            issues.append(
                f"{actual_reference} native pins are {tuple(inventory)}; "
                f"expected exactly {tuple(sorted(expected_pins))}"
            )

        signal_assignments = pin_nets.get(requirement.signal_pin.casefold(), set())
        return_assignments = pin_nets.get(requirement.return_pin.casefold(), set())
        if signal_assignments != {line_net} or return_assignments != {requirement.return_net}:
            issues.append(
                f"{requirement.reference} pin nets are "
                f"{requirement.signal_pin}={tuple(sorted(signal_assignments)) or ('unconnected',)}, "
                f"{requirement.return_pin}={tuple(sorted(return_assignments)) or ('unconnected',)}; "
                f"expected {line_net} and {requirement.return_net}"
            )

        nominal = parse_capacitance_pf(component.value)
        if nominal is None:
            issues.append(
                f"{actual_reference} value {component.value!r} is not a supported capacitance"
            )
        else:
            minimum = Decimal(str(requirement.minimum_nominal_capacitance_pf))
            maximum = Decimal(str(requirement.maximum_nominal_capacitance_pf))
            if not minimum <= nominal <= maximum:
                issues.append(
                    f"{actual_reference} nominal capacitance is {nominal}pF, outside "
                    f"{minimum}–{maximum}pF"
                )

    declared_maximum = sum(
        (Decimal(str(item.maximum_effective_capacitance_pf)) for item in scope.contributors),
        start=Decimal(0),
    ) + Decimal(str(scope.maximum_residual_capacitance_pf))
    bus_maximum = Decimal(str(window.maximum_bus_capacitance_pf))
    if declared_maximum > bus_maximum:
        issues.append(
            f"mapped effective capacitance plus residual bound is {declared_maximum}pF, "
            f"above the authored bus maximum of {bus_maximum}pF"
        )

    contributors = (
        "; ".join(
            f"{item.reference}≤{item.maximum_effective_capacitance_pf:g}pF "
            f"({item.effective_capacitance_basis})"
            for item in scope.contributors
        )
        or "no mapped local capacitors"
    )
    detail = (
        f"{line_name} net {line_net}: {contributors}; residual ≤ "
        f"{scope.maximum_residual_capacitance_pf:g}pF ({scope.residual_capacitance_basis}); "
        f"inventory basis: {scope.inventory_basis}; total upper bound {declared_maximum}pF "
        f"versus bus maximum {bus_maximum}pF."
    )
    if issues:
        detail += " Issues: " + "; ".join(issues) + "."
    return ElectricalCheck(
        id=f"i2c-pullup/{bus_id}/{line_name.casefold()}/electrical-window/capacitance-scope",
        status="FAIL" if issues else "PASS",
        observed=float(declared_maximum),
        unit="pF",
        detail=detail,
    )
