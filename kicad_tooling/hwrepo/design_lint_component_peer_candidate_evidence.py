"""Typed generic component-peer sources and their stable finding projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, TypeAlias

from .component_peer_pin_identity import component_peer_pin_identity_context
from .component_peer_pin_models import ComponentPeerPinRuleId
from .component_peer_pin_scan import (
    GENERIC_COMPONENT_PIN_TYPES,
    PeerPinAssignmentOutlier,
    PeerPowerPinAssignmentDivergence,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection


def project_generic_peer_pin_evidence(
    source: PeerPinAssignmentOutlier,
) -> CandidateEvidenceProjection:
    """Project one anchored strict-majority outlier to the established report fields."""
    if source.electrical_type.casefold() not in GENERIC_COMPONENT_PIN_TYPES:
        raise ValueError("Generic peer-pin evidence requires a generic electrical type")
    if source.majority_net is None or not source.outlier_pins or not source.shared_anchor_contacts:
        raise ValueError("Generic peer-pin evidence requires majority, outlier, and anchor data")

    identity = component_peer_pin_identity_context(source)
    return CandidateEvidenceProjection(
        rule_id="component.generic_peer_pin_assignment_outlier",
        evidence={
            **source.assignments,
            **identity.evidence,
            "pin_number": (source.pin_number,),
            "pin_function": (source.pin_function or "",),
            "pin_electrical_type": (source.electrical_type,),
            "majority_net": (source.majority_net,),
            "outlier_pins": source.outlier_pins,
            "shared_anchor_contacts": source.shared_anchor_contacts,
        },
    )


@dataclass(frozen=True, slots=True)
class GenericPeerPinCandidate(Candidate):
    """Internal generic peer finding retaining its immutable scan record."""

    source_evidence: PeerPinAssignmentOutlier

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PeerPinAssignmentOutlier,
        *,
        subject: str,
        message: str,
    ) -> GenericPeerPinCandidate:
        projection = project_generic_peer_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_generic_peer_pin_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Generic peer candidate rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Generic peer evidence must match its typed source projection")


@dataclass(frozen=True, slots=True)
class PeerPinFunctionEvidence:
    """One exact native pin-function observation used by a peer comparison."""

    pin: str
    function: str


@dataclass(frozen=True, slots=True)
class GenericPowerInputDivergenceEvidence:
    """Generic power-input split and the native functions used for comparison."""

    outlier: PeerPinAssignmentOutlier
    pin_functions: tuple[PeerPinFunctionEvidence, ...]

    def __post_init__(self) -> None:
        if self.outlier.electrical_type.casefold() != "power_in":
            raise ValueError("Generic peer power-input evidence requires a power_in pin")
        assignments = tuple(self.outlier.assignments.values())
        if not assignments or any(not nets for nets in assignments):
            raise ValueError("Generic power-input divergence requires assigned peer pins")
        if len(set(assignments)) < 2:
            raise ValueError("Generic power-input divergence requires different assignments")
        expected_pins = tuple(pin.casefold() for pin in self.outlier.assignments)
        observed_pins = tuple(item.pin.casefold() for item in self.pin_functions)
        if observed_pins != expected_pins:
            raise ValueError("Pin-function evidence must cover the exact peer assignments")


@dataclass(frozen=True, slots=True)
class NamedPowerInputDivergenceEvidence:
    """Named power-input peers with different assigned nets."""

    outlier: PeerPinAssignmentOutlier

    def __post_init__(self) -> None:
        _require_named_power_input(self.outlier)
        if any(not nets for nets in self.outlier.assignments.values()):
            raise ValueError("Named power-input divergence requires assigned peers")
        if len({nets for nets in self.outlier.assignments.values()}) < 2:
            raise ValueError("Named power-input divergence requires different assignments")


@dataclass(frozen=True, slots=True)
class NamedPowerInputOpenEvidence:
    """Named power-input peers with both open and assigned pins."""

    outlier: PeerPinAssignmentOutlier

    def __post_init__(self) -> None:
        _require_named_power_input(self.outlier)
        assignments = tuple(self.outlier.assignments.values())
        if not any(not nets for nets in assignments) or not any(assignments):
            raise ValueError("Named power-input open evidence requires open and assigned peers")


@dataclass(frozen=True, slots=True)
class NamedPowerInputAllOpenEvidence:
    """Named power-input peers whose matching pins are all open."""

    outlier: PeerPinAssignmentOutlier

    def __post_init__(self) -> None:
        _require_named_power_input(self.outlier)
        if not self.outlier.assignments or any(self.outlier.assignments.values()):
            raise ValueError("Named all-open evidence requires every peer pin to be open")


PowerInputPeerEvidence: TypeAlias = (
    GenericPowerInputDivergenceEvidence
    | NamedPowerInputDivergenceEvidence
    | NamedPowerInputOpenEvidence
    | NamedPowerInputAllOpenEvidence
)

PowerInputPeerRuleId: TypeAlias = Literal[
    "component.peer_power_input_assignment_divergence",
    "component.peer_power_input_named_assignment_divergence",
    "component.peer_power_input_open_assignment",
    "component.peer_power_input_named_all_open",
]


def _require_named_power_input(outlier: PeerPinAssignmentOutlier) -> None:
    if outlier.electrical_type.casefold() != "power_in" or not outlier.pin_function:
        raise ValueError("Named peer power-input evidence requires its native pin function")


def _named_power_input_evidence(
    outlier: PeerPinAssignmentOutlier,
    rule_id: PowerInputPeerRuleId,
    *,
    all_open: bool = False,
) -> CandidateEvidenceProjection:
    evidence = dict(outlier.assignments)
    if outlier.peer_identity_basis == "part_id":
        evidence.update(
            {
                "peer_identity_basis": (outlier.peer_identity_basis,),
                "peer_identity": (outlier.peer_identity,),
                "peer_symbols": outlier.peer_symbols,
            }
        )
    evidence.update(
        {
            "symbol": (outlier.symbol,),
            "pin_number": (outlier.pin_number,),
            "pin_function": (outlier.pin_function or "",),
            "pin_electrical_type": ("power_in",),
        }
    )
    if all_open or rule_id == "component.peer_power_input_open_assignment":
        evidence["open_peer_pins"] = tuple(
            pin for pin, nets in outlier.assignments.items() if not nets
        )
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


def project_power_input_peer_evidence(
    source: PowerInputPeerEvidence,
) -> CandidateEvidenceProjection:
    """Project typed power-input peer observations to their stable wire fields."""
    if isinstance(source, GenericPowerInputDivergenceEvidence):
        outlier = source.outlier
        return CandidateEvidenceProjection(
            rule_id="component.peer_power_input_assignment_divergence",
            evidence={
                **outlier.assignments,
                "symbol": (outlier.symbol,),
                "pin_number": (outlier.pin_number,),
                "pin_electrical_type": ("power_in",),
                "pin_functions": tuple(
                    f"{item.pin}={item.function}" for item in source.pin_functions
                ),
            },
        )
    if isinstance(source, NamedPowerInputDivergenceEvidence):
        return _named_power_input_evidence(
            source.outlier,
            "component.peer_power_input_named_assignment_divergence",
        )
    if isinstance(source, NamedPowerInputOpenEvidence):
        return _named_power_input_evidence(
            source.outlier,
            "component.peer_power_input_open_assignment",
        )
    return _named_power_input_evidence(
        source.outlier,
        "component.peer_power_input_named_all_open",
        all_open=True,
    )


@dataclass(frozen=True, slots=True)
class PowerInputPeerCandidate(Candidate):
    """Power-input peer finding retaining its exact typed scan record."""

    source_evidence: PowerInputPeerEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PowerInputPeerEvidence,
        *,
        subject: str,
        message: str,
    ) -> PowerInputPeerCandidate:
        projection = project_power_input_peer_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_power_input_peer_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Power-input evidence must match its typed source projection")


@dataclass(frozen=True, slots=True)
class PeerPowerPinDivergenceEvidence:
    """Recognized peer supply or return pins assigned to different nets."""

    divergence: PeerPowerPinAssignmentDivergence

    def __post_init__(self) -> None:
        assignments = tuple(self.divergence.assignments.values())
        if not assignments or any(not nets for nets in assignments):
            raise ValueError("Peer power-pin divergence requires assigned pins")
        if len(set(assignments)) < 2:
            raise ValueError("Peer power-pin divergence requires different assignments")
        if self.divergence.role not in {"supply", "ground/return"}:
            raise ValueError("Peer power-pin divergence requires a recognized power role")


def project_peer_power_pin_divergence(
    source: PeerPowerPinDivergenceEvidence,
) -> CandidateEvidenceProjection:
    """Project typed recognized-power peer assignments to established fields."""
    group = source.divergence
    evidence = dict(group.assignments)
    if group.peer_identity_basis == "part_id":
        evidence.update(
            {
                "peer_identity_basis": (group.peer_identity_basis,),
                "peer_identity": (group.peer_identity,),
                "peer_symbols": group.peer_symbols,
            }
        )
    evidence.update(
        {
            "symbol": (group.symbol,),
            "pin_number": (group.pin_number,),
            "pin_function": (group.function,),
            "peer_role": (group.role,),
        }
    )
    return CandidateEvidenceProjection(
        rule_id="component.peer_power_pin_assignment_divergence",
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class PeerPowerPinDivergenceCandidate(Candidate):
    """Power-pin finding retaining its recognized-peer divergence record."""

    source_evidence: PeerPowerPinDivergenceEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PeerPowerPinDivergenceEvidence,
        *,
        subject: str,
        message: str,
    ) -> PeerPowerPinDivergenceCandidate:
        projection = project_peer_power_pin_divergence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_peer_power_pin_divergence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Peer power-pin evidence must match its typed source projection")


PeerUnconnectedPinKind: TypeAlias = Literal[
    "power_output",
    "signal_output",
    "signal_input",
    "bidirectional",
]


@dataclass(frozen=True, slots=True)
class PeerUnconnectedPinEvidence:
    """One open peer-pin assignment with its native electrical role."""

    kind: PeerUnconnectedPinKind
    outlier: PeerPinAssignmentOutlier

    def __post_init__(self) -> None:
        expected_types = {
            "power_output": frozenset({"power_out"}),
            "signal_output": frozenset({"output"}),
            "signal_input": frozenset({"input", "input_low"}),
            "bidirectional": frozenset({"bidirectional"}),
        }
        if self.outlier.electrical_type.casefold() not in expected_types[self.kind]:
            raise ValueError("Unconnected peer evidence must match its native electrical role")
        assignments = tuple(self.outlier.assignments.values())
        if not any(not nets for nets in assignments) or not any(assignments):
            raise ValueError("Unconnected peer evidence requires both open and assigned pins")


_UNCONNECTED_PEER_RULE_IDS: Mapping[PeerUnconnectedPinKind, ComponentPeerPinRuleId] = (
    MappingProxyType(
        {
            "power_output": "component.peer_power_output_unconnected",
            "signal_output": "component.peer_signal_output_unconnected",
            "signal_input": "component.peer_signal_input_unconnected",
            "bidirectional": "component.peer_bidirectional_pin_unconnected",
        }
    )
)


def project_peer_unconnected_pin_evidence(
    source: PeerUnconnectedPinEvidence,
) -> CandidateEvidenceProjection:
    """Project a typed unconnected-peer observation to established fields."""
    group = source.outlier
    identity = component_peer_pin_identity_context(group)
    pin_type = "power_out" if source.kind == "power_output" else group.electrical_type
    return CandidateEvidenceProjection(
        rule_id=_UNCONNECTED_PEER_RULE_IDS[source.kind],
        evidence={
            **group.assignments,
            **identity.evidence,
            "pin_number": (group.pin_number,),
            "pin_electrical_type": (pin_type,),
            "pin_function": (group.pin_function or "",),
            "unassigned_pins": tuple(pin for pin, nets in group.assignments.items() if not nets),
        },
    )


@dataclass(frozen=True, slots=True)
class UnconnectedPeerPinCandidate(Candidate):
    """Unconnected peer-pin finding retaining its typed scan record."""

    source_evidence: PeerUnconnectedPinEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PeerUnconnectedPinEvidence,
        *,
        subject: str,
        message: str,
    ) -> UnconnectedPeerPinCandidate:
        projection = project_peer_unconnected_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_peer_unconnected_pin_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Unconnected peer evidence must match its typed source projection")
