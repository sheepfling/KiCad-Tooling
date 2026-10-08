"""Source-bound comparison for explicit external-interface protection maps."""

from __future__ import annotations

from .models import (
    ComponentContract,
    ConnectorCoverageReport,
    ExternalProtectionCoverageEntry,
    ExternalProtectionCoverageReport,
    ExternalProtectionDeviceRequirement,
    ExternalProtectionMap,
    NetlistContract,
)


def _device_issues(
    requirement: ExternalProtectionDeviceRequirement,
    components: dict[str, tuple[str, ComponentContract]],
    symbols: dict[str, str],
    pin_numbers: dict[str, set[str]],
    pin_nets: dict[str, set[str]],
    dnp: set[str],
) -> tuple[str, ...]:
    key = requirement.reference.casefold()
    issues: list[str] = []
    component_entry = components.get(key)
    if component_entry is None:
        issues.append(f"{requirement.reference} is absent from the native netlist")
    else:
        _, component = component_entry
        if component.footprint != requirement.expected_footprint:
            issues.append(
                f"{requirement.reference} footprint is {component.footprint or 'empty'}; "
                f"expected {requirement.expected_footprint}"
            )
    observed_symbol = symbols.get(key)
    if observed_symbol != requirement.expected_symbol:
        issues.append(
            f"{requirement.reference} symbol is {observed_symbol or 'unknown'}; "
            f"expected {requirement.expected_symbol}"
        )
    if key in dnp:
        issues.append(f"{requirement.reference} is DNP but a protection channel is required")

    inventory = pin_numbers.get(key)
    if inventory is None:
        issues.append(f"{requirement.reference} has no native symbol pin inventory")
    else:
        expected_numbers = {pin.rsplit(".", 1)[1].casefold() for pin in requirement.pin_nets}
        expected_numbers.update(
            pin.rsplit(".", 1)[1].casefold() for pin in requirement.unmapped_pin_reasons
        )
        missing = tuple(sorted(expected_numbers - inventory))
        unaccounted = tuple(sorted(inventory - expected_numbers))
        if missing:
            issues.append(f"{requirement.reference} mapped pins are absent: {missing}")
        if unaccounted:
            issues.append(f"{requirement.reference} has unreviewed pins: {unaccounted}")

    for pin, expected_net in requirement.pin_nets.items():
        assigned = pin_nets.get(pin.casefold(), set())
        if assigned != {expected_net}:
            issues.append(
                f"{pin} is on {', '.join(sorted(assigned)) or 'unconnected'}; "
                f"expected {expected_net}"
            )
    return tuple(issues)


def evaluate(
    requirements: ExternalProtectionMap | None,
    observed: NetlistContract,
    connector_coverage: ConnectorCoverageReport | None,
    netlist_sha256: str | None,
    *,
    handled_by_existing_contract: dict[str, str] | None = None,
    electrical_contract_path: str | None = None,
    electrical_contract_sha256: str | None = None,
) -> ExternalProtectionCoverageReport:
    """Compare explicit connector protection decisions with native netlist evidence."""
    handled = {
        pin.casefold(): (pin, net) for pin, net in (handled_by_existing_contract or {}).items()
    }
    requirements_by_pin = (
        {}
        if requirements is None
        else {item.connector_pin.casefold(): item for item in requirements.interfaces}
    )
    interface_pins: dict[str, tuple[str, str, tuple[str, ...], str]] = {}
    if connector_coverage is not None:
        for connector in connector_coverage.entries:
            if connector.status != "COVERED":
                continue
            for pin in connector.mapped_pins:
                interface_pins[pin.component_pin.casefold()] = (
                    connector.reference,
                    pin.interface_signal,
                    pin.nets,
                    pin.component_pin,
                )

    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    devices = (
        {}
        if requirements is None
        else {item.reference.casefold(): item for item in requirements.devices}
    )
    entries: list[ExternalProtectionCoverageEntry] = []
    all_pins = set(interface_pins) | set(requirements_by_pin)
    device_issue_cache: dict[str, tuple[str, ...]] = {}

    for pin_key in sorted(all_pins | set(handled)):
        connector_reference, interface_signal, observed_nets, display_pin = interface_pins.get(
            pin_key,
            (
                requirements_by_pin[pin_key].connector_reference
                if pin_key in requirements_by_pin
                else pin_key.rsplit(".", 1)[0],
                None,
                (),
                requirements_by_pin[pin_key].connector_pin
                if pin_key in requirements_by_pin
                else next(
                    (
                        pin
                        for pin, _ in (handled_by_existing_contract or {}).items()
                        if pin.casefold() == pin_key
                    ),
                    pin_key,
                ),
            ),
        )
        requirement = requirements_by_pin.get(pin_key)
        if pin_key in handled:
            if requirement is None:
                entries.append(
                    ExternalProtectionCoverageEntry(
                        connector_reference=connector_reference,
                        connector_pin=display_pin,
                        interface_signal=interface_signal,
                        signal_net=handled[pin_key][1],
                        observed_nets=observed_nets,
                        status="HANDLED_BY_EXISTING_CONTRACT",
                        basis="Protection disposition is owned by the existing USB-C electrical contract.",
                    )
                )
            else:
                entries.append(
                    ExternalProtectionCoverageEntry(
                        connector_reference=connector_reference,
                        connector_pin=display_pin,
                        interface_signal=interface_signal,
                        signal_net=requirement.signal_net,
                        observed_nets=observed_nets,
                        status="INCOMPLETE",
                        basis=requirement.basis,
                        issues=(
                            "This connector pin is already covered by the USB-C electrical contract; "
                            + "remove the duplicate external-protection map entry.",
                        ),
                    )
                )
            continue

        if requirement is None:
            entries.append(
                ExternalProtectionCoverageEntry(
                    connector_reference=connector_reference,
                    connector_pin=display_pin,
                    interface_signal=interface_signal,
                    observed_nets=observed_nets,
                    status="UNDECLARED",
                    issues=(
                        "No protection requirement or reasoned not-required decision is recorded",
                    ),
                )
            )
            continue

        issues: list[str] = []
        reference_key = requirement.connector_reference.casefold()
        component_entry = components.get(reference_key)
        if component_entry is None:
            issues.append(f"{requirement.connector_reference} is absent from the native netlist")
        else:
            _, component = component_entry
            if component.footprint != requirement.expected_connector_footprint:
                issues.append(
                    f"{requirement.connector_reference} footprint is "
                    f"{component.footprint or 'empty'}; expected "
                    f"{requirement.expected_connector_footprint}"
                )
        observed_symbol = symbols.get(reference_key)
        if observed_symbol != requirement.expected_connector_symbol:
            issues.append(
                f"{requirement.connector_reference} symbol is {observed_symbol or 'unknown'}; "
                f"expected {requirement.expected_connector_symbol}"
            )
        connector_inventory = pin_numbers.get(reference_key)
        pin_number = requirement.connector_pin.rsplit(".", 1)[1].casefold()
        if connector_inventory is None:
            issues.append(f"{requirement.connector_reference} has no native symbol pin inventory")
        elif pin_number not in connector_inventory:
            issues.append(f"{requirement.connector_pin} is absent from the native symbol inventory")
        connector_nets = pin_nets.get(requirement.connector_pin.casefold(), set())
        if connector_nets != {requirement.signal_net}:
            issues.append(
                f"{requirement.connector_pin} is on "
                f"{', '.join(sorted(connector_nets)) or 'unconnected'}; "
                f"expected {requirement.signal_net}"
            )

        if requirement.disposition == "not_required":
            status = "INCOMPLETE" if issues else "NOT_REQUIRED"
            references: tuple[str, ...] = ()
        else:
            references = tuple(sorted({item.device_reference for item in requirement.channels}))
            for channel in requirement.channels:
                device_key = channel.device_reference.casefold()
                if device_key not in device_issue_cache:
                    device = devices.get(device_key)
                    device_issue_cache[device_key] = (
                        (f"{channel.device_reference} has no authored device identity",)
                        if device is None
                        else _device_issues(
                            device,
                            components,
                            symbols,
                            pin_numbers,
                            pin_nets,
                            dnp,
                        )
                    )
                issues.extend(device_issue_cache[device_key])
            status = "INCOMPLETE" if issues else "PROTECTED"
        entries.append(
            ExternalProtectionCoverageEntry(
                connector_reference=requirement.connector_reference,
                connector_pin=display_pin,
                interface_signal=interface_signal,
                signal_net=requirement.signal_net,
                observed_nets=tuple(sorted(connector_nets)),
                status=status,
                basis=requirement.basis,
                device_references=references,
                issues=tuple(dict.fromkeys(issues)),
            )
        )

    if not entries:
        return ExternalProtectionCoverageReport(
            status="NOT_REQUESTED",
            netlist_sha256=netlist_sha256,
            electrical_contract_path=electrical_contract_path,
            electrical_contract_sha256=electrical_contract_sha256,
        )
    if netlist_sha256 is None:
        return ExternalProtectionCoverageReport(
            status="BLOCKED",
            electrical_contract_path=electrical_contract_path,
            electrical_contract_sha256=electrical_contract_sha256,
            issue="Source-bound native netlist hash is unavailable for protection coverage",
        )
    if any(item.status in {"INCOMPLETE", "STALE"} for item in entries):
        status = "INCOMPLETE"
    elif any(item.status == "UNDECLARED" for item in entries):
        status = "UNDECLARED"
    else:
        status = "COMPLETE"
    return ExternalProtectionCoverageReport(
        status=status,
        netlist_sha256=netlist_sha256,
        electrical_contract_path=electrical_contract_path,
        electrical_contract_sha256=electrical_contract_sha256,
        entries=tuple(entries),
    )
