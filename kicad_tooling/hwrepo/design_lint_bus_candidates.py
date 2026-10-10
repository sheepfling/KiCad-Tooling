"""Candidate translation for I2C, SPI, CAN, and named-pair lint rules."""

from __future__ import annotations

from collections.abc import Sequence

from .bus_signal_pairs import (
    ComplementaryPinFunctionAliasResolution,
    complementary_signal_gaps,
)
from .bus_signal_roles import (
    unconnected_interface_pins,
)
from .can_peer_heuristics import (
    can_peer_assignment_divergences,
)
from .can_termination_heuristics import (
    can_buses_without_local_termination,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .differential_pair_names import named_differential_pairs
from .i2c_addressing import format_i2c_address, unmapped_i2c_responders
from .i2c_pullup_heuristics import (
    i2c_buses_with_low_equivalent_pullup_resistance,
    i2c_buses_with_multiple_pullup_rail_families,
    i2c_buses_without_local_pullups,
)
from .models import (
    I2cAddressCoverageReport,
    I2cAddressMap,
    I2cPullupHeuristicCoverage,
    I2cResponderAddressCoverageEntry,
    NetlistContract,
)
from .pcb_drc_models import PcbDifferentialPairRuleMap
from .spi_bias_heuristics import (
    spi_active_low_chip_selects_without_pullups,
)


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


def bus_candidates(
    observed: NetlistContract,
    *,
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution | None = None,
    i2c_address_coverage: I2cAddressCoverageReport | None = None,
    i2c_address_map: I2cAddressMap | None = None,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None,
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None = None,
) -> tuple[Candidate, ...]:
    """Translate protocol and named-pair observations into review candidates."""
    found: list[Candidate] = []
    pullup_coverage_entries = (
        ()
        if i2c_pullup_heuristic_coverage is None
        or i2c_pullup_heuristic_coverage.status == "BLOCKED"
        else i2c_pullup_heuristic_coverage.entries
    )
    covered_i2c_pullup_gaps = {
        (
            entry.sda_net.casefold(),
            entry.scl_net.casefold(),
            entry.missing_lines,
        )
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
    for gap in spi_active_low_chip_selects_without_pullups(observed):
        found.append(
            Candidate(
                rule_id="bus.spi_active_low_chip_select_without_pullup",
                subject=f"{gap.net}: active-low SPI chip-select bias",
                message=(
                    "This assigned active-low chip-select input has no visible 1 kΩ–100 kΩ "
                    "resistor path to a recognized positive rail. Review the device's reset-time "
                    "state and any internal or off-board bias; the pin name alone does not "
                    "establish that an external pull-up is required."
                ),
                evidence={
                    "net": (gap.net,),
                    "active_low_chip_select_pins": gap.pins,
                    "recognized_positive_rails": gap.positive_rails,
                    "visible_pullup_paths": (),
                },
            )
        )
    for pin in unconnected_interface_pins(observed):
        if pin.protocol == "i2c":
            rule_id: DesignLintRuleId = "bus.i2c_unconnected_pin"
            description = "I²C signal"
        elif pin.protocol == "spi":
            rule_id = "bus.spi_unconnected_chip_select"
            description = "SPI chip-select"
        elif pin.protocol == "usb_c":
            rule_id = "bus.usb_c_unconnected_cc_pin"
            description = "USB-C configuration-channel"
        else:
            rule_id = "bus.can_unconnected_line"
            description = "CANH/CANL line"
        found.append(
            Candidate(
                rule_id=rule_id,
                subject=f"{pin.pin}: {pin.function}",
                message=(
                    f"This named {description} pin has no net assignment. Review whether it is "
                    "intentionally unused or a connection is missing."
                ),
                evidence={pin.pin: (), "function": (pin.function,)},
            )
        )
    for bus in can_buses_without_local_termination(observed):
        found.append(
            Candidate(
                rule_id="bus.can_missing_termination",
                subject=f"CANH {bus.high_net} / CANL {bus.low_net}",
                message=(
                    "No visible 108 Ω–132 Ω resistor is connected directly across these named "
                    "CAN lines. Review external or split termination and the intended bus topology."
                ),
                evidence={
                    "CANH": (bus.high_net,),
                    "CANL": (bus.low_net,),
                    "pins": (*bus.high_pins, *bus.low_pins),
                    "termination": (),
                },
            )
        )
    for divergence in can_peer_assignment_divergences(observed):
        found.append(
            Candidate(
                rule_id="bus.can_peer_assignment_divergence",
                subject=(
                    f"{divergence.shared_role} {divergence.shared_net}: "
                    "peer pair assignments diverge"
                ),
                message=(
                    f"Complete CAN pin pairs share {divergence.shared_role} net "
                    f"{divergence.shared_net}, but their {divergence.complementary_role} "
                    f"pins use multiple nets ({', '.join(divergence.complementary_nets)}). "
                    "Review whether the separate pair assignments are intentional; pin names "
                    "do not establish common-bus intent or physical connectivity."
                ),
                evidence={
                    "shared_role": (divergence.shared_role,),
                    "shared_net": (divergence.shared_net,),
                    "complementary_role": (divergence.complementary_role,),
                    "complementary_nets": divergence.complementary_nets,
                    "participants": divergence.participants,
                },
            )
        )
    for gap in complementary_signal_gaps(observed, complementary_alias_resolution):
        if (
            gap.family == "CAN"
            and gap.alias_symbol is None
            and gap.pins["positive"]
            and gap.pins["negative"]
            and (not gap.nets["positive"] or not gap.nets["negative"])
        ):
            # The per-pin CAN rule already reports open CANH/CANL assignments.
            continue
        evidence = {
            "positive_pins": gap.pins["positive"],
            "negative_pins": gap.pins["negative"],
            "positive_nets": gap.nets["positive"],
            "negative_nets": gap.nets["negative"],
        }
        if gap.alias_symbol is not None:
            if gap.alias_basis is None or gap.alias_sha256 is None:
                raise AssertionError(
                    "Resolved complementary aliases must retain their basis digest"
                )
            evidence.update(
                {
                    "alias_symbol": (gap.alias_symbol,),
                    "alias_basis": (gap.alias_basis,),
                    "alias_sha256": (gap.alias_sha256,),
                }
            )
        found.append(
            Candidate(
                rule_id="bus.complementary_pair_assignment",
                subject=f"{gap.reference}: {gap.family} pair",
                message=(
                    f"A recognized {gap.family} complementary pair has an incomplete or ambiguous "
                    f"schematic assignment: {gap.reason}. Review the interface pin map."
                ),
                evidence=evidence,
            )
        )
    for pair in named_differential_pairs(observed.nets, pcb_differential_pair_rule_map):
        found.append(
            Candidate(
                rule_id="signal.named_pair_without_reviewed_requirement",
                subject=f"{pair.positive_net} / {pair.negative_net}",
                message=(
                    "These source net names match a recognized complementary-signal pattern. "
                    "Review whether they form a physical differential pair and, if so, add "
                    "project-owned PCB constraints. The name pattern does not establish pair "
                    "intent, routing quality, or an acceptable skew limit."
                ),
                evidence={
                    "positive_net": (pair.positive_net,),
                    "positive_references": pair.positive_references,
                    "negative_net": (pair.negative_net,),
                    "negative_references": pair.negative_references,
                    "naming_pattern": (pair.naming_pattern,),
                },
            )
        )

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
