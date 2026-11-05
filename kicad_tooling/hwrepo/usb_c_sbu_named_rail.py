"""Review fitted USB-C SBU controller pins assigned directly to named rails."""

from __future__ import annotations

from .bus_signal_roles import usb_c_sbu_role
from .design_lint_named_rail_candidate_evidence import (
    NamedRailSignalCandidate,
    UsbCSbuSignalNamedRailEvidence,
    usb_c_sbu_pair_is_complete,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .named_rail_pin_evidence import NamedRailPinSource, assigned_named_rail_ic_pins
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.usb_c_sbu_signal_on_named_rail"


def usb_c_sbu_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review unique fitted IC SBU1/SBU2 functions on supply/return-like labels.

    Exact SBU roles, fitted U/IC references, complete pin inventory, and
    unambiguous direct rail assignments are review clues. The check does not
    infer controller identity, alternate-mode use, or a required connection.
    """
    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        role = usb_c_sbu_role(item.function)
        if role is None:
            continue
        pin_source = NamedRailPinSource(observed=observed, evidence=item)
        if not usb_c_sbu_pair_is_complete(pin_source):
            continue

        candidates.append(
            NamedRailSignalCandidate.from_source_evidence(
                UsbCSbuSignalNamedRailEvidence(
                    pin=pin_source,
                    role=role,
                ),
                subject=f"{item.pin}: {role} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The fitted IC {role} function is assigned to a net whose label "
                    f"({item.net_name!r}) is recognized as {item.rail_role}. Review whether "
                    "this direct assignment is intentional. Function and label are review "
                    "clues, not proof of electrical potential, USB-C controller identity, "
                    "alternate-mode use, or a defect; this check does not trace passive paths "
                    "or assess PCB copper or physical continuity."
                ),
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
