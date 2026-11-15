"""Review CAN bus-line pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_roles import can_function_role
from .design_lint_named_rail_line_candidate_evidence import (
    CanLineNamedRailEvidence,
    NamedRailLineCandidate,
    can_line_named_rail_peer,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .named_rail_pin_evidence import (
    NamedRailPinEvidence,
    NamedRailPinSource,
    assigned_named_rail_connector_pins,
    assigned_named_rail_ic_pins,
)
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.can_line_on_named_rail"


def can_line_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review fitted IC or bounded connector CANH/CANL pins on named rails.

    A unique exported CANH/CANL function pair and complete native inventory
    distinguish bus-side pins from controller TX/RX signals. The assignment
    and rail-like name remain review clues, not proof of a defect.
    """
    candidates: list[Candidate] = []
    pin_evidence_by_pin: dict[str, NamedRailPinEvidence] = {}
    for item in (
        *assigned_named_rail_ic_pins(observed),
        *assigned_named_rail_connector_pins(observed),
    ):
        pin_evidence_by_pin.setdefault(item.pin.casefold(), item)
    for item in sorted(
        pin_evidence_by_pin.values(), key=lambda evidence: (evidence.pin.casefold(), evidence.pin)
    ):
        role = can_function_role(item.function)
        if role not in {"CANH", "CANL"}:
            continue
        pin_source = NamedRailPinSource(observed=observed, evidence=item)
        pair = can_line_named_rail_peer(pin_source)
        if pair is None:
            continue
        candidates.append(
            NamedRailLineCandidate.from_source_evidence(
                CanLineNamedRailEvidence(pin=pin_source, peer=pair),
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The CAN bus-line {pair.role} function is assigned to a net whose label "
                    f"({item.net_name!r}) is recognized as {item.rail_role}. Review whether "
                    "this direct assignment is intentional. Function and label are review "
                    "clues, not proof of electrical potential, required CAN connectivity, or "
                    "a defect; this check does not assess PCB copper or physical continuity."
                ),
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
