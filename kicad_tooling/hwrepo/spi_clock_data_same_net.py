"""Review fitted SPI clock/control and data roles assigned to one net."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .design_lint_types import Candidate
from .models import NetlistContract
from .spi_role_assignments import (
    SpiRoleAssignmentGroup,
    SpiRolePinAssignment,
    spi_channel_label,
    spi_role_assignment_groups,
)

RULE_ID = "bus.spi_clock_control_data_same_net"
_SPI_CONTROL_ROLES = frozenset({"clock", "chip_select"})
_SPI_DATA_ROLES = frozenset({"data_input", "data_output"})
_ROLE_ORDER: Mapping[str, int] = MappingProxyType(
    {"clock": 0, "chip_select": 1, "data_input": 2, "data_output": 3}
)


def _candidate(
    group: SpiRoleAssignmentGroup,
    control_role: str,
    data_role: str,
    control: SpiRolePinAssignment,
    data: SpiRolePinAssignment,
    net: str,
) -> Candidate:
    channel = spi_channel_label(group.channel)
    control_name = control_role.replace("_", " ")
    data_name = data_role.replace("_", " ")
    return Candidate(
        rule_id=RULE_ID,
        subject=(
            f"{group.reference}: {channel} {control_name} {control.function} and "
            f"{data_name} {data.function} share {net}"
        ),
        message=(
            f"Fitted IC {group.reference} has a native SPI {control_name} pin "
            f"{control.pin} ({control.function}, {control.electrical_type}) and a "
            f"{data_name} pin {data.pin} ({data.function}, {data.electrical_type}) "
            f"on one schematic net ({net}). Review whether the assignment is intentional. "
            "Pin-function names do not establish the device's configured mode or required topology."
        ),
        evidence={
            "component": (group.reference,),
            "channel": (channel,),
            "spi_role_pin": (control.pin,),
            "spi_role": (control_role,),
            "spi_function": (control.function,),
            "spi_electrical_type": (control.electrical_type,),
            "data_pin": (data.pin,),
            "data_role": (data_role,),
            "data_function": (data.function,),
            "data_electrical_type": (data.electrical_type,),
            "net": (net,),
        },
    )


def spi_clock_control_data_same_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find one supported SPI clock/control and data pin pair on the same net.

    This opt-in review clue does not prove that a device uses the function names
    as its configured SPI roles. Data-input/output pairs are owned by the more
    specific SPI data-role same-net rule.
    """
    findings: list[Candidate] = []
    for group in spi_role_assignment_groups(observed):
        control_roles = sorted(_SPI_CONTROL_ROLES & group.roles.keys(), key=_ROLE_ORDER.__getitem__)
        data_roles = sorted(_SPI_DATA_ROLES & group.roles.keys(), key=_ROLE_ORDER.__getitem__)
        for control_role in control_roles:
            for data_role in data_roles:
                controls = group.roles[control_role]
                data_endpoints = group.roles[data_role]
                if len(controls) != 1 or len(data_endpoints) != 1:
                    continue
                control, data = controls[0], data_endpoints[0]
                if not control.in_component_inventory or not data.in_component_inventory:
                    continue
                if len(control.nets) != 1 or len(data.nets) != 1:
                    continue
                if control.nets[0] != data.nets[0]:
                    continue
                if control.electrical_type == data.electrical_type == "output":
                    continue
                findings.append(
                    _candidate(group, control_role, data_role, control, data, control.nets[0])
                )
    return tuple(findings)
