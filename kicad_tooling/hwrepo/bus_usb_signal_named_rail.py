"""Review fitted USB data pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_pairs import usb_signal_family_and_side
from .design_lint_named_rail_candidate_evidence import (
    NamedRailSignalCandidate,
    UsbSignalNamedRailEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .named_rail_pin_evidence import NamedRailPinSource, assigned_named_rail_ic_pins
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.usb_signal_on_named_rail"


def usb_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[NamedRailSignalCandidate, ...]:
    """Review fitted IC USB data pins assigned to one named supply or return rail.

    Pin-function and net-label vocabularies are bounded clues. A rail-looking
    assignment can also be an intentional strap, so this predicate requests
    review instead of asserting a required connection or electrical defect.
    """
    candidates: list[NamedRailSignalCandidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        identity = usb_signal_family_and_side(item.function)
        if identity is None:
            continue
        family, side = identity
        candidates.append(
            NamedRailSignalCandidate.from_source_evidence(
                UsbSignalNamedRailEvidence(
                    pin=NamedRailPinSource(observed=observed, evidence=item),
                    family=family,
                    side=side,
                ),
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The native {family} pin function identifies the {side} side, while its "
                    f"single assigned net label ({item.net_name!r}) is recognized as "
                    f"{item.rail_role}. Review whether this direct assignment is intentional. "
                    "Function and label clues do not establish electrical potential, required "
                    "connectivity, routed copper, or physical continuity."
                ),
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
