"""Usb c contract for deterministic KiCad bus analysis."""

from __future__ import annotations

from .models import (
    AnalysisPending,
    ElectricalCheck,
    NetlistContract,
    UsbCAnalysis,
    UsbCcResistorAttachment,
    UsbCProtectionAnalysis,
    UsbCVbusCapacitanceRequirement,
)
from .resistor_paths import direct_resistors
from .usb_c_vbus import (
    usb_c_vbus_capacitance_check,
    usb_c_vbus_path_check,
)


def usb_c_checks(spec: UsbCAnalysis, observed: NetlistContract) -> tuple[ElectricalCheck, ...]:
    """Compare authored USB-C CC, connector pin, component, and protection facts."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
    known_pins = set(observed.pin_functions) | set(pin_nets)
    known_pins.update(
        f"{reference}.{number}"
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    )
    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): value for reference, value in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    resistors = direct_resistors(observed)
    resistors_by_reference = {item.reference.casefold(): item for item in resistors}

    def assignment_failure(pin: str, expected_net: str) -> str | None:
        if pin not in known_pins:
            return f"{pin} is absent from the native symbol pin inventory"
        actual = pin_nets.get(pin, set())
        if actual != {expected_net}:
            assigned = ", ".join(sorted(actual)) if actual else "unconnected"
            return f"{pin} is assigned to {assigned}; expected {expected_net}"
        return None

    results: list[ElectricalCheck] = []
    for port in spec.ports:
        base = f"usb-c/{port.id}"
        failures = [
            issue
            for pin, net in (
                (port.cc1.connector_pin, port.cc1.net),
                (port.cc2.connector_pin, port.cc2.net),
                *((assignment.pin, assignment.net) for assignment in port.vbus_pins),
                *((pin, port.ground_net) for pin in port.ground_pins),
            )
            if (issue := assignment_failure(pin, net)) is not None
        ]
        results.append(
            ElectricalCheck(
                id=f"{base}/connector-pins",
                status="FAIL" if failures else "PASS",
                detail=(
                    "; ".join(failures)
                    if failures
                    else "Declared CC, VBUS, and ground connector/board pins match their exact nets."
                ),
            )
        )
        if port.vbus_path is not None:
            results.append(
                usb_c_vbus_path_check(
                    port.vbus_path,
                    observed,
                    f"{base}/vbus-path/{port.vbus_path.id}",
                )
            )
        if isinstance(port.vbus_capacitance, UsbCVbusCapacitanceRequirement):
            results.append(
                usb_c_vbus_capacitance_check(
                    port.vbus_capacitance,
                    vbus_net=port.vbus_net,
                    ground_net=port.ground_net,
                    observed=observed,
                    check_id=f"{base}/vbus-capacitance",
                )
            )
        elif isinstance(port.vbus_capacitance, AnalysisPending):
            results.append(
                ElectricalCheck(
                    id=f"{base}/vbus-capacitance",
                    status="NOT_CONFIGURED",
                    detail=port.vbus_capacitance.reason,
                )
            )
        else:
            results.append(
                ElectricalCheck(
                    id=f"{base}/vbus-capacitance",
                    status="NOT_APPLICABLE",
                    detail=port.vbus_capacitance.reason,
                )
            )

        if port.controller is not None:
            entry = components.get(port.controller.reference.casefold())
            identity_failures: list[str] = []
            if entry is None:
                identity_failures.append(f"{port.controller.reference} is absent from the netlist")
            else:
                reference, component = entry
                if symbols.get(reference.casefold()) != port.controller.symbol:
                    identity_failures.append(
                        f"{reference} symbol is {symbols.get(reference.casefold(), 'unknown')}; "
                        f"expected {port.controller.symbol}"
                    )
                if component.footprint != port.controller.footprint:
                    identity_failures.append(
                        f"{reference} footprint is {component.footprint or 'empty'}; "
                        f"expected {port.controller.footprint}"
                    )
            results.append(
                ElectricalCheck(
                    id=f"{base}/controller-identity",
                    status="FAIL" if identity_failures else "PASS",
                    detail=(
                        "; ".join(identity_failures)
                        if identity_failures
                        else f"{port.controller.reference} matches the declared USB-C controller symbol and footprint."
                    ),
                )
            )

        for label, line in (("cc1", port.cc1), ("cc2", port.cc2)):
            attachment = line.attachment
            if isinstance(attachment, UsbCcResistorAttachment):
                expected_ref = attachment.reference.casefold()
                resistor = resistors_by_reference.get(expected_ref)
                entry = components.get(expected_ref)
                failures: list[str] = []
                if entry is None:
                    failures.append(f"{attachment.reference} is absent from the netlist")
                elif expected_ref in dnp:
                    failures.append(f"{attachment.reference} is DNP but must be fitted")
                if resistor is None:
                    if entry is not None and expected_ref not in dnp:
                        failures.append(
                            f"{attachment.reference} is not a recognized fitted two-terminal resistor"
                        )
                else:
                    actual_path = {resistor.first_net, resistor.second_net}
                    expected_path = {line.net, attachment.rail_net}
                    if actual_path != expected_path:
                        failures.append(
                            f"{attachment.reference} connects {resistor.first_net}/{resistor.second_net}; "
                            f"expected {line.net}/{attachment.rail_net}"
                        )
                    if (
                        not attachment.minimum_ohms
                        <= resistor.resistance_ohms
                        <= attachment.maximum_ohms
                    ):
                        failures.append(
                            f"{attachment.reference} is {resistor.resistance_ohms:g}Ω, outside "
                            f"{attachment.minimum_ohms:g}–{attachment.maximum_ohms:g}Ω"
                        )
                extras = tuple(
                    item
                    for item in resistors
                    if line.net in {item.first_net, item.second_net}
                    and item.reference.casefold() != expected_ref
                )
                if extras:
                    failures.append(
                        "unlisted fitted resistors touch this CC net: "
                        + ", ".join(item.reference for item in extras)
                    )
                detail = (
                    "; ".join(failures)
                    if failures
                    else (
                        f"{attachment.behavior.upper()} {attachment.reference}="
                        f"{resistor.resistance_ohms:g}Ω connects {line.net} to "
                        f"{attachment.rail_net} within the declared nominal range."
                    )
                    if resistor is not None
                    else f"{attachment.reference} has no recognized fitted resistor."
                )
                results.append(
                    ElectricalCheck(
                        id=f"{base}/{label}-attachment",
                        status="FAIL" if failures else "PASS",
                        observed=resistor.resistance_ohms if resistor is not None else None,
                        unit="Ω",
                        detail=detail,
                    )
                )
            else:
                failures: list[str] = []
                if (issue := assignment_failure(attachment.controller_pin, line.net)) is not None:
                    failures.append(issue)
                extras = tuple(
                    item for item in resistors if line.net in {item.first_net, item.second_net}
                )
                if extras:
                    failures.append(
                        "unlisted fitted resistors touch this controller-driven CC net: "
                        + ", ".join(item.reference for item in extras)
                    )
                results.append(
                    ElectricalCheck(
                        id=f"{base}/{label}-attachment",
                        status="FAIL" if failures else "PASS",
                        detail=(
                            "; ".join(failures)
                            if failures
                            else f"Controller pin {attachment.controller_pin} is assigned to {line.net}."
                        ),
                    )
                )

        if isinstance(port.protection, UsbCProtectionAnalysis):
            for requirement in port.protection.components:
                entry = components.get(requirement.reference.casefold())
                component_failures: list[str] = []
                if entry is None:
                    component_failures.append(f"{requirement.reference} is absent from the netlist")
                else:
                    reference, component = entry
                    if reference.casefold() in dnp:
                        component_failures.append(f"{reference} is DNP but protection is required")
                    if symbols.get(reference.casefold()) != requirement.symbol:
                        component_failures.append(
                            f"{reference} symbol is {symbols.get(reference.casefold(), 'unknown')}; "
                            f"expected {requirement.symbol}"
                        )
                    if component.footprint != requirement.footprint:
                        component_failures.append(
                            f"{reference} footprint is {component.footprint or 'empty'}; "
                            f"expected {requirement.footprint}"
                        )
                for assignment in requirement.pins:
                    if (issue := assignment_failure(assignment.pin, assignment.net)) is not None:
                        component_failures.append(issue)
                results.append(
                    ElectricalCheck(
                        id=f"{base}/protection/{requirement.reference}",
                        status="FAIL" if component_failures else "PASS",
                        detail=(
                            "; ".join(component_failures)
                            if component_failures
                            else f"{requirement.reference} matches the declared symbol, footprint, and pin nets."
                        ),
                    )
                )
        elif isinstance(port.protection, AnalysisPending):
            results.append(
                ElectricalCheck(
                    id=f"{base}/protection",
                    status="NOT_CONFIGURED",
                    detail=port.protection.reason,
                )
            )
        else:
            results.append(
                ElectricalCheck(
                    id=f"{base}/protection",
                    status="NOT_APPLICABLE",
                    detail=port.protection.reason,
                )
            )

        if port.role == "debug_accessory":
            results.append(
                ElectricalCheck(
                    id=f"{base}/role-support",
                    status="NOT_RUN",
                    detail="USB-C debug-accessory role behavior is not modeled by this deterministic v1 check.",
                )
            )
    return tuple(results)
