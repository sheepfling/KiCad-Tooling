"""Review explicit RS-485 transceiver data pins on named rails."""

from __future__ import annotations

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_pin_evidence import assigned_named_rail_ic_pins
from .rs485_data_functions import explicit_rs485_transceiver_identity, rs485_data_pin_role

RULE_ID: DesignLintRuleId = "bus.rs485_signal_on_named_rail"


def rs485_signal_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review fitted, identified RS-485 D/DI or R/RO pins assigned to named rails.

    Function and net labels are clues only. Some RS-485 devices intentionally
    strap a data pin for a chosen mode, so this rule asks for review rather than
    claiming a defect.
    """
    candidates: list[Candidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        identity = explicit_rs485_transceiver_identity(observed, item.reference)
        role = rs485_data_pin_role(item.function)
        if identity is None or role is None:
            continue
        role_name = "driver-data input" if role == "tx" else "receiver-data output"
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The identified RS-485 {role_name} function is assigned to a net whose "
                    f"label ({item.net_name!r}) is recognized as {item.rail_role}. Review "
                    "whether this direct assignment is intentional. Identity, function, and "
                    "label are review clues, not proof of electrical potential, required "
                    "operating mode, a defect, PCB copper, or physical continuity."
                ),
                evidence={
                    "pin": (item.pin,),
                    "pin_function": (item.function,),
                    "rs485_data_role": (role,),
                    "assigned_net": (item.net_name,),
                    "net_label_role_clue": (item.rail_role,),
                    "identity_basis": (identity,),
                    "component_pin_inventory": item.inventory,
                },
            )
        )
    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
