"""Review UART/USART signal pins assigned directly to named rails."""

from __future__ import annotations

from .design_lint_named_rail_candidate_evidence import (
    NamedRailSignalCandidate,
    SerialSignalNamedRailEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .named_rail_pin_evidence import (
    NamedRailPinSource,
    assigned_named_rail_connector_pins,
    assigned_named_rail_ic_pins,
)
from .netlist_contract_models import NetlistContract
from .serial_participants import (
    serial_flow_control_role_and_channel,
    serial_function_role_and_channel,
)

RULE_ID: DesignLintRuleId = "bus.serial_signal_on_named_rail"


def serial_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[NamedRailSignalCandidate, ...]:
    """Review fitted IC or connector UART/USART signal pins on a named rail.

    Pin functions and net labels are clues for review. The candidate does not
    establish a required serial endpoint or prove an electrical defect.
    """
    candidates: list[NamedRailSignalCandidate] = []
    pin_evidence = (
        *assigned_named_rail_ic_pins(observed),
        *assigned_named_rail_connector_pins(observed),
    )
    for item in pin_evidence:
        pin_role = serial_function_role_and_channel(item.function)
        if pin_role is None:
            pin_role = serial_flow_control_role_and_channel(item.function)
        if pin_role is None:
            continue

        role, channel = pin_role
        candidates.append(
            NamedRailSignalCandidate.from_source_evidence(
                SerialSignalNamedRailEvidence(
                    pin=NamedRailPinSource(observed=observed, evidence=item),
                    role=role,
                    channel=channel,
                ),
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The native UART/USART pin function indicates {role.upper()} on channel "
                    f"{channel!r}, while its single assigned net label ({item.net_name!r}) is "
                    f"recognized as {item.rail_role}. Review whether this is an intentional rail "
                    "strap or a pin-assignment issue. A CTS/RTS strap may be intentional when "
                    "hardware flow control is unused. The function and label are review clues, "
                    "not proof of electrical potential, required serial connectivity, or a "
                    "defect; this check does not assess PCB copper or physical continuity."
                ),
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
