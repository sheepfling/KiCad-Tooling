"""Build crystal-network coverage review candidates."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import CrystalNetworkCoverageReport


def crystal_network_candidates(
    crystal_network_coverage: CrystalNetworkCoverageReport | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if crystal_network_coverage is not None:
        for entry in crystal_network_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            calculated = (
                "unavailable"
                if entry.calculated_minimum_load_pf is None
                or entry.calculated_maximum_load_pf is None
                else (
                    f"{entry.calculated_minimum_load_pf:g}–{entry.calculated_maximum_load_pf:g} pF"
                )
            )
            found.append(
                Candidate(
                    rule_id="oscillator.crystal_load_network_mismatch",
                    subject=f"{entry.oscillator_reference}: mapped crystal load network",
                    message=(
                        "The source-bound oscillator, resonator, load-capacitor topology, or "
                        "nominal load estimate differs from the project-authored requirement. "
                        "Review the exact pin map and device requirements."
                    ),
                    evidence={
                        "oscillator": (entry.oscillator_reference,),
                        "resonator": (entry.resonator_reference,),
                        "load_capacitors": entry.load_capacitor_references,
                        "potential_extra_load_capacitors": entry.extra_capacitor_references,
                        "potential_extra_load_capacitor_pin_nets": tuple(
                            f"{reference}: {', '.join(pin_nets)}"
                            for reference, pin_nets in sorted(
                                entry.extra_capacitor_pin_nets.items()
                            )
                        ),
                        "pin_nets": tuple(
                            f"{pin} -> {', '.join(nets) or 'unconnected'}"
                            for pin, nets in sorted(entry.node_nets.items())
                        ),
                        "capacitance_pf": tuple(
                            f"{reference}={value:g} pF"
                            for reference, value in sorted(entry.capacitance_pf.items())
                        ),
                        "formula": (entry.formula,),
                        "calculated_nominal_load_pf": (calculated,),
                        "target_nominal_load_pf": (
                            (
                                f"{entry.target_minimum_load_pf:g}–"
                                f"{entry.target_maximum_load_pf:g} pF"
                            ),
                        ),
                        "stray_capacitance_assumption_pf": (
                            (
                                f"{entry.minimum_stray_capacitance_pf:g}–"
                                f"{entry.maximum_stray_capacitance_pf:g} pF"
                            ),
                        ),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                    },
                )
            )
    return tuple(found)
