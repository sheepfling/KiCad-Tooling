"""Review source coverage for I2C pull-up voltage compatibility."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Literal

from .i2c_addressing import unmapped_i2c_responders
from .i2c_pullup_models import I2cPullupAnalysis
from .i2c_pullup_voltage_models import I2cPullupVoltageCoverageEntry
from .models import ElectricalCheck, NetlistContract
from .resistor_array_paths import (
    ResistorArrayNetlistEvidence,
    resistor_array_channel_issue,
    resistor_array_component_issues,
)
from .resistor_paths import (
    VISIBLE_PULLUP_MAX_OHMS,
    VISIBLE_PULLUP_MIN_OHMS,
    visible_resistor_pullups,
)


def i2c_pullup_voltage_coverage(
    observed: NetlistContract,
    *,
    state: str,
    spec: I2cPullupAnalysis | None = None,
    checks_by_id: Mapping[str, ElectricalCheck] | None = None,
) -> tuple[I2cPullupVoltageCoverageEntry, ...]:
    """Find fitted I2C pins on locally pulled-up lines without exact input limits.

    This only measures authored coverage. It does not infer a pin's voltage
    tolerance, a rail voltage, or whether a reported connection is unsafe.
    """
    pin_nets: dict[str, set[str]] = defaultdict(set)
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets[pin.casefold()].add(net)

    pin_inventory = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }

    endpoint_pins: dict[tuple[str, str], dict[str, set[str]]] = {}
    net_names: dict[tuple[str, str], tuple[str, str]] = {}
    for responder in unmapped_i2c_responders(observed, None):
        if len(responder.sda_pins) != 1 or len(responder.scl_pins) != 1:
            continue
        known_numbers = pin_inventory.get(responder.reference.casefold())
        if known_numbers is None or any(
            pin.rsplit(".", 1)[-1].casefold() not in known_numbers
            for pin in (*responder.sda_pins, *responder.scl_pins)
        ):
            continue
        for sda_net, scl_net in responder.signal_pairs:
            pair = (sda_net.casefold(), scl_net.casefold())
            sda_pins = {
                pin
                for pin in responder.sda_pins
                if {net.casefold() for net in pin_nets.get(pin.casefold(), set())}
                == {sda_net.casefold()}
            }
            scl_pins = {
                pin
                for pin in responder.scl_pins
                if {net.casefold() for net in pin_nets.get(pin.casefold(), set())}
                == {scl_net.casefold()}
            }
            if not sda_pins or not scl_pins:
                continue
            net_names.setdefault(pair, (sda_net, scl_net))
            signals = endpoint_pins.setdefault(pair, {"SDA": set(), "SCL": set()})
            signals["SDA"].update(sda_pins)
            signals["SCL"].update(scl_pins)

    pullup_names_by_net: dict[str, str] = {}
    pullup_rails_by_net: dict[str, set[str]] = {}
    for net, paths in visible_resistor_pullups(observed, include_device_r_symbol=True).items():
        if not paths:
            continue
        key = net.casefold()
        pullup_names_by_net[key] = net
        pullup_rails_by_net.setdefault(key, set()).update(path.rail_net for path in paths)

    if state == "required" and spec is not None:
        for key, (signal_net, rails) in _source_bound_array_pullups(observed, spec).items():
            pullup_names_by_net.setdefault(key, signal_net)
            pullup_rails_by_net.setdefault(key, set()).update(rails)

    pullups_by_net = {
        key: (
            pullup_names_by_net[key],
            tuple(sorted(rails, key=lambda item: (item.casefold(), item))),
        )
        for key, rails in pullup_rails_by_net.items()
    }
    exact_buses = () if state != "required" or spec is None else spec.buses
    entries: list[I2cPullupVoltageCoverageEntry] = []

    for pair in sorted(endpoint_pins):
        sda_net, scl_net = net_names[pair]
        lines = {"SDA": sda_net, "SCL": scl_net}
        for line_name in ("SDA", "SCL"):
            signal_net = lines[line_name]
            pullup = pullups_by_net.get(signal_net.casefold())
            if pullup is None:
                continue
            pins = tuple(
                sorted(endpoint_pins[pair][line_name], key=lambda item: (item.casefold(), item))
            )
            matching = [
                bus
                for bus in exact_buses
                if bus.sda.net.casefold() == pair[0] and bus.scl.net.casefold() == pair[1]
            ]
            issues: list[str] = []
            bus_id: str | None = None
            covered: tuple[str, ...] = ()
            missing = pins
            if state != "required" or spec is None:
                reason = {
                    "pending": "the project I2C pull-up review is pending",
                    "not_applicable": "the project marks I2C pull-up analysis not applicable",
                    "blocked": "the project I2C pull-up contract could not be loaded or verified",
                }.get(state, "no project-authored I2C pull-up voltage requirement is configured")
                issues.append(f"Review exact input-voltage limits for {', '.join(pins)}; {reason}.")
            elif len(matching) != 1:
                issues.append(
                    "No unique project I2C pull-up requirement covers this exact ordered "
                    f"SDA/SCL pair ({sda_net} / {scl_net})."
                )
            else:
                bus = matching[0]
                bus_id = bus.id
                line_requirement = bus.sda if line_name == "SDA" else bus.scl
                voltage_requirement = line_requirement.voltage_compatibility
                if voltage_requirement is None:
                    issues.append(
                        f"No exact maximum input-voltage map covers {line_name} on {signal_net}."
                    )
                else:
                    limit_pins = {
                        item.pin.casefold(): item.pin for item in voltage_requirement.input_limits
                    }
                    covered = tuple(pin for pin in pins if pin.casefold() in limit_pins)
                    covered_keys = {pin.casefold() for pin in covered}
                    missing = tuple(pin for pin in pins if pin.casefold() not in covered_keys)
                    if missing:
                        issues.append(
                            f"The authored {line_name} voltage map omits fitted endpoint pins: "
                            f"{', '.join(missing)}."
                        )
                    line_check_id = f"i2c-pullup/{bus.id}/{line_name.casefold()}"
                    line_check = (
                        checks_by_id.get(line_check_id) if checks_by_id is not None else None
                    )
                    if line_check is None:
                        issues.append(
                            f"The authored {line_name} pull-up check did not produce "
                            "source-bound evidence."
                        )
                    elif line_check.status != "PASS":
                        issues.append(
                            f"The authored {line_name} pull-up check did not pass: "
                            f"{line_check.detail}"
                        )
                    check_id = f"i2c-pullup/{bus.id}/{line_name.casefold()}/voltage-compatibility"
                    check = checks_by_id.get(check_id) if checks_by_id is not None else None
                    if check is None:
                        issues.append(
                            f"The authored {line_name} voltage-compatibility check "
                            "did not produce source-bound evidence."
                        )
                    elif check.status != "PASS":
                        issues.append(
                            f"The authored {line_name} voltage-compatibility check did not pass: "
                            f"{check.detail}"
                        )

            status: Literal["COVERED", "OPEN"] = "OPEN" if issues else "COVERED"
            entries.append(
                I2cPullupVoltageCoverageEntry(
                    status=status,
                    bus_id=bus_id,
                    sda_net=sda_net,
                    scl_net=scl_net,
                    line=line_name,
                    signal_net=pullup[0],
                    pullup_rails=pullup[1],
                    endpoint_pins=pins,
                    covered_input_pins=covered,
                    missing_input_pins=missing,
                    issues=tuple(issues),
                )
            )

    return tuple(entries)


def _source_bound_array_pullups(
    observed: NetlistContract, spec: I2cPullupAnalysis
) -> dict[str, tuple[str, set[str]]]:
    """Return only fitted, exact-mapped array channels inside the visible range."""
    array_evidence = ResistorArrayNetlistEvidence.from_netlist(observed)

    line_pairs = {(line.net, line.rail) for bus in spec.buses for line in (bus.sda, bus.scl)}
    pullups: dict[str, tuple[str, set[str]]] = {}
    for array in spec.arrays:
        if resistor_array_component_issues(
            array_evidence,
            reference=array.reference,
            expected_symbol=array.expected_symbol,
            expected_footprint=array.expected_footprint,
            expected_value=array.expected_value,
            expected_part_id=array.expected_part_id,
            channel_pins=tuple(
                (channel.signal_pin, channel.rail_pin) for channel in array.channels
            ),
            unmapped_pin_reasons=array.unmapped_pin_reasons,
            component_kind="mapped pull-up channel",
        ):
            continue
        for channel in array.channels:
            if (channel.signal_net, channel.rail_net) not in line_pairs:
                continue
            if not VISIBLE_PULLUP_MIN_OHMS <= channel.resistance_ohms <= VISIBLE_PULLUP_MAX_OHMS:
                continue
            if (
                resistor_array_channel_issue(
                    array_evidence,
                    reference=array.reference,
                    channel_id=channel.id,
                    pin_a=channel.signal_pin,
                    pin_b=channel.rail_pin,
                    net_a=channel.signal_net,
                    net_b=channel.rail_net,
                )
                is not None
            ):
                continue
            key = channel.signal_net.casefold()
            pullups.setdefault(key, (channel.signal_net, set()))[1].add(channel.rail_net)
    return pullups
