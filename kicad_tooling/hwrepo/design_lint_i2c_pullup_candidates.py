"""I2C pull-up theme candidate evaluation with explicit coverage input."""

from __future__ import annotations

from .design_lint_types import Candidate
from .i2c_pullup_heuristics import (
    i2c_buses_with_low_equivalent_pullup_resistance,
    i2c_buses_with_multiple_pullup_rail_families,
    i2c_buses_without_local_pullups,
)
from .i2c_pullup_inputs import I2cPullupSnifferInput


def i2c_pullup_theme_candidates(
    inputs: I2cPullupSnifferInput,
) -> tuple[Candidate, ...]:
    """Build I2C pull-up topology review prompts."""
    observed = inputs.observed
    i2c_pullup_heuristic_coverage = inputs.coverage
    found: list[Candidate] = []
    pullup_coverage_entries = (
        ()
        if i2c_pullup_heuristic_coverage.status == "BLOCKED"
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
    for entry in i2c_pullup_heuristic_coverage.voltage_entries:
        if entry.status != "OPEN":
            continue
        found.append(
            Candidate(
                rule_id="bus.i2c_pullup_input_limit_coverage",
                subject=f"{entry.line} {entry.signal_net}: input-voltage coverage",
                message=(
                    "A visible local pull-up reaches "
                    f"{', '.join(entry.pullup_rails)}, but the exact project voltage review "
                    "is absent, incomplete, or failed its source-bound pull-up/voltage checks. "
                    "Review the maximum pull-up rail voltage against each device's approved "
                    "input limit; this prompt does not infer voltage compatibility."
                ),
                evidence={
                    "SDA": (entry.sda_net,),
                    "SCL": (entry.scl_net,),
                    "line": (entry.line,),
                    "signal_net": (entry.signal_net,),
                    "pullup_rails": entry.pullup_rails,
                    "endpoint_pins": entry.endpoint_pins,
                    "covered_input_pins": entry.covered_input_pins,
                    "missing_input_pins": entry.missing_input_pins,
                    "issues": entry.issues,
                },
            )
        )
    return tuple(found)
