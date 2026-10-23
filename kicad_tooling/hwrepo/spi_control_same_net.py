"""Review one fitted SPI IC's clock and chip-select pins on one net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .spi_role_assignments import spi_channel_label, spi_role_assignment_groups

RULE_ID = "bus.spi_clock_chip_select_same_net"


def spi_clock_chip_select_same_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find one fitted SPI IC's clock and chip-select roles on the same net.

    The default-off prompt uses bounded native function and net assignments.
    It does not infer the configured SPI mode or whether either pin is
    intentionally multiplexed.
    """
    findings: list[Candidate] = []
    for group in spi_role_assignment_groups(observed):
        clocks = group.roles.get("clock", ())
        chip_selects = group.roles.get("chip_select", ())
        if len(clocks) != 1 or len(chip_selects) != 1:
            continue
        clock, chip_select = clocks[0], chip_selects[0]
        if not clock.in_component_inventory or not chip_select.in_component_inventory:
            continue
        if len(clock.nets) != 1 or len(chip_select.nets) != 1:
            continue
        if clock.nets[0] != chip_select.nets[0]:
            continue
        if clock.electrical_type == chip_select.electrical_type == "output":
            continue

        channel = spi_channel_label(group.channel)
        net = clock.nets[0]
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{group.reference}: {channel} clock {clock.function} and chip select "
                    f"{chip_select.function} share {net}"
                ),
                message=(
                    f"Fitted IC {group.reference} has a native SPI clock pin {clock.pin} "
                    f"({clock.function}, {clock.electrical_type}) and chip-select pin "
                    f"{chip_select.pin} ({chip_select.function}, "
                    f"{chip_select.electrical_type}) on one schematic net ({net}). "
                    "Review whether the assignment is intentional. Pin-function names do not "
                    "establish the device's configured mode or required topology."
                ),
                evidence={
                    "component": (group.reference,),
                    "channel": (channel,),
                    "clock_pin": (clock.pin,),
                    "clock_function": (clock.function,),
                    "clock_electrical_type": (clock.electrical_type,),
                    "chip_select_pin": (chip_select.pin,),
                    "chip_select_function": (chip_select.function,),
                    "chip_select_electrical_type": (chip_select.electrical_type,),
                    "net": (net,),
                },
            )
        )
    return tuple(findings)
