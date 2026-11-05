"""Typed source evidence for SPI same-net candidate variants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .spi_role_assignments import (
    SpiRoleAssignmentGroup,
    SpiRolePinAssignment,
    spi_channel_label,
    spi_role_assignment_groups,
)

SPI_DATA_ROLES_SAME_NET_RULE_ID: DesignLintRuleId = "bus.spi_data_input_output_same_net"
SPI_CLOCK_DATA_SAME_NET_RULE_ID: DesignLintRuleId = "bus.spi_clock_control_data_same_net"
SPI_CLOCK_SELECT_SAME_NET_RULE_ID: DesignLintRuleId = "bus.spi_clock_chip_select_same_net"

SpiControlRole = Literal["clock", "chip_select"]
SpiDataRole = Literal["data_input", "data_output"]


def _require_current_group(
    observed: NetlistContract,
    group: SpiRoleAssignmentGroup,
) -> None:
    matches = tuple(
        current
        for current in spi_role_assignment_groups(observed)
        if current.reference.casefold() == group.reference.casefold()
        and current.channel == group.channel
    )
    if len(matches) != 1 or matches[0] != group:
        raise ValueError("SPI role group must match the current native netlist")


def _require_role_endpoint(
    group: SpiRoleAssignmentGroup,
    role: str,
    endpoint: SpiRolePinAssignment,
) -> None:
    matches = group.roles.get(role, ())
    if len(matches) != 1 or matches[0] != endpoint:
        raise ValueError("SPI evidence requires one current endpoint for each selected role")
    if not endpoint.in_component_inventory or len(endpoint.nets) != 1:
        raise ValueError("SPI evidence requires an inventoried pin with one exact net")


def _require_non_output_conflict(
    left: SpiRolePinAssignment,
    right: SpiRolePinAssignment,
) -> None:
    if left.electrical_type == right.electrical_type == "output":
        raise ValueError("Two native SPI outputs are excluded from same-net findings")


@dataclass(frozen=True, slots=True)
class SpiDataRolesSameNetEvidence:
    """One fitted SPI IC data-input/output pair on a case-insensitive net match."""

    observed: NetlistContract
    group: SpiRoleAssignmentGroup
    input_data: SpiRolePinAssignment
    output_data: SpiRolePinAssignment
    net: str

    def __post_init__(self) -> None:
        _require_current_group(self.observed, self.group)
        _require_role_endpoint(self.group, "data_input", self.input_data)
        _require_role_endpoint(self.group, "data_output", self.output_data)
        if self.input_data.nets[0] != self.net:
            raise ValueError("SPI data evidence must preserve the input pin's native net name")
        if self.input_data.nets[0].casefold() != self.output_data.nets[0].casefold():
            raise ValueError("SPI data endpoints must resolve to the same native net")
        _require_non_output_conflict(self.input_data, self.output_data)


@dataclass(frozen=True, slots=True)
class SpiClockDataSameNetEvidence:
    """One fitted SPI control and data pair on one exact native net."""

    observed: NetlistContract
    group: SpiRoleAssignmentGroup
    control_role: SpiControlRole
    data_role: SpiDataRole
    control: SpiRolePinAssignment
    data: SpiRolePinAssignment
    net: str

    def __post_init__(self) -> None:
        _require_current_group(self.observed, self.group)
        _require_role_endpoint(self.group, self.control_role, self.control)
        _require_role_endpoint(self.group, self.data_role, self.data)
        if self.control.nets[0] != self.net or self.data.nets[0] != self.net:
            raise ValueError("SPI control/data evidence must match both exact native assignments")
        _require_non_output_conflict(self.control, self.data)


@dataclass(frozen=True, slots=True)
class SpiClockSelectSameNetEvidence:
    """One fitted SPI clock and chip-select pair on one exact native net."""

    observed: NetlistContract
    group: SpiRoleAssignmentGroup
    clock: SpiRolePinAssignment
    chip_select: SpiRolePinAssignment
    net: str

    def __post_init__(self) -> None:
        _require_current_group(self.observed, self.group)
        _require_role_endpoint(self.group, "clock", self.clock)
        _require_role_endpoint(self.group, "chip_select", self.chip_select)
        if self.clock.nets[0] != self.net or self.chip_select.nets[0] != self.net:
            raise ValueError("SPI clock/select evidence must match both exact native assignments")
        _require_non_output_conflict(self.clock, self.chip_select)


SpiSameNetEvidence: TypeAlias = (
    SpiDataRolesSameNetEvidence | SpiClockDataSameNetEvidence | SpiClockSelectSameNetEvidence
)


def project_spi_same_net_evidence(
    source: SpiSameNetEvidence,
) -> CandidateEvidenceProjection:
    """Project typed SPI source variants into their established report fields."""
    if isinstance(source, SpiDataRolesSameNetEvidence):
        channel = spi_channel_label(source.group.channel)
        return CandidateEvidenceProjection(
            rule_id=SPI_DATA_ROLES_SAME_NET_RULE_ID,
            evidence={
                "component": (source.group.reference,),
                "channel": (channel,),
                "controller_to_peripheral_pin": (source.input_data.pin,),
                "controller_to_peripheral_function": (source.input_data.function,),
                "controller_to_peripheral_type": (source.input_data.electrical_type,),
                "peripheral_to_controller_pin": (source.output_data.pin,),
                "peripheral_to_controller_function": (source.output_data.function,),
                "peripheral_to_controller_type": (source.output_data.electrical_type,),
                "net": (source.net,),
            },
        )
    if isinstance(source, SpiClockDataSameNetEvidence):
        channel = spi_channel_label(source.group.channel)
        return CandidateEvidenceProjection(
            rule_id=SPI_CLOCK_DATA_SAME_NET_RULE_ID,
            evidence={
                "component": (source.group.reference,),
                "channel": (channel,),
                "spi_role_pin": (source.control.pin,),
                "spi_role": (source.control_role,),
                "spi_function": (source.control.function,),
                "spi_electrical_type": (source.control.electrical_type,),
                "data_pin": (source.data.pin,),
                "data_role": (source.data_role,),
                "data_function": (source.data.function,),
                "data_electrical_type": (source.data.electrical_type,),
                "net": (source.net,),
            },
        )
    return CandidateEvidenceProjection(
        rule_id=SPI_CLOCK_SELECT_SAME_NET_RULE_ID,
        evidence={
            "component": (source.group.reference,),
            "channel": (spi_channel_label(source.group.channel),),
            "clock_pin": (source.clock.pin,),
            "clock_function": (source.clock.function,),
            "clock_electrical_type": (source.clock.electrical_type,),
            "chip_select_pin": (source.chip_select.pin,),
            "chip_select_function": (source.chip_select.function,),
            "chip_select_electrical_type": (source.chip_select.electrical_type,),
            "net": (source.net,),
        },
    )


@dataclass(frozen=True, slots=True)
class SpiSameNetCandidate(Candidate):
    """Candidate whose SPI role pair remains bound to its native netlist."""

    source_evidence: SpiSameNetEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SpiSameNetEvidence,
        *,
        subject: str,
        message: str,
    ) -> SpiSameNetCandidate:
        projection = project_spi_same_net_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_spi_same_net_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("SPI same-net fields must match their typed source projection")
