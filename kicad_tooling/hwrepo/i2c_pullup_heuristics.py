"""I2c pullup heuristics for deterministic KiCad bus analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .bus_signal_roles import i2c_signal_role
from .i2c_pullup_contract import i2c_pullup_checks
from .i2c_pullup_models import (
    I2cPullupAnalysis,
    I2cPullupHeuristicCoverage,
    I2cPullupHeuristicEntry,
    I2cPullupLineRequirement,
)
from .i2c_pullup_voltage_coverage import i2c_pullup_voltage_coverage
from .models import Digest
from .netlist_contract_models import NetlistContract
from .resistor_paths import (
    VisibleResistorPath,
    positive_power_net_families,
    visible_resistor_pullups,
)


@dataclass(frozen=True, slots=True)
class I2cPullupGap:
    sda_net: str
    scl_net: str
    sda_pins: tuple[str, ...]
    scl_pins: tuple[str, ...]
    missing_lines: tuple[Literal["SDA", "SCL"], ...]


@dataclass(frozen=True, slots=True)
class I2cBusPinAssignments:
    """One uniquely assigned I2C bus pair and its observed signal pins."""

    sda_net: str
    scl_net: str
    sda_pins: tuple[str, ...]
    scl_pins: tuple[str, ...]


def _new_i2c_pin_set() -> set[str]:
    return set()


@dataclass(slots=True)
class _I2cPinRoleAccumulator:
    """Mutable local collection for one component or observed bus pair."""

    sda_pins: set[str] = field(default_factory=_new_i2c_pin_set)
    scl_pins: set[str] = field(default_factory=_new_i2c_pin_set)


@dataclass(frozen=True, slots=True)
class I2cLowEquivalentLineEvidence:
    line: Literal["SDA", "SCL"]
    pullup_paths: tuple[VisibleResistorPath, ...]
    equivalent_resistance_ohms: float


@dataclass(frozen=True, slots=True)
class I2cLowEquivalentResistanceObservation:
    sda_net: str
    scl_net: str
    sda_pins: tuple[str, ...]
    scl_pins: tuple[str, ...]
    lines: tuple[I2cLowEquivalentLineEvidence, ...]


@dataclass(frozen=True, slots=True)
class I2cPullupCoverageRequest:
    """Supplied pull-up coverage and the current netlist identity."""

    coverage: I2cPullupHeuristicCoverage | None
    current_netlist_sha256: Digest | None


@dataclass(frozen=True, slots=True)
class I2cPullupCoverageResolution:
    """Coverage admitted for this netlist, with any binding issue retained."""

    coverage: I2cPullupHeuristicCoverage | None
    binding_issue: str | None


@dataclass(frozen=True, slots=True)
class I2cMultiplePullupRailFamilies:
    sda_net: str
    scl_net: str
    pins: tuple[str, ...]
    rail_families: tuple[str, ...]
    pullup_paths: tuple[str, ...]


def _i2c_bus_pin_assignments(
    observed: NetlistContract,
    *,
    exclude_dnp_references: bool = False,
) -> tuple[I2cBusPinAssignments, ...]:
    """Build the shared bus index without passing role-keyed maps downstream."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    dnp_references: set[str] = (
        {reference.casefold() for reference in observed.dnp_components}
        if exclude_dnp_references
        else set()
    )
    signal_pins_by_reference: dict[str, _I2cPinRoleAccumulator] = {}
    for pin, function in observed.pin_functions.items():
        reference = pin.rsplit(".", 1)[0]
        if reference.casefold() in dnp_references:
            continue
        role = i2c_signal_role(function)
        if role is None:
            continue
        role_pins = signal_pins_by_reference.setdefault(reference, _I2cPinRoleAccumulator())
        if role == "SDA":
            role_pins.sda_pins.add(pin)
        elif role == "SCL":
            role_pins.scl_pins.add(pin)

    bus_pins_by_net_pair: dict[tuple[str, str], _I2cPinRoleAccumulator] = {}
    for role_pins in signal_pins_by_reference.values():
        if not role_pins.sda_pins or not role_pins.scl_pins:
            continue
        sda_assignments = tuple(
            (pin, next(iter(nets)))
            for pin in role_pins.sda_pins
            if len(nets := pin_nets.get(pin, set())) == 1
        )
        scl_assignments = tuple(
            (pin, next(iter(nets)))
            for pin in role_pins.scl_pins
            if len(nets := pin_nets.get(pin, set())) == 1
        )
        for sda_pin, sda_net in sda_assignments:
            for scl_pin, scl_net in scl_assignments:
                if sda_net == scl_net:
                    continue
                bus_pins = bus_pins_by_net_pair.setdefault(
                    (sda_net, scl_net), _I2cPinRoleAccumulator()
                )
                bus_pins.sda_pins.add(sda_pin)
                bus_pins.scl_pins.add(scl_pin)

    return tuple(
        I2cBusPinAssignments(
            sda_net=sda_net,
            scl_net=scl_net,
            sda_pins=tuple(sorted(role_pins.sda_pins)),
            scl_pins=tuple(sorted(role_pins.scl_pins)),
        )
        for (sda_net, scl_net), role_pins in sorted(bus_pins_by_net_pair.items())
    )


def i2c_buses_without_local_pullups(observed: NetlistContract) -> tuple[I2cPullupGap, ...]:
    """Find named SDA/SCL pairs without a 1 kΩ–100 kΩ path to a named rail."""
    pullup_nets = set(visible_resistor_pullups(observed, include_device_r_symbol=True))

    gaps: list[I2cPullupGap] = []
    for bus in _i2c_bus_pin_assignments(observed):
        missing_lines: list[Literal["SDA", "SCL"]] = []
        if bus.sda_net not in pullup_nets:
            missing_lines.append("SDA")
        if bus.scl_net not in pullup_nets:
            missing_lines.append("SCL")
        missing = tuple(missing_lines)
        if missing:
            gaps.append(
                I2cPullupGap(
                    sda_net=bus.sda_net,
                    scl_net=bus.scl_net,
                    sda_pins=bus.sda_pins,
                    scl_pins=bus.scl_pins,
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
    """Resolve missing-pull-up hints and collect input-limit coverage evidence."""
    gaps = i2c_buses_without_local_pullups(observed)
    checks_by_id = (
        {check.id: check for check in i2c_pullup_checks(spec, observed)} if spec is not None else {}
    )
    voltage_entries = i2c_pullup_voltage_coverage(
        observed,
        state=state,
        spec=spec,
        checks_by_id=checks_by_id,
    )
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
            netlist_sha256=netlist_sha256 if gaps or voltage_entries else None,
            entries=tuple(entries),
            voltage_entries=voltage_entries,
            issue=(reason if state == "blocked" else None),
        )

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

            if line.electrical_window is not None:
                window_suffixes = [
                    "minimum-sink-resistance",
                    "maximum-rise-resistance",
                ]
                if line.electrical_window.resistor_tolerances:
                    window_suffixes.append("tolerance-scope")
                if line.electrical_window.capacitance_scope is not None:
                    window_suffixes.append("capacitance-scope")
                for suffix in window_suffixes:
                    window_id = f"{check_id}/electrical-window/{suffix}"
                    required_check_ids.append(window_id)
                    window_check = checks_by_id.get(window_id)
                    if window_check is None:
                        issues.append(
                            f"{line_name}: the authored electrical-window check "
                            f"{suffix} did not produce evidence."
                        )
                    elif window_check.status != "PASS":
                        issues.append(
                            f"{line_name} electrical window ({suffix}): {window_check.detail}"
                        )

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
        # COMPLETE with no hint entries still asserts that this netlist was scanned.
        netlist_sha256=netlist_sha256,
        entries=tuple(entries),
        voltage_entries=voltage_entries,
    )


def i2c_pullup_coverage_issue(
    coverage: I2cPullupHeuristicCoverage,
    current_netlist_sha256: str | None,
) -> str | None:
    """Reject I2C coverage that is incomplete, unowned, or stale before suppression."""
    covered_entries = tuple(
        item for item in (*coverage.entries, *coverage.voltage_entries) if item.status == "COVERED"
    )
    if coverage.status == "BLOCKED":
        return coverage.issue or "I2C pull-up coverage is blocked."
    if coverage.status not in {"COMPLETE", "OPEN"} and covered_entries:
        return "Covered I2C pull-up evidence requires complete or open coverage."
    if coverage.source_path is None and covered_entries:
        return "Covered I2C pull-up evidence requires an identified electrical contract."
    has_evidence = (
        coverage.status == "COMPLETE"
        or bool(coverage.entries)
        or bool(coverage.voltage_entries)
        or coverage.netlist_sha256 is not None
    )
    if has_evidence and (
        current_netlist_sha256 is None or coverage.netlist_sha256 != current_netlist_sha256
    ):
        return "I2C pull-up coverage uses a different or unavailable native netlist hash."
    return None


def resolve_i2c_pullup_coverage(
    request: I2cPullupCoverageRequest,
) -> I2cPullupCoverageResolution:
    """Withhold covered pull-up and voltage rows when source binding fails."""
    coverage = request.coverage
    if coverage is None:
        return I2cPullupCoverageResolution(coverage=None, binding_issue=None)
    issue = i2c_pullup_coverage_issue(coverage, request.current_netlist_sha256)
    if issue is None:
        return I2cPullupCoverageResolution(coverage=coverage, binding_issue=None)
    blocked_coverage = I2cPullupHeuristicCoverage(
        status="BLOCKED",
        source_path=coverage.source_path,
        source_sha256=coverage.source_sha256,
        netlist_sha256=coverage.netlist_sha256,
        issue=issue,
    )
    return I2cPullupCoverageResolution(
        coverage=blocked_coverage,
        binding_issue=issue,
    )


def i2c_buses_with_low_equivalent_pullup_resistance(
    observed: NetlistContract,
) -> tuple[I2cLowEquivalentResistanceObservation, ...]:
    """Find direct fitted pull-ups whose nominal parallel resistance is below 1 kΩ."""
    visible_pullups = visible_resistor_pullups(observed, include_device_r_symbol=True)
    findings: list[I2cLowEquivalentResistanceObservation] = []
    for bus in _i2c_bus_pin_assignments(observed):
        affected_lines: list[I2cLowEquivalentLineEvidence] = []
        line_nets: tuple[tuple[Literal["SDA", "SCL"], str], ...] = (
            ("SDA", bus.sda_net),
            ("SCL", bus.scl_net),
        )
        for line, net in line_nets:
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
            affected_lines.append(
                I2cLowEquivalentLineEvidence(
                    line=line,
                    pullup_paths=paths,
                    equivalent_resistance_ohms=equivalent,
                )
            )
        if affected_lines:
            findings.append(
                I2cLowEquivalentResistanceObservation(
                    sda_net=bus.sda_net,
                    scl_net=bus.scl_net,
                    sda_pins=bus.sda_pins,
                    scl_pins=bus.scl_pins,
                    lines=tuple(affected_lines),
                )
            )
    return tuple(findings)


def i2c_buses_with_multiple_pullup_rail_families(
    observed: NetlistContract,
) -> tuple[I2cMultiplePullupRailFamilies, ...]:
    """Review an I2C bus whose visible pull-ups use distinct recognized rail families."""
    buses = _i2c_bus_pin_assignments(observed, exclude_dnp_references=True)
    visible_pullups = visible_resistor_pullups(observed, include_device_r_symbol=True)
    rail_families_by_net = positive_power_net_families(observed)
    findings: list[I2cMultiplePullupRailFamilies] = []
    for bus in buses:
        families: set[str] = set()
        paths: set[str] = set()
        for line, net in (("SDA", bus.sda_net), ("SCL", bus.scl_net)):
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
                sda_net=bus.sda_net,
                scl_net=bus.scl_net,
                pins=tuple(sorted((*bus.sda_pins, *bus.scl_pins))),
                rail_families=tuple(sorted(families)),
                pullup_paths=tuple(sorted(paths)),
            )
        )
    return tuple(findings)
