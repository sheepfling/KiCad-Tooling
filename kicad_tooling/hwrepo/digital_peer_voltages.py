"""Check authored voltage limits for directly connected digital pins."""

from __future__ import annotations

from .models import (
    DigitalPeerPinRequirement,
    DigitalPeerVoltageAnalysis,
    ElectricalCheck,
    NetlistContract,
)
from .serial_heuristics import logic_direction_check


def digital_peer_voltage_checks(
    spec: DigitalPeerVoltageAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Compare mapped output/input limits only when native topology matches."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    known_pins = {
        f"{reference}.{number}".casefold()
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    }
    known_pins.update(pin.casefold() for pin in observed.pin_functions)
    known_pins.update(pin.casefold() for pins in observed.nets.values() for pin in pins)
    components = {
        reference.casefold(): component for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}

    def identity_issue(endpoint: DigitalPeerPinRequirement) -> str | None:
        key = endpoint.reference.casefold()
        component = components.get(key)
        if component is None:
            return f"{endpoint.reference} is absent from the native netlist"
        if key in dnp:
            return f"{endpoint.reference} is marked DNP"
        actual_symbol = symbols.get(key)
        if actual_symbol != endpoint.symbol:
            return f"{endpoint.reference} symbol is {actual_symbol or 'unknown'}; expected {endpoint.symbol}"
        if component.footprint != endpoint.footprint:
            return f"{endpoint.reference} footprint is {component.footprint or 'empty'}; expected {endpoint.footprint}"
        return None

    def pin_issue(endpoint: DigitalPeerPinRequirement) -> str | None:
        key = endpoint.pin.casefold()
        if key not in known_pins:
            return f"{endpoint.pin} is absent from the native symbol pin inventory"
        actual = pin_nets.get(key, set())
        if actual != {endpoint.net}:
            assigned = ", ".join(sorted(actual)) if actual else "unconnected"
            return f"{endpoint.pin} is assigned to {assigned}; expected {endpoint.net}"
        return None

    checks: list[ElectricalCheck] = []
    for link in spec.links:
        base = f"digital-peer-voltage/{link.id}"
        endpoint_valid: list[bool] = []
        for role, endpoint in (("driver", link.driver), ("receiver", link.receiver)):
            identity_failure = identity_issue(endpoint)
            pin_failure = pin_issue(endpoint)
            endpoint_valid.extend((identity_failure is None, pin_failure is None))
            checks.extend(
                (
                    ElectricalCheck(
                        id=f"{base}/{role}/identity",
                        status="PASS" if identity_failure is None else "FAIL",
                        detail=(
                            identity_failure
                            or f"{endpoint.reference} matches the reviewed symbol and footprint."
                        ),
                    ),
                    ElectricalCheck(
                        id=f"{base}/{role}/pin",
                        status="PASS" if pin_failure is None else "FAIL",
                        detail=(
                            pin_failure
                            or f"{endpoint.pin} is assigned to the reviewed net {endpoint.net}."
                        ),
                    ),
                )
            )

        compatibility_id = f"{base}/compatibility"
        if not all(endpoint_valid):
            checks.append(
                ElectricalCheck(
                    id=compatibility_id,
                    status="NOT_APPLICABLE",
                    detail=(
                        "Voltage limits were not compared because the source-bound native netlist "
                        "does not match the reviewed direct pin map."
                    ),
                )
            )
        elif link.output_limits is None or link.input_limits is None:
            missing: list[str] = []
            if link.output_limits is None:
                missing.append("driver VOL/VOH guarantees")
            if link.input_limits is None:
                missing.append("receiver VIL/VIH thresholds and absolute limits")
            checks.append(
                ElectricalCheck(
                    id=compatibility_id,
                    status="NOT_CONFIGURED",
                    detail=(
                        f"{link.basis}: missing reviewed {' and '.join(missing)} with operating "
                        "conditions and source references."
                    ),
                )
            )
        else:
            measured = logic_direction_check(
                compatibility_id,
                "driver to receiver",
                link.output_limits,
                link.input_limits,
            )
            checks.append(
                measured.model_copy(update={"detail": f"{link.basis}. {measured.detail}"})
            )
    return tuple(checks)
