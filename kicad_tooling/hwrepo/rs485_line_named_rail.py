"""Review explicit RS-485 bus-line pins assigned directly to named rails."""

from __future__ import annotations

from .design_lint_named_rail_line_candidate_evidence import (
    NamedRailLineCandidate,
    Rs485LineNamedRailEvidence,
    rs485_line_named_rail_peer,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .named_rail_pin_evidence import NamedRailPinSource, assigned_named_rail_ic_pins
from .netlist_contract_models import NetlistContract
from .rs485_line_functions import rs485_bus_line_role

RULE_ID: DesignLintRuleId = "bus.rs485_line_on_named_rail"


def rs485_line_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review identified RS-485 A/B pins with one assignment to a named rail.

    Requiring a unique A/B function pair, complete pin inventories, a fitted
    IC, and explicit RS-485 identity keeps generic A/B pins out of scope. The
    rail label remains a clue and the finding defaults to review.
    """
    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        role = rs485_bus_line_role(item.function)
        if role is None:
            continue
        pin_source = NamedRailPinSource(observed=observed, evidence=item)
        pair = rs485_line_named_rail_peer(pin_source)
        if pair is None:
            continue
        role_name = "A" if pair.role == "a" else "B"
        candidates.append(
            NamedRailLineCandidate.from_source_evidence(
                Rs485LineNamedRailEvidence(pin=pin_source, peer=pair),
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The identified RS-485 bus-line {role_name} function is assigned to a "
                    f"net whose label ({item.net_name!r}) is recognized as {item.rail_role}. "
                    "Review whether this direct assignment is intentional. Identity, function, "
                    "and label are review clues, not proof of electrical potential, a required "
                    "bus topology, a defect, PCB copper, or physical continuity."
                ),
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
