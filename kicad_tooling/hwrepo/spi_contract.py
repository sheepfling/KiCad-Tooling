"""Spi contract for deterministic KiCad bus analysis."""

from __future__ import annotations

from .models import (
    ElectricalCheck,
    NetlistContract,
    SpiAnalysis,
    SpiBridgeRequirement,
    SpiMisoConnectedRequirement,
    SpiPinNetRequirement,
    SpiPinNotPresent,
    SpiPinUnconnectedRequirement,
)


def spi_checks(spec: SpiAnalysis, observed: NetlistContract) -> tuple[ElectricalCheck, ...]:
    """Compare authored SPI roles and membership with exact native pin/net evidence."""
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
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}

    def pin_issue(pin: str, expected_net: str) -> str | None:
        key = pin.casefold()
        if key not in known_pins:
            return f"{pin} is absent from the native symbol pin inventory"
        actual = pin_nets.get(key, set())
        if actual != {expected_net}:
            assigned = ", ".join(sorted(actual)) if actual else "unconnected"
            return f"{pin} is assigned to {assigned}; expected {expected_net}"
        return None

    def unconnected_issue(pin: str) -> str | None:
        key = pin.casefold()
        if key not in known_pins:
            return f"{pin} is absent from the native symbol pin inventory"
        actual = pin_nets.get(key, set())
        if actual:
            return f"{pin} is assigned to {', '.join(sorted(actual))}; expected unconnected"
        return None

    def identity_issues(reference: str, symbol: str, footprint: str) -> list[str]:
        key = reference.casefold()
        entry = components.get(key)
        if entry is None:
            return [f"{reference} is absent from the netlist"]
        actual_reference, component = entry
        issues: list[str] = []
        if key in dnp:
            issues.append(f"{actual_reference} is marked DNP")
        actual_symbol = symbols.get(key)
        if actual_symbol != symbol:
            issues.append(
                f"{actual_reference} symbol is {actual_symbol or 'unknown'}; expected {symbol}"
            )
        if component.footprint != footprint:
            issues.append(
                f"{actual_reference} footprint is {component.footprint or 'empty'}; expected {footprint}"
            )
        return issues

    def pin_disposition(
        pin: SpiPinNetRequirement | SpiMisoConnectedRequirement | SpiPinUnconnectedRequirement,
    ) -> str | None:
        if isinstance(pin, SpiPinUnconnectedRequirement):
            return unconnected_issue(pin.pin)
        return pin_issue(pin.pin, pin.net)

    results: list[ElectricalCheck] = []
    for bus in spec.buses:
        base = f"spi/{bus.id}"
        controller = bus.controller
        controller_identity = identity_issues(
            controller.reference, controller.symbol, controller.footprint
        )
        results.append(
            ElectricalCheck(
                id=f"{base}/controller-identity",
                status="FAIL" if controller_identity else "PASS",
                detail=(
                    "; ".join(controller_identity)
                    if controller_identity
                    else f"{controller.reference} matches the declared SPI controller symbol and footprint."
                ),
            )
        )

        controller_pin_requirements: list[
            tuple[
                str,
                SpiPinNetRequirement | SpiMisoConnectedRequirement | SpiPinUnconnectedRequirement,
            ]
        ] = [("SCK", controller.sck), ("MOSI", controller.mosi)]
        controller_pin_requirements.extend(
            (f"CS[{index}]", pin) for index, pin in enumerate(controller.chip_selects, start=1)
        )
        controller_pin_issues = [
            f"{role}: {issue}"
            for role, pin in controller_pin_requirements
            if (issue := pin_disposition(pin)) is not None
        ]
        if isinstance(
            controller.miso, (SpiMisoConnectedRequirement, SpiPinUnconnectedRequirement)
        ) and (issue := pin_disposition(controller.miso)):
            controller_pin_issues.append(f"MISO: {issue}")
        results.append(
            ElectricalCheck(
                id=f"{base}/controller-pins",
                status="FAIL" if controller_pin_issues else "PASS",
                detail=(
                    "; ".join(controller_pin_issues)
                    if controller_pin_issues
                    else f"Declared SCK, MOSI, MISO disposition, and {len(controller.chip_selects)} chip-select pin assignments match."
                ),
            )
        )
        if isinstance(controller.miso, SpiPinNotPresent):
            results.append(
                ElectricalCheck(
                    id=f"{base}/controller-miso",
                    status="NOT_APPLICABLE",
                    detail=f"Controller MISO is declared absent: {controller.miso.reason}",
                )
            )

        bridge_path_ok: dict[tuple[str, str, str], bool] = {}
        for bridge in bus.bridges:
            bridge_key = bridge.reference.casefold()
            issues = identity_issues(bridge.reference, bridge.symbol, bridge.footprint)
            results.append(
                ElectricalCheck(
                    id=f"{base}/bridge/{bridge.reference}/identity",
                    status="FAIL" if issues else "PASS",
                    detail=(
                        "; ".join(issues)
                        if issues
                        else f"{bridge.reference} matches the declared SPI bridge symbol and footprint."
                    ),
                )
            )
            path_issues: list[str] = []
            for path in bridge.paths:
                first = pin_issue(path.from_pin, path.from_net)
                second = pin_issue(path.to_pin, path.to_net)
                bridge_path_ok[(bridge_key, path.signal, path.from_net + "\0" + path.to_net)] = (
                    not issues and first is None and second is None
                )
                if first is not None:
                    path_issues.append(f"{path.signal} input: {first}")
                if second is not None:
                    path_issues.append(f"{path.signal} output: {second}")
            results.append(
                ElectricalCheck(
                    id=f"{base}/bridge/{bridge.reference}/pins",
                    status="FAIL" if path_issues else "PASS",
                    detail=(
                        "; ".join(path_issues)
                        if path_issues
                        else f"All {len(bridge.paths)} declared bridge path pin assignments match their nets. Internal bridge behavior is not verified."
                    ),
                )
            )

        def has_observed_route(
            signal: str,
            source: str,
            destination: str,
            *,
            bridges: tuple[SpiBridgeRequirement, ...] = bus.bridges,
            valid_paths: dict[tuple[str, str, str], bool] = bridge_path_ok,
        ) -> bool:
            if source == destination:
                return True
            graph: dict[str, set[str]] = {}
            for bridge in bridges:
                bridge_key = bridge.reference.casefold()
                for path in bridge.paths:
                    if path.signal != signal:
                        continue
                    edge_key = (bridge_key, path.signal, path.from_net + "\0" + path.to_net)
                    if not valid_paths.get(edge_key, False):
                        continue
                    graph.setdefault(path.from_net, set()).add(path.to_net)
                    graph.setdefault(path.to_net, set()).add(path.from_net)
            pending = [source]
            reached: set[str] = set()
            while pending:
                net = pending.pop()
                if net == destination:
                    return True
                if net in reached:
                    continue
                reached.add(net)
                pending.extend(graph.get(net, ()))
            return False

        def add_route(
            device_id: str,
            signal: str,
            source: str,
            destination: str,
            *,
            route_base: str = base,
        ) -> None:
            passed = has_observed_route(signal, source, destination)
            results.append(
                ElectricalCheck(
                    id=f"{route_base}/device/{device_id}/route/{signal}",
                    status="PASS" if passed else "FAIL",
                    detail=(
                        f"Declared {signal.upper()} route {source} to {destination} has matching endpoint assignments. Internal bridge behavior is not verified."
                        if passed
                        else f"No declared {signal.upper()} route with matching bridge pin assignments connects {source} to {destination}."
                    ),
                )
            )

        for device in bus.devices:
            device_base = f"{base}/device/{device.id}"
            issues = identity_issues(device.reference, device.symbol, device.footprint)
            results.append(
                ElectricalCheck(
                    id=f"{device_base}/identity",
                    status="FAIL" if issues else "PASS",
                    detail=(
                        "; ".join(issues)
                        if issues
                        else f"{device.reference} matches the declared SPI device symbol and footprint."
                    ),
                )
            )
            device_pin_requirements = (
                ("SCK", device.sck),
                ("MOSI", device.mosi),
                ("CS", device.chip_select),
            )
            device_pin_issues = [
                f"{role}: {issue}"
                for role, pin in device_pin_requirements
                if (issue := pin_disposition(pin)) is not None
            ]
            if isinstance(
                device.miso, (SpiMisoConnectedRequirement, SpiPinUnconnectedRequirement)
            ) and (issue := pin_disposition(device.miso)):
                device_pin_issues.append(f"MISO: {issue}")
            results.append(
                ElectricalCheck(
                    id=f"{device_base}/pins",
                    status="FAIL" if device_pin_issues else "PASS",
                    detail=(
                        "; ".join(device_pin_issues)
                        if device_pin_issues
                        else "Declared SCK, MOSI, MISO disposition, and chip-select pin assignments match."
                    ),
                )
            )
            add_route(device.id, "sck", controller.sck.net, device.sck.net)
            add_route(device.id, "mosi", controller.mosi.net, device.mosi.net)
            if isinstance(device.miso, SpiMisoConnectedRequirement):
                if isinstance(controller.miso, SpiMisoConnectedRequirement):
                    add_route(device.id, "miso", controller.miso.net, device.miso.net)
            else:
                reason = (
                    device.miso.reason
                    if isinstance(device.miso, SpiPinNotPresent)
                    else "Device MISO is declared unconnected."
                )
                results.append(
                    ElectricalCheck(
                        id=f"{device_base}/route/miso",
                        status="NOT_APPLICABLE",
                        detail=f"No device MISO return route is required: {reason}",
                    )
                )
    return tuple(results)
