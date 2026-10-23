"""Review SPI clock and chip-select pin functions against explicit net labels."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .spi_participants import spi_signal_role_and_channel
from .spi_role_assignments import spi_role_assignment_groups

RULE_ID = "bus.spi_clock_select_label_mismatch"
_OPPOSITE_ROLES = {"clock": "chip_select", "chip_select": "clock"}


def spi_clock_select_label_mismatch_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted SPI pins assigned to an explicitly opposite-role net name."""
    findings: list[Candidate] = []
    for group in spi_role_assignment_groups(observed):
        role_pins = (*group.roles.get("clock", ()), *group.roles.get("chip_select", ()))
        if any(not pin.in_component_inventory for pin in role_pins):
            continue
        for pin_role, net_role in _OPPOSITE_ROLES.items():
            for pin in group.roles.get(pin_role, ()):
                if len(pin.nets) != 1:
                    continue
                net = pin.nets[0]
                parsed_net = spi_signal_role_and_channel(net)
                if parsed_net is None or parsed_net[0] != net_role:
                    continue

                findings.append(
                    Candidate(
                        rule_id=RULE_ID,
                        subject=f"{pin.pin}: {pin.function} on {net}",
                        message=(
                            f"Native SPI pin function identifies {pin_role}, but the assigned "
                            f"net name {net!r} identifies {net_role}. Review the part-specific "
                            "pin map and naming convention; labels alone do not establish "
                            "required topology or routing."
                        ),
                        evidence={
                            "reference": (group.reference,),
                            "pin": (pin.pin,),
                            "pin_function": (pin.function,),
                            "pin_role": (pin_role,),
                            "pin_channel": (group.channel,),
                            "net": (net,),
                            "net_role": (parsed_net[0],),
                            "net_channel": (parsed_net[1],),
                        },
                    )
                )
    return tuple(findings)
