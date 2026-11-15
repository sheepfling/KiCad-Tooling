"""Review generic pin-function metadata on one exact-part connector peer."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_footprint_peer_groups import (
    ConnectorFootprintPeerGroup,
    connector_footprint_peer_candidate_groups,
)
from .connector_footprint_peer_pin_function_support import (
    ConnectorFootprintPeerPinFunctionObservation,
    PeerPinFunctionRows,
    connector_footprint_peer_pin_function_rows,
    peer_pin_rows_share_one_common_assignment,
)
from .connector_identity import (
    has_meaningful_pin_function,
    native_pin_metadata_is_missing,
    pin_function_is_generic,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_function_metadata_incomplete"


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinFunctionMetadataEvidence:
    """Validated source evidence for one incomplete peer pin-function label."""

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
        _validate_metadata_evidence(self)

    @property
    def projection(self) -> CandidateEvidenceProjection:
        """Project stable review fields from validated native peer metadata."""
        assert self.group.part_id is not None
        named_functions = tuple(
            item.function.strip()
            for item in self.observations
            if has_meaningful_pin_function(item.function)
        )
        if len({function.casefold() for function in named_functions}) != 1:
            raise ValueError("Connector peer metadata evidence needs one meaningful function")
        return CandidateEvidenceProjection(
            rule_id=RULE_ID,
            evidence={
                "value": (self.group.value,),
                "footprint": (self.group.footprint,),
                "part_id": (self.group.part_id,),
                "peer_identity_basis": ("part_id",),
                "pin_number": (self.pin_number,),
                "peer_pin_functions": tuple(
                    f"{item.pin}={_function_evidence_value(item.function)}"
                    for item in self.observations
                ),
                "generic_function_peers": tuple(
                    item.reference
                    for item in self.observations
                    if not native_pin_metadata_is_missing(item.function)
                    and pin_function_is_generic(item.function)
                ),
                "missing_function_peers": tuple(
                    item.reference
                    for item in self.observations
                    if native_pin_metadata_is_missing(item.function)
                ),
                "named_function": (named_functions[0].strip(),),
                "peer_pin_electrical_types": tuple(
                    f"{item.pin}={item.electrical_type}" for item in self.observations
                ),
                "assignments": tuple(f"{item.pin}={item.nets[0]}" for item in self.observations),
                "symbols": tuple(f"{item.reference}={item.symbol}" for item in self.observations),
                "common_anchor_pin_numbers": self.common_anchor_pin_numbers,
            },
        )


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinFunctionMetadataCandidate(Candidate):
    """Review candidate whose report fields stay bound to native source rows."""

    source_evidence: ConnectorFootprintPeerPinFunctionMetadataEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorFootprintPeerPinFunctionMetadataEvidence,
    ) -> ConnectorFootprintPeerPinFunctionMetadataCandidate:
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
        expected_subject = (
            f"{self.source_evidence.group.value} [{self.source_evidence.group.footprint}] "
            f"pin {self.source_evidence.pin_number}"
        )
        if (
            self.rule_id != projection.rule_id
            or self.subject != expected_subject
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError("Connector peer metadata finding must match its native source rows")


def connector_footprint_peer_pin_function_metadata_gaps(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Review incomplete pin functions beside an anchored exact-part peer role.

    Require a shared nonempty PART_ID, matching value and footprint, complete
    identical pin inventory, complete electrical-type metadata, matching peer
    types, one generic-or-missing-versus-named function mismatch, a common target
    assignment, and a separate meaningful-function/common-net anchor. This does
    not prove which function is correct or that the target pin must be connected.
    """
    candidates: list[Candidate] = []
    groups = connector_footprint_peer_candidate_groups(
        observed,
        declared_references,
        include_part_id_peers=True,
    )
    for group in groups:
        mismatch = _eligible_metadata_gap(observed, group)
        if mismatch is None:
            continue
        pin_number, observations, anchors = mismatch
        evidence = ConnectorFootprintPeerPinFunctionMetadataEvidence(
            observed=observed,
            group=group,
            pin_number=pin_number,
            observations=observations,
            common_anchor_pin_numbers=anchors,
            declared_references=declared_references,
        )
        candidates.append(
            ConnectorFootprintPeerPinFunctionMetadataCandidate.from_source_evidence(evidence)
        )
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


def _eligible_metadata_gap(
    observed: NetlistContract,
    group: ConnectorFootprintPeerGroup,
) -> tuple[str, tuple[ConnectorFootprintPeerPinFunctionObservation, ...], tuple[str, ...]] | None:
    """Return one anchored generic-or-missing-to-named metadata gap, if present."""
    if group.part_id is None or not group.part_id.strip():
        return None
    pin_rows: PeerPinFunctionRows | None = connector_footprint_peer_pin_function_rows(
        observed,
        group,
        allow_missing_functions=True,
    )
    if pin_rows is None:
        return None
    mismatches = tuple(
        (number, rows)
        for number, rows in pin_rows
        if len({_function_key(item.function) for item in rows}) > 1
    )
    if len(mismatches) != 1:
        return None
    pin_number, target_rows = mismatches[0]
    missing_rows = tuple(
        item for item in target_rows if native_pin_metadata_is_missing(item.function)
    )
    generic_rows = tuple(
        item
        for item in target_rows
        if not native_pin_metadata_is_missing(item.function)
        and pin_function_is_generic(item.function)
    )
    named_functions = {
        item.function.strip().casefold()
        for item in target_rows
        if has_meaningful_pin_function(item.function)
    }
    if len(named_functions) != 1 or (not missing_rows and not generic_rows):
        return None
    if missing_rows and generic_rows:
        return None
    if any(
        number.casefold() != pin_number.casefold()
        and any(native_pin_metadata_is_missing(item.function) for item in rows)
        for number, rows in pin_rows
    ):
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
                and all(has_meaningful_pin_function(item.function) for item in rows)
                and len({_function_key(item.function) for item in rows}) == 1
                and peer_pin_rows_share_one_common_assignment(rows)
            ),
            key=lambda number: (number.casefold(), number),
        )
    )
    return (pin_number, target_rows, anchors) if anchors else None


def _candidate_message(
    evidence: ConnectorFootprintPeerPinFunctionMetadataEvidence,
) -> str:
    """Explain the metadata gap without inferring pinout or connectivity intent."""
    missing_function = any(
        native_pin_metadata_is_missing(item.function) for item in evidence.observations
    )
    discrepancy = (
        "one peer omits its native function name while another supplies a meaningful name"
        if missing_function
        else "one peer uses a generic function while another supplies a meaningful name"
    )
    return (
        "Fitted connector symbols with the same exact PART_ID, value, footprint, and complete "
        "pin inventory assign this pin to one common net, but "
        + discrepancy
        + ". Review the approved part pinout and symbol metadata; "
        "the similarity and assignment clues do not establish which function is correct or that "
        "the pin must be connected."
    )


def _function_evidence_value(function: str) -> str:
    return "<missing>" if native_pin_metadata_is_missing(function) else function


def _function_key(function: str) -> str | None:
    return None if native_pin_metadata_is_missing(function) else function.strip().casefold()


def _validate_metadata_evidence(
    evidence: ConnectorFootprintPeerPinFunctionMetadataEvidence,
) -> None:
    """Reject metadata evidence when the source group or evaluated rows changed."""
    groups = connector_footprint_peer_candidate_groups(
        evidence.observed,
        evidence.declared_references,
        include_part_id_peers=True,
    )
    if evidence.group.part_id is None or evidence.group not in groups:
        raise ValueError("Connector peer metadata evidence requires a current exact PART_ID group")
    mismatch = _eligible_metadata_gap(evidence.observed, evidence.group)
    if mismatch is None:
        raise ValueError(
            "Connector peer metadata evidence requires one anchored generic-or-missing mismatch"
        )
    pin_number, observations, anchors = mismatch
    if (
        evidence.pin_number != pin_number
        or evidence.observations != observations
        or evidence.common_anchor_pin_numbers != anchors
    ):
        raise ValueError("Connector peer metadata evidence must match current native pin rows")
