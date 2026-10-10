"""Translate authored connector signal-to-return distribution coverage."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import ConnectorReturnDistributionCoverageReport


def return_distribution_candidates(
    connector_return_distribution: ConnectorReturnDistributionCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Build review candidates for explicit connector return-contact thresholds."""
    found: list[Candidate] = []
    if connector_return_distribution is not None:
        for entry in connector_return_distribution.entries:
            if entry.status not in {"OUT_OF_RANGE", "INCOMPLETE"}:
                continue
            ratio = (
                "undefined (no return contacts)"
                if entry.signal_to_return_ratio is None
                else f"{entry.signal_to_return_ratio:g} signals per return"
            )
            found.append(
                Candidate(
                    rule_id="connector.return_distribution",
                    subject=(
                        f"{entry.connector_reference or entry.interface_id}: "
                        "reviewed return-contact distribution"
                    ),
                    message=(
                        "The explicitly role-classified interface is outside its project-authored "
                        "signal-to-return contact threshold or lacks complete role evidence. "
                        "Review the pin allocation; this ratio does not require returns to share "
                        "a net."
                    ),
                    evidence={
                        "profile": (entry.id,),
                        "connector": (entry.connector_reference or "<no bound connector>",),
                        "interface": (entry.interface_id,),
                        "signal_contact_count": (str(entry.signal_pin_count),),
                        "signal_pins": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.signal_pin_map.items())
                        ),
                        "return_contact_count": (str(entry.return_pin_count),),
                        "return_pins": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.return_pin_map.items())
                        ),
                        "supply_pins_excluded": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.supply_pin_map.items())
                        ),
                        "shield_pins_excluded": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.shield_pin_map.items())
                        ),
                        "other_pins_excluded": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.other_pin_map.items())
                        ),
                        "unclassified_pins": tuple(
                            f"interface {number} -> {pin}"
                            for number, pin in sorted(entry.unclassified_pin_map.items())
                        ),
                        "required_return_contact_count": (str(entry.required_return_pin_count),),
                        "signal_to_return_ratio": (ratio,),
                        "minimum_signal_pin_count": (str(entry.minimum_signal_pin_count),),
                        "maximum_signal_to_return_ratio": (
                            f"{entry.maximum_signal_to_return_ratio:g}",
                        ),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                    },
                )
            )
    return tuple(found)
