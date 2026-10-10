"""Translate I2C pull-up and address-map review observations."""

from __future__ import annotations

from collections.abc import Sequence

from .design_lint_types import Candidate
from .i2c_address_models import (
    I2cAddressCoverageReport,
    I2cAddressMap,
    I2cResponderAddressCoverageEntry,
)
from .i2c_addressing import format_i2c_address, unmapped_i2c_responders
from .i2c_pullup_heuristics import (
    i2c_buses_with_low_equivalent_pullup_resistance,
    i2c_buses_with_multiple_pullup_rail_families,
    i2c_buses_without_local_pullups,
)
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .models import NetlistContract


def _i2c_address_evidence(
    entries: Sequence[I2cResponderAddressCoverageEntry],
) -> dict[str, tuple[str, ...]]:
    evidence: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        evidence[f"{entry.reference}.symbol"] = (
            f"expected {entry.expected_symbol}; observed {entry.observed_symbol or 'unknown'}",
        )
        evidence[f"{entry.reference}.SDA"] = (
            f"{entry.sda_pin} -> {', '.join(entry.sda_nets) or 'unconnected'}",
        )
        evidence[f"{entry.reference}.SCL"] = (
            f"{entry.scl_pin} -> {', '.join(entry.scl_nets) or 'unconnected'}",
        )
        address_evidence = (
            f"expected {format_i2c_address(entry.expected_address)}; "
            f"observed {format_i2c_address(entry.observed_address)}"
        )
        evidence[f"{entry.reference}.address"] = (address_evidence,)
        for bit in entry.address_bits:
            bit_evidence = (
                f"{bit.pin} function {bit.observed_function or 'unknown'}; "
                f"nets {', '.join(bit.nets) or 'unconnected'}; "
                f"resolved {bit.resolved_value if bit.resolved_value is not None else 'unknown'}"
            )
            evidence[f"{entry.reference}.bit{bit.bit}"] = (bit_evidence,)
        evidence[f"{entry.reference}.basis"] = (entry.basis,)
    return evidence


def i2c_pullup_candidates(
    observed: NetlistContract,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None,
) -> tuple[Candidate, ...]:
    """Build I2C pull-up topology review prompts."""
    found: list[Candidate] = []
    pullup_coverage_entries = (
        ()
        if i2c_pullup_heuristic_coverage is None
        or i2c_pullup_heuristic_coverage.status == "BLOCKED"
        else i2c_pullup_heuristic_coverage.entries
    )
    covered_i2c_pullup_gaps = {
        (entry.sda_net.casefold(), entry.scl_net.casefold(), entry.missing_lines)
        for entry in pullup_coverage_entries
        if entry.status == "COVERED"
    }
    for bus in i2c_buses_without_local_pullups(observed):
        if (
            bus.sda_net.casefold(),
            bus.scl_net.casefold(),
            bus.missing_lines,
        ) in covered_i2c_pullup_gaps:
            continue
        found.append(
            Candidate(
                rule_id="bus.i2c_missing_pullup",
                subject=f"SDA {bus.sda_net} / SCL {bus.scl_net}",
                message=(
                    "This named SDA/SCL pair has no visible 1 kΩ–100 kΩ resistor path to a "
                    "named positive rail on "
                    f"{', '.join(bus.missing_lines)}. Review internal or off-board pull-ups."
                ),
                evidence={
                    "SDA": (bus.sda_net,),
                    "SCL": (bus.scl_net,),
                    "pins": (*bus.sda_pins, *bus.scl_pins),
                    "missing_pullups": bus.missing_lines,
                },
            )
        )
    for bus in i2c_buses_with_low_equivalent_pullup_resistance(observed):
        found.append(
            Candidate(
                rule_id="bus.i2c_low_equivalent_resistance",
                subject=f"SDA {bus.sda_net} / SCL {bus.scl_net}",
                message=(
                    "Recognized fitted pull-ups in parallel have nominal effective resistance "
                    f"below 1 kΩ on {', '.join(bus.lines)}. Review the approved bus range, rail, "
                    "and sink-current limits; capacitance and timing are not modeled."
                ),
                evidence={
                    "SDA": (bus.sda_net,),
                    "SCL": (bus.scl_net,),
                    "lines": bus.lines,
                    "pins": (*bus.pins["SDA"], *bus.pins["SCL"]),
                    "equivalent_ohms": tuple(
                        f"{line}={bus.equivalent_ohms[line]}Ω" for line in bus.lines
                    ),
                    "pullup_resistors": tuple(
                        item for line in bus.lines for item in bus.resistors[line]
                    ),
                },
            )
        )
    for bus in i2c_buses_with_multiple_pullup_rail_families(observed):
        found.append(
            Candidate(
                rule_id="bus.i2c_multiple_pullup_rail_families",
                subject=f"SDA {bus.sda_net} / SCL {bus.scl_net}",
                message=(
                    "Visible fitted I2C pull-up paths use different recognized positive-rail "
                    f"families ({', '.join(bus.rail_families)}). Review the bus voltage limits, "
                    "pull-up rail, and any level-shifting topology; rail names alone do not "
                    "establish voltage compatibility."
                ),
                evidence={
                    "SDA": (bus.sda_net,),
                    "SCL": (bus.scl_net,),
                    "pins": bus.pins,
                    "rail_families": bus.rail_families,
                    "pullup_paths": bus.pullup_paths,
                },
            )
        )
    return tuple(found)


def i2c_address_candidates(
    i2c_address_coverage: I2cAddressCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Build I2C address mismatch and collision prompts from declared coverage."""
    found: list[Candidate] = []
    if i2c_address_coverage is not None:
        for entry in i2c_address_coverage.entries:
            if (
                entry.status == "COMPLETE"
                and entry.mode == "strapped"
                and entry.expected_address != entry.observed_address
            ):
                found.append(
                    Candidate(
                        rule_id="bus.i2c_address_mismatch",
                        subject=(
                            f"{entry.reference} on {entry.segment_id}: "
                            f"{format_i2c_address(entry.observed_address)}"
                        ),
                        message=(
                            "Source-bound address-pin nets resolve to a different static I2C "
                            "address than the project map declares. Review the strap wiring, "
                            "device profile, or approved address."
                        ),
                        evidence={
                            "segment": (entry.segment_id,),
                            **_i2c_address_evidence((entry,)),
                        },
                    )
                )
        address_groups: dict[tuple[str, int], list[I2cResponderAddressCoverageEntry]] = {}
        for entry in i2c_address_coverage.entries:
            if entry.status == "COMPLETE" and entry.observed_address is not None:
                address_groups.setdefault((entry.segment_id, entry.observed_address), []).append(
                    entry
                )
        for (segment_id, address), entries in sorted(address_groups.items()):
            if len(entries) < 2:
                continue
            references = tuple(sorted(entry.reference for entry in entries))
            found.append(
                Candidate(
                    rule_id="bus.i2c_address_collision",
                    subject=f"{segment_id}: {', '.join(references)} at {format_i2c_address(address)}",
                    message=(
                        "Multiple fitted responders on this declared I2C segment resolve to the "
                        "same static address. Review the address map or any mux isolation not "
                        "represented by the declared segment."
                    ),
                    evidence={
                        "segment": (segment_id,),
                        "address": (format_i2c_address(address),),
                        **_i2c_address_evidence(entries),
                    },
                )
            )
    return tuple(found)


def i2c_responder_coverage_candidates(
    observed: NetlistContract,
    i2c_address_map: I2cAddressMap | None,
) -> tuple[Candidate, ...]:
    """Prompt review of I2C responders absent from the project address map."""
    found: list[Candidate] = []
    for responder in unmapped_i2c_responders(observed, i2c_address_map):
        net_pairs = tuple(f"{sda} / {scl}" for sda, scl in responder.signal_pairs)
        has_map = i2c_address_map is not None
        found.append(
            Candidate(
                rule_id="bus.i2c_unmapped_responder",
                subject=f"{responder.reference}: I2C address-map coverage",
                message=(
                    f"{responder.reference} has assigned native SDA/SCL pin functions but "
                    + (
                        "is not listed as a responder in the project address map. "
                        if has_map
                        else "no project I2C address map is configured. "
                    )
                    + "Review whether it is a static or dynamic responder, or intentionally "
                    "outside address checking."
                ),
                evidence={
                    "SDA_pins": responder.sda_pins,
                    "SCL_pins": responder.scl_pins,
                    "assigned_net_pairs": net_pairs,
                    "address_map": (("configured",) if has_map else ("not_configured",)),
                },
            )
        )
    return tuple(found)
