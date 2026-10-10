"""Build RC-filter coverage review candidates."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import RcFilterCoverageReport


def rc_filter_candidates(
    rc_filter_coverage: RcFilterCoverageReport | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if rc_filter_coverage is not None:
        for entry in rc_filter_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            calculated = (
                "unavailable"
                if entry.calculated_corner_hz is None
                else f"{entry.calculated_corner_hz:g} Hz"
            )
            found.append(
                Candidate(
                    rule_id="filter.rc_corner_mismatch",
                    subject=f"{entry.id}: mapped first-order RC low-pass filter",
                    message=(
                        "The source-bound resistor/capacitor identity, series/shunt topology, "
                        "nominal values, or calculated corner differs from the project-authored "
                        "requirement. Review the schematic and intended source/load conditions."
                    ),
                    evidence={
                        "profile": (entry.id,),
                        "resistor": (entry.resistor_reference,),
                        "capacitor": (entry.capacitor_reference,),
                        "input_net": (entry.input_net,),
                        "filtered_net": (entry.filtered_net,),
                        "reference_net": (entry.reference_net,),
                        "pin_nets": tuple(
                            f"{pin} -> {', '.join(nets) or 'unconnected'}"
                            for pin, nets in sorted(entry.pin_nets.items())
                        ),
                        "nominal_resistance_ohms": (
                            "unavailable"
                            if entry.resistance_ohms is None
                            else f"{entry.resistance_ohms:g} Ω",
                        ),
                        "nominal_capacitance_pf": (
                            "unavailable"
                            if entry.capacitance_pf is None
                            else f"{entry.capacitance_pf:g} pF",
                        ),
                        "formula": (entry.formula,),
                        "calculated_nominal_corner_hz": (calculated,),
                        "target_corner_hz": (
                            (
                                f"{entry.target_minimum_corner_hz:g}–"
                                f"{entry.target_maximum_corner_hz:g} Hz"
                            ),
                        ),
                        "nominal_resistance_range_ohms": (
                            (
                                f"{entry.nominal_resistance_range_ohms[0]:g}–"
                                f"{entry.nominal_resistance_range_ohms[1]:g} Ω"
                            ),
                        ),
                        "nominal_capacitance_range_pf": (
                            (
                                f"{entry.nominal_capacitance_range_pf[0]:g}–"
                                f"{entry.nominal_capacitance_range_pf[1]:g} pF"
                            ),
                        ),
                        "unlisted_parallel_components": entry.unlisted_parallel_components,
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                    },
                )
            )
    return tuple(found)
