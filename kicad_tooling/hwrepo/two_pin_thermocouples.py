"""Review supported fitted two-pin thermocouples assigned to one schematic net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .two_pin_components import TwoPinComponentOnSameNet


def two_pin_thermocouple_same_net_candidates(
    observations: tuple[TwoPinComponentOnSameNet, ...],
) -> tuple[Candidate, ...]:
    """Build REVIEW candidates for exact two-pin thermocouples sharing one net."""
    return tuple(
        Candidate(
            rule_id="component.two_pin_thermocouple_same_net",
            subject=f"{item.reference}: both thermocouple leads share {item.net}",
            message=(
                "Both leads of this supported fitted two-pin thermocouple are assigned to the "
                "same native schematic net, so the net assignment shows no differential signal "
                "across its input leads. Review whether this is intentional or a connection is "
                "missing. This prompt does not establish temperature measurement, cold-junction "
                "compensation, sensor suitability, instrumentation grounding, polarity, footprint "
                "mapping, physical connectivity, or assembly state."
            ),
            evidence={
                "symbol": (item.symbol,),
                "value": (item.value,),
                "net": (item.net,),
                "pin_assignments": tuple(
                    f"{item.reference}.{number} -> {item.net}" for number in item.pin_numbers
                ),
            },
        )
        for item in observations
        if item.kind == "thermocouple"
    )
