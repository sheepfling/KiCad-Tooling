"""I2c pullup heuristics for deterministic KiCad bus analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .bus_signal_roles import i2c_signal_role
from .i2c_pullup_contract import i2c_pullup_checks
from .i2c_pullup_models import (
    I2cPullupAnalysis,
    I2cPullupHeuristicCoverage,
    I2cPullupHeuristicEntry,
    I2cPullupLineRequirement,
)
from .models import NetlistContract
from .resistor_paths import (
    positive_power_net_families,
    visible_resistor_pullups,
)


@dataclass(frozen=True)
class I2cPullupGap:
    sda_net: str
    scl_net: str
    sda_pins: tuple[str, ...]
    scl_pins: tuple[str, ...]
    missing_lines: tuple[Literal["SDA", "SCL"], ...]


@dataclass(frozen=True)
class I2cLowEquivalentResistance:
    sda_net: str
    scl_net: str
    lines: tuple[str, ...]
    pins: dict[str, tuple[str, ...]]
    resistors: dict[str, tuple[str, ...]]
    equivalent_ohms: dict[str, str]


@dataclass(frozen=True)
class I2cMultiplePullupRailFamilies:
    sda_net: str
    scl_net: str
    pins: tuple[str, ...]
    rail_families: tuple[str, ...]
    pullup_paths: tuple[str, ...]


def i2c_buses_without_local_pullups(observed: NetlistContract) -> tuple[I2cPullupGap, ...]:
    """Find named SDA/SCL pairs without a 1 kΩ–100 kΩ path to a named rail."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    signal_pins: dict[str, dict[str, set[str]]] = {}
    for pin, function in observed.pin_functions.items():
        role = i2c_signal_role(function)
        if role is None:
            continue
        reference = pin.rsplit(".", 1)[0]
        signal_pins.setdefault(reference, {}).setdefault(role, set()).add(pin)

    buses: dict[tuple[str, str], dict[str, set[str]]] = {}
    for roles in signal_pins.values():
        if not {"SDA", "SCL"}.issubset(roles):
            continue
        sda_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SDA"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        scl_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SCL"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        for sda_pin, sda_net in sda_assignments:
            for scl_pin, scl_net in scl_assignments:
                if sda_net == scl_net:
                    continue
                evidence = buses.setdefault((sda_net, scl_net), {"SDA": set(), "SCL": set()})
                evidence["SDA"].add(sda_pin)
                evidence["SCL"].add(scl_pin)

    pullup_nets = set(visible_resistor_pullups(observed))

    gaps: list[I2cPullupGap] = []
    for (sda_net, scl_net), evidence in sorted(buses.items()):
        missing_lines: list[Literal["SDA", "SCL"]] = []
        if sda_net not in pullup_nets:
            missing_lines.append("SDA")
        if scl_net not in pullup_nets:
            missing_lines.append("SCL")
        missing = tuple(missing_lines)
        if missing:
            gaps.append(
                I2cPullupGap(
                    sda_net=sda_net,
                    scl_net=scl_net,
                    sda_pins=tuple(sorted(evidence["SDA"])),
                    scl_pins=tuple(sorted(evidence["SCL"])),
                    missing_lines=missing,
                )
            )
    return tuple(gaps)


def i2c_pullup_heuristic_coverage(
    observed: NetlistContract,
    *,
    netlist_sha256: str,
    source_path: str | None,
    source_sha256: str | None,
    state: str,
    spec: I2cPullupAnalysis | None = None,
) -> I2cPullupHeuristicCoverage:
    """Resolve only exact missing-line hints with passing authored pull-up checks."""
    gaps = i2c_buses_without_local_pullups(observed)
    if spec is None:
        reason = {
            "pending": "Project I2C pull-up review is pending; no requirement can resolve this prompt.",
            "not_applicable": "The project marks I2C pull-up analysis not applicable; no net-specific requirement resolves this prompt.",
            "blocked": "The project I2C pull-up requirement could not be loaded.",
        }.get(state, "No project-authored I2C pull-up requirement covers this candidate.")
        entries: list[I2cPullupHeuristicEntry] = [
            I2cPullupHeuristicEntry(
                sda_net=gap.sda_net,
                scl_net=gap.scl_net,
                missing_lines=gap.missing_lines,
                status="OPEN",
                issues=(reason,),
            )
            for gap in gaps
        ]
        status_by_state: dict[
            str,
            Literal["NOT_CONFIGURED", "PENDING", "NOT_APPLICABLE", "COMPLETE", "OPEN", "BLOCKED"],
        ] = {
            "pending": "PENDING",
            "not_applicable": "NOT_APPLICABLE",
            "blocked": "BLOCKED",
        }
        status = status_by_state.get(state, "NOT_CONFIGURED")
        return I2cPullupHeuristicCoverage(
            status=status,
            source_path=source_path,
            source_sha256=source_sha256,
            netlist_sha256=netlist_sha256 if gaps else None,
            entries=tuple(entries),
            issue=(reason if state == "blocked" else None),
        )

    checks_by_id = {check.id: check for check in i2c_pullup_checks(spec, observed)}
    entries: list[I2cPullupHeuristicEntry] = []
    for gap in gaps:
        matching = [
            bus
            for bus in spec.buses
            if bus.sda.net.casefold() == gap.sda_net.casefold()
            and bus.scl.net.casefold() == gap.scl_net.casefold()
        ]
        if len(matching) != 1:
            issue = (
                "No I2C pull-up requirement names this exact ordered SDA/SCL net pair."
                if not matching
                else "More than one I2C pull-up requirement names this exact ordered SDA/SCL net pair."
            )
            entries.append(
                I2cPullupHeuristicEntry(
                    sda_net=gap.sda_net,
                    scl_net=gap.scl_net,
                    missing_lines=gap.missing_lines,
                    status="OPEN",
                    issues=(issue,),
                )
            )
            continue

        bus = matching[0]
        required_check_ids: list[str] = []
        issues: list[str] = []
        lines: dict[str, I2cPullupLineRequirement] = {"SDA": bus.sda, "SCL": bus.scl}
        for line_name in ("SDA", "SCL"):
            line = lines[line_name]
            check_id = f"i2c-pullup/{bus.id}/{line_name.casefold()}"
            required_check_ids.append(check_id)
            check = checks_by_id.get(check_id)
            if check is None:
                issues.append(f"{line_name}: the authored pull-up check did not produce evidence.")
            elif check.status != "PASS":
                issues.append(f"{line_name}: {check.detail}")

            if line.voltage_compatibility is not None:
                voltage_id = f"{check_id}/voltage-compatibility"
                required_check_ids.append(voltage_id)
                voltage_check = checks_by_id.get(voltage_id)
                if voltage_check is None:
                    issues.append(
                        f"{line_name}: the authored voltage-compatibility check did not produce evidence."
                    )
                elif voltage_check.status != "PASS":
                    issues.append(f"{line_name} voltage compatibility: {voltage_check.detail}")

        entries.append(
            I2cPullupHeuristicEntry(
                sda_net=gap.sda_net,
                scl_net=gap.scl_net,
                missing_lines=gap.missing_lines,
                status="OPEN" if issues else "COVERED",
                bus_id=bus.id,
                check_ids=tuple(required_check_ids),
                issues=tuple(issues),
            )
        )

    coverage_status = "OPEN" if any(entry.status == "OPEN" for entry in entries) else "COMPLETE"
    return I2cPullupHeuristicCoverage(
        status=coverage_status,
        source_path=source_path,
        source_sha256=source_sha256,
        netlist_sha256=netlist_sha256 if gaps else None,
        entries=tuple(entries),
    )


def i2c_buses_with_low_equivalent_pullup_resistance(
    observed: NetlistContract,
) -> tuple[I2cLowEquivalentResistance, ...]:
    """Find direct fitted pull-ups whose nominal parallel resistance is below 1 kΩ."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    signal_pins: dict[str, dict[str, set[str]]] = {}
    for pin, function in observed.pin_functions.items():
        role = i2c_signal_role(function)
        if role is None:
            continue
        reference = pin.rsplit(".", 1)[0]
        signal_pins.setdefault(reference, {}).setdefault(role, set()).add(pin)

    buses: dict[tuple[str, str], dict[str, set[str]]] = {}
    for roles in signal_pins.values():
        if not {"SDA", "SCL"}.issubset(roles):
            continue
        sda_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SDA"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        scl_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SCL"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        for sda_pin, sda_net in sda_assignments:
            for scl_pin, scl_net in scl_assignments:
                if sda_net == scl_net:
                    continue
                evidence = buses.setdefault((sda_net, scl_net), {"SDA": set(), "SCL": set()})
                evidence["SDA"].add(sda_pin)
                evidence["SCL"].add(scl_pin)

    visible_pullups = visible_resistor_pullups(observed)
    findings: list[I2cLowEquivalentResistance] = []
    for (sda_net, scl_net), evidence in sorted(buses.items()):
        affected: list[str] = []
        resistors: dict[str, tuple[str, ...]] = {}
        equivalents: dict[str, str] = {}
        for line, net in (("SDA", sda_net), ("SCL", scl_net)):
            paths = tuple(
                sorted(
                    visible_pullups.get(net, ()), key=lambda item: (item.rail_net, item.references)
                )
            )
            if not paths or len({item.rail_net for item in paths}) != 1:
                continue
            equivalent = 1 / sum(1 / item.resistance_ohms for item in paths)
            if equivalent >= 1_000:
                continue
            affected.append(line)
            equivalents[line] = f"{equivalent:.6g}"
            resistors[line] = tuple(
                f"{' + '.join(item.references)}={item.resistance_ohms:.6g}Ω to {item.rail_net}"
                for item in paths
            )
        if affected:
            findings.append(
                I2cLowEquivalentResistance(
                    sda_net=sda_net,
                    scl_net=scl_net,
                    lines=tuple(affected),
                    pins={line: tuple(sorted(evidence[line])) for line in ("SDA", "SCL")},
                    resistors=resistors,
                    equivalent_ohms=equivalents,
                )
            )
    return tuple(findings)


def i2c_buses_with_multiple_pullup_rail_families(
    observed: NetlistContract,
) -> tuple[I2cMultiplePullupRailFamilies, ...]:
    """Review an I2C bus whose visible pull-ups use distinct recognized rail families."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    dnp = {reference.casefold() for reference in observed.dnp_components}
    signal_pins: dict[str, dict[str, set[str]]] = {}
    for pin, function in observed.pin_functions.items():
        if pin.rsplit(".", 1)[0].casefold() in dnp:
            continue
        role = i2c_signal_role(function)
        if role is None:
            continue
        reference = pin.rsplit(".", 1)[0]
        signal_pins.setdefault(reference, {}).setdefault(role, set()).add(pin)

    buses: dict[tuple[str, str], dict[str, set[str]]] = {}
    for roles in signal_pins.values():
        if not {"SDA", "SCL"}.issubset(roles):
            continue
        sda_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SDA"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        scl_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["SCL"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        for sda_pin, sda_net in sda_assignments:
            for scl_pin, scl_net in scl_assignments:
                if sda_net == scl_net:
                    continue
                evidence = buses.setdefault((sda_net, scl_net), {"SDA": set(), "SCL": set()})
                evidence["SDA"].add(sda_pin)
                evidence["SCL"].add(scl_pin)

    visible_pullups = visible_resistor_pullups(observed)
    rail_families_by_net = positive_power_net_families(observed)
    findings: list[I2cMultiplePullupRailFamilies] = []
    for (sda_net, scl_net), bus_pins in sorted(buses.items()):
        families: set[str] = set()
        paths: set[str] = set()
        for line, net in (("SDA", sda_net), ("SCL", scl_net)):
            for path in visible_pullups.get(net, ()):
                family = rail_families_by_net.get(path.rail_net)
                if family is None:
                    continue
                families.add(family)
                references = " + ".join(path.references)
                paths.add(
                    f"{line}: {references}={path.resistance_ohms:g}Ω to {path.rail_net} ({family})"
                )
        if len(families) < 2:
            continue
        findings.append(
            I2cMultiplePullupRailFamilies(
                sda_net=sda_net,
                scl_net=scl_net,
                pins=tuple(sorted((*bus_pins["SDA"], *bus_pins["SCL"]))),
                rail_families=tuple(sorted(families)),
                pullup_paths=tuple(sorted(paths)),
            )
        )
    return tuple(findings)
