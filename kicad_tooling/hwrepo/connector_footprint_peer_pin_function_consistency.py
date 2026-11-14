"""Review native pin-function disagreement across exact-part connector peers."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_footprint_peer_groups import (
    ConnectorFootprintPeerGroup,
    connector_footprint_peer_candidate_groups,
)
from .connector_footprint_peer_pin_function_support import (
    ConnectorFootprintPeerPinFunctionObservation,
    connector_footprint_peer_pin_function_rows,
    peer_pin_rows_share_one_common_assignment,
)
from .connector_identity import pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_function_disagreement"


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinFunctionEvidence:
    """Validated native evidence for one exact-part pin-function disagreement."""

    observed: NetlistContract
    group: ConnectorFootprintPeerGroup
    pin_number: str
    observations: tuple[ConnectorFootprintPeerPinFunctionObservation, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    declared_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "common_anchor_pin_numbers", tuple(self.common_anchor_pin_numbers))
        object.__setattr__(self, "declared_references", tuple(self.declared_references))
        _validate_function_evidence(self)

    @property
    def projection(self) -> CandidateEvidenceProjection:
        """Project stable fields directly from the validated native source."""
        assert self.group.part_id is not None
        return CandidateEvidenceProjection(
            rule_id=RULE_ID,
            evidence={
                "value": (self.group.value,),
                "footprint": (self.group.footprint,),
                "part_id": (self.group.part_id,),
                "peer_identity_basis": ("part_id",),
                "pin_number": (self.pin_number,),
                "peer_pin_functions": tuple(
                    f"{item.pin}={item.function}" for item in self.observations
                ),
                "peer_pin_electrical_types": tuple(
                    f"{item.pin}={item.electrical_type}" for item in self.observations
                ),
                "assignments": tuple(f"{item.pin}={item.nets[0]}" for item in self.observations),
                "symbols": tuple(f"{item.reference}={item.symbol}" for item in self.observations),
                "common_anchor_pin_numbers": self.common_anchor_pin_numbers,
            },
        )


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinFunctionCandidate(Candidate):
    """Review candidate whose public fields remain bound to the native source."""

    source_evidence: ConnectorFootprintPeerPinFunctionEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorFootprintPeerPinFunctionEvidence,
    ) -> ConnectorFootprintPeerPinFunctionCandidate:
        projection = source_evidence.projection
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.group.value} [{source_evidence.group.footprint}] "
                f"pin {source_evidence.pin_number}"
            ),
            message=_candidate_message(source_evidence),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = self.source_evidence.projection
        if (
            self.rule_id != projection.rule_id
            or self.subject
            != (
                f"{self.source_evidence.group.value} [{self.source_evidence.group.footprint}] "
                f"pin {self.source_evidence.pin_number}"
            )
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError(
                "Connector peer function finding must match its native source evidence"
            )


def connector_footprint_peer_pin_function_disagreements(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Review one named pin-function mismatch across fitted exact-part aliases.

    Require a matching nonempty PART_ID, value, footprint, and complete pin
    inventory. Every pin's electrical type must agree across peers. Exactly one
    target pin may have differing meaningful function text; that pin must have
    one exact common net assignment and another common pin is required as an
    identity anchor. This is a review cue, not proof of a library or wiring fault.
    """
    candidates: list[Candidate] = []
    groups = connector_footprint_peer_candidate_groups(
        observed,
        declared_references,
        include_part_id_peers=True,
    )
    for group in groups:
        if group.part_id is None:
            continue
        mismatch = _eligible_function_mismatch(observed, group)
        if mismatch is None:
            continue
        pin_number, observations, anchors = mismatch
        evidence = ConnectorFootprintPeerPinFunctionEvidence(
            observed=observed,
            group=group,
            pin_number=pin_number,
            observations=observations,
            common_anchor_pin_numbers=anchors,
            declared_references=declared_references,
        )
        candidates.append(ConnectorFootprintPeerPinFunctionCandidate.from_source_evidence(evidence))

    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(item.evidence["peer_pin_functions"]),
                tuple(item.evidence["part_id"]),
            ),
        )
    )


def _eligible_function_mismatch(
    observed: NetlistContract,
    group: ConnectorFootprintPeerGroup,
) -> tuple[str, tuple[ConnectorFootprintPeerPinFunctionObservation, ...], tuple[str, ...]] | None:
    """Return the one anchored meaningful function mismatch, if fully supported."""
    if group.part_id is None or not group.part_id.strip():
        return None
    pin_rows = connector_footprint_peer_pin_function_rows(observed, group)
    if pin_rows is None:
        return None
    function_mismatches = tuple(
        (pin_number, rows)
        for pin_number, rows in pin_rows
        if len({item.function.strip().casefold() for item in rows}) > 1
    )
    if len(function_mismatches) != 1:
        return None
    pin_number, target_rows = function_mismatches[0]
    if any(pin_function_is_generic(item.function) for item in target_rows):
        return None
    if any(
        len({item.electrical_type.strip().casefold() for item in rows}) != 1 for _, rows in pin_rows
    ):
        return None
    if not peer_pin_rows_share_one_common_assignment(target_rows):
        return None

    anchors = tuple(
        sorted(
            (
                number
                for number, rows in pin_rows
                if number.casefold() != pin_number.casefold()
                and len({item.function.strip().casefold() for item in rows}) == 1
                and peer_pin_rows_share_one_common_assignment(rows)
            ),
            key=lambda number: (number.casefold(), number),
        )
    )
    return (pin_number, target_rows, anchors) if anchors else None


def _candidate_message(
    evidence: ConnectorFootprintPeerPinFunctionEvidence,
) -> str:
    """Describe the review cue without choosing which symbol function is correct."""
    return (
        "Fitted connector symbols with the same exact PART_ID, value, footprint, and "
        "complete pin inventory assign this pin to the same net but report different "
        "non-generic native pin functions. Review the approved part pinout and symbol "
        "definitions; the identity and net clues do not establish which function is correct."
    )


def _validate_function_evidence(
    evidence: ConnectorFootprintPeerPinFunctionEvidence,
) -> None:
    """Reject a candidate when its group, target, peers, or anchors changed."""
    current_groups = connector_footprint_peer_candidate_groups(
        evidence.observed,
        evidence.declared_references,
        include_part_id_peers=True,
    )
    if evidence.group.part_id is None or evidence.group not in current_groups:
        raise ValueError("Connector peer function evidence requires a current exact PART_ID group")
    mismatch = _eligible_function_mismatch(evidence.observed, evidence.group)
    if mismatch is None:
        raise ValueError("Connector peer function evidence requires one anchored function mismatch")
    pin_number, observations, anchors = mismatch
    if (
        evidence.pin_number != pin_number
        or evidence.observations != observations
        or evidence.common_anchor_pin_numbers != anchors
    ):
        raise ValueError("Connector peer function evidence must match current native pin metadata")
