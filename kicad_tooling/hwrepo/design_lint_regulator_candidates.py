"""Build regulator-feedback coverage review candidates."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import RegulatorFeedbackCoverageReport


def regulator_feedback_candidates(
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if regulator_feedback_coverage is not None:
        for entry in regulator_feedback_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            calculated = (
                "unavailable"
                if entry.calculated_output_minimum_v is None
                or entry.calculated_output_maximum_v is None
                else (
                    f"{entry.calculated_output_minimum_v:g}–{entry.calculated_output_maximum_v:g} V"
                )
            )
            feedback_reference_range = (
                f"{entry.feedback_reference_minimum_v:g}–{entry.feedback_reference_maximum_v:g} V"
            )
            target_output_range = (
                f"{entry.target_output_minimum_v:g}–{entry.target_output_maximum_v:g} V"
            )
            found.append(
                Candidate(
                    rule_id="power.regulator_feedback_mismatch",
                    subject=f"{entry.regulator_reference}: mapped feedback divider",
                    message=(
                        "The source-bound regulator identity, two-resistor feedback topology, "
                        "nominal values, or calculated output range differs from the "
                        "project-authored requirement. Review the device data sheet and pin map."
                    ),
                    evidence={
                        "profile": (entry.id,),
                        "regulator": (entry.regulator_reference,),
                        "output_net": (entry.output_net,),
                        "reference_net": (entry.reference_net,),
                        "feedback_net": (entry.feedback_net or "<unresolved>",),
                        "pin_nets": tuple(
                            f"{pin} -> {', '.join(nets) or 'unconnected'}"
                            for pin, nets in sorted(entry.pin_nets.items())
                        ),
                        "nominal_resistance_ohms": tuple(
                            f"{reference}={value:g} Ω"
                            for reference, value in sorted(entry.nominal_resistance_ohms.items())
                        ),
                        "formula": (entry.formula,),
                        "feedback_reference_range_v": (feedback_reference_range,),
                        "calculated_nominal_output_range_v": (calculated,),
                        "target_output_range_v": (target_output_range,),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                    },
                )
            )
    return tuple(found)
