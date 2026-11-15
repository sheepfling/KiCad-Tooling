"""Review CAN controller and identified module data pins on named rails."""

from __future__ import annotations

from .can_signal_functions import (
    CAN_MODULE_CHANNEL,
    can_module_data_role,
    can_signal_role_and_channel,
    explicit_can_module_identity,
)
from .design_lint_named_rail_candidate_evidence import (
    CanSignalNamedRailEvidence,
    NamedRailSignalCandidate,
)
from .design_lint_rule_types import DesignLintRuleId
from .named_rail_pin_evidence import (
    NamedRailPinSource,
    assigned_named_rail_connector_pins,
    assigned_named_rail_ic_pins,
)
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.can_signal_on_named_rail"


def can_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[NamedRailSignalCandidate, ...]:
    """Review fitted IC or connector CAN/FDCAN TX/RX pins on named rails.

    Native pin-function names and rail-like net labels are clues only. A direct
    strap may be intentional for a particular transceiver or operating mode.
    """
    candidates: list[NamedRailSignalCandidate] = []
    pin_evidence = (
        *assigned_named_rail_ic_pins(observed),
        *assigned_named_rail_connector_pins(observed),
    )
    for item in pin_evidence:
        role_channel = can_signal_role_and_channel(item.function)
        identity_basis: str | None = None
        if role_channel is None and item.reference_kind == "connector":
            identity_basis = explicit_can_module_identity(observed, item.reference)
            module_role = can_module_data_role(item.function)
            if identity_basis is None or module_role is None:
                continue
            role_channel = (module_role, CAN_MODULE_CHANNEL)
        if role_channel is None:
            continue
        role, channel = role_channel
        candidates.append(
            NamedRailSignalCandidate.from_source_evidence(
                CanSignalNamedRailEvidence(
                    pin=NamedRailPinSource(observed=observed, evidence=item),
                    role=role,
                    channel=channel,
                    identity_basis=identity_basis,
                ),
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    _can_named_rail_message(
                        role=role,
                        channel=channel,
                        identity_basis=identity_basis,
                        net_name=item.net_name,
                        rail_role=item.rail_role,
                    )
                ),
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))


def _can_named_rail_message(
    *, role: str, channel: str, identity_basis: str | None, net_name: str, rail_role: str
) -> str:
    if identity_basis is None:
        endpoint = f"native CAN/FDCAN {role.upper()} function on channel {channel!r}"
    else:
        endpoint = (
            f"generic {role.upper()} function on an explicitly identified CAN module "
            f"({identity_basis})"
        )
    return (
        f"The {endpoint} is assigned to a net whose label ({net_name!r}) is recognized "
        f"as {rail_role}. Review whether this is an intentional rail strap or a pin-assignment "
        f"issue. Identity, "
        "function, and label are review clues, not proof of electrical potential, required "
        "operating mode, a defect, PCB copper, or physical continuity."
    )
