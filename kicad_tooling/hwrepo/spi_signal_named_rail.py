"""Review SPI signal pins assigned directly to named rails."""

from __future__ import annotations

from types import MappingProxyType

from .design_lint_named_rail_candidate_evidence import (
    NamedRailSignalCandidate,
    SpiSignalNamedRailEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .named_rail_pin_evidence import NamedRailPinSource, assigned_named_rail_ic_pins
from .netlist_contract_models import NetlistContract
from .spi_participants import spi_signal_role_and_channel

RULE_ID: DesignLintRuleId = "bus.spi_signal_on_named_rail"

_ROLE_LABELS = MappingProxyType(
    {
        "clock": "clock",
        "chip_select": "chip select",
        "data_input": "controller-to-peripheral data",
        "data_output": "peripheral-to-controller data",
    }
)


def spi_signal_on_named_rail_candidates(
    observed: NetlistContract,
) -> tuple[NamedRailSignalCandidate, ...]:
    """Review fitted IC SPI pins with one assignment to a rail-like net name.

    Native pin functions and net labels are clues only. A direct rail strap,
    including an intentionally inactive chip select, can be valid.
    """
    candidates: list[NamedRailSignalCandidate] = []
    for item in assigned_named_rail_ic_pins(observed):
        role_channel = spi_signal_role_and_channel(item.function)
        if role_channel is None:
            continue
        role, channel = role_channel
        role_label = _ROLE_LABELS[role]
        candidates.append(
            NamedRailSignalCandidate.from_source_evidence(
                SpiSignalNamedRailEvidence(
                    pin=NamedRailPinSource(observed=observed, evidence=item),
                    role=role,
                    channel=channel,
                ),
                subject=f"{item.pin}: {item.function} on {item.rail_role} net {item.net_name}",
                message=(
                    f"The native SPI pin function indicates {role_label} on channel "
                    f"{channel!r}, while its single assigned net label ({item.net_name!r}) is "
                    f"recognized as {item.rail_role}. Review whether this is an intentional "
                    "rail strap or a pin-assignment issue. The function and label are review "
                    "clues, not proof of electrical potential, required SPI connectivity, or a "
                    "defect; this check does not assess PCB copper or physical continuity."
                ),
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
