"""Source-bound evidence for connector footprint-peer metadata findings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeAlias

from .connector_footprint_peer_anchors import connector_footprint_peer_common_anchor_pin_numbers
from .connector_footprint_peer_assignments import (
    connector_footprint_peer_pin_assignments,
    connector_footprint_peer_pin_net_map,
)
from .connector_footprint_peer_groups import (
    ConnectorFootprintPeerGroup,
    complete_connector_footprint_peer_pin_inventory,
    connector_footprint_peer_candidate_groups,
)
from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinScanSource
from .connector_identity import (
    PeerAssignmentPartition,
    native_pin_metadata_is_missing,
    partition_peer_assignments,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection

ConnectorFootprintPeerMetadataKind: TypeAlias = Literal[
    "known_split",
    "known_open",
    "missing_split",
    "missing_open",
]

_RULE_IDS: Mapping[ConnectorFootprintPeerMetadataKind, DesignLintRuleId] = {
    "known_split": "connector.footprint_peer_pin_metadata_assignment_divergence",
    "known_open": "connector.footprint_peer_pin_metadata_open_outlier",
    "missing_split": "connector.footprint_peer_pin_missing_metadata_assignment_divergence",
    "missing_open": "connector.footprint_peer_pin_missing_metadata_open_outlier",
}


def _scope_references(scope: PeerAssignmentPartition) -> tuple[str, ...]:
    return tuple(
        sorted(
            {pin.rpartition(".")[0] for pin in scope.assignments_by_pin},
            key=lambda item: (item.casefold(), item),
        )
    )


def _non_missing_metadata_values(
    observations: tuple[ConnectorFootprintPeerPinMetadataObservation, ...],
    field: Literal["pin_function", "pin_electrical_type"],
) -> set[str]:
    values: set[str] = set()
    for observation in observations:
        value = observation.function if field == "pin_function" else observation.electrical_type
        if value is not None and not native_pin_metadata_is_missing(value):
            values.add(value.strip().casefold())
    return values


def _metadata_evidence_value(value: str | None, *, missing_state: bool) -> str:
    if not missing_state:
        return value or ""
    if native_pin_metadata_is_missing(value):
        return "<missing>"
    return (value or "").strip()


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinMetadataObservation:
    """One source pin's exact native role metadata and peer assignment."""

    reference: str
    pin: str
    function: str | None
    electrical_type: str | None
    symbol: str
    assignments: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignments", tuple(self.assignments))


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerMetadataEvidence:
    """A metadata comparison bound to its netlist, inventory, and peer scope."""

    source: ConnectorFootprintPeerPinScanSource
    group: ConnectorFootprintPeerGroup
    scope: PeerAssignmentPartition
    kind: ConnectorFootprintPeerMetadataKind
    pin_number: str
    observations: tuple[ConnectorFootprintPeerPinMetadataObservation, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    metadata_mismatch_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "common_anchor_pin_numbers", tuple(self.common_anchor_pin_numbers))
        object.__setattr__(self, "metadata_mismatch_fields", tuple(self.metadata_mismatch_fields))
        _validate_current_metadata_evidence(self)

    @classmethod
    def from_scan(
        cls,
        *,
        source: ConnectorFootprintPeerPinScanSource,
        group: ConnectorFootprintPeerGroup,
        scope: PeerAssignmentPartition,
        kind: ConnectorFootprintPeerMetadataKind,
        pin_number: str,
        common_anchor_pin_numbers: tuple[str, ...],
        metadata_mismatch_fields: tuple[str, ...] = (),
    ) -> ConnectorFootprintPeerMetadataEvidence:
        """Capture typed metadata rows from one existing native scan partition."""
        observed = source.observed
        functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
        electrical_types = {
            pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
        }
        symbols = {
            reference.casefold(): value for reference, value in observed.component_symbols.items()
        }
        observations = tuple(
            ConnectorFootprintPeerPinMetadataObservation(
                reference=pin.rpartition(".")[0],
                pin=pin,
                function=functions.get(pin.casefold()),
                electrical_type=electrical_types.get(pin.casefold()),
                symbol=symbols.get(pin.rpartition(".")[0].casefold(), ""),
                assignments=tuple(scope.assignments_by_pin[pin]),
            )
            for pin in sorted(
                scope.assignments_by_pin,
                key=lambda item: (item.casefold(), item),
            )
        )
        return cls(
            source=source,
            group=group,
            scope=scope,
            kind=kind,
            pin_number=pin_number,
            observations=observations,
            common_anchor_pin_numbers=common_anchor_pin_numbers,
            metadata_mismatch_fields=metadata_mismatch_fields,
        )


def _validate_current_metadata_evidence(
    evidence: ConnectorFootprintPeerMetadataEvidence,
) -> None:
    source = evidence.source
    observed = source.observed
    pin_nets = connector_footprint_peer_pin_net_map(observed)
    include_part_id_peers = evidence.kind in {"missing_split", "missing_open"}
    current_groups = connector_footprint_peer_candidate_groups(
        observed,
        source.declared_references,
        include_part_id_peers=include_part_id_peers,
    )
    if evidence.group not in current_groups:
        raise ValueError("Connector peer metadata identity must match the current fitted group")

    inventory = complete_connector_footprint_peer_pin_inventory(observed, evidence.group.references)
    if inventory is None:
        raise ValueError("Connector peer metadata requires a current complete pin inventory")
    pin_number_key = evidence.pin_number.casefold()
    if pin_number_key not in {item.casefold() for item in inventory.pin_numbers}:
        raise ValueError("Connector peer metadata pin must remain in the current inventory")
    displayed_target = inventory.displayed_numbers_by_reference[
        evidence.group.references[0].casefold()
    ][pin_number_key]
    if displayed_target != evidence.pin_number:
        raise ValueError("Connector peer metadata must retain the native display pin number")

    group_assignments: dict[str, tuple[str, ...]] = {}
    for reference in evidence.group.references:
        display_number = inventory.displayed_numbers_by_reference[reference.casefold()][
            pin_number_key
        ]
        pin = f"{reference}.{display_number}"
        group_assignments[pin] = connector_footprint_peer_pin_assignments(pin_nets, pin)
    current_scopes = partition_peer_assignments(group_assignments, source.peer_assignment_groups)
    if evidence.scope not in current_scopes:
        raise ValueError("Connector peer metadata scope must match the current authored peer group")

    scope_references = _scope_references(evidence.scope)
    observation_references = tuple(item.reference for item in evidence.observations)
    if observation_references != scope_references or len(scope_references) < 2:
        raise ValueError("Connector peer metadata must retain the exact scoped peer set")

    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
    }
    symbols = {
        reference.casefold(): value for reference, value in observed.component_symbols.items()
    }
    for observation in evidence.observations:
        display_number = inventory.displayed_numbers_by_reference[observation.reference.casefold()][
            pin_number_key
        ]
        expected_pin = f"{observation.reference}.{display_number}"
        if observation.pin != expected_pin:
            raise ValueError("Connector peer metadata must retain each native display pin")
        if (
            observation.function != functions.get(expected_pin.casefold())
            or observation.electrical_type != electrical_types.get(expected_pin.casefold())
            or observation.symbol != symbols.get(observation.reference.casefold())
            or observation.assignments != evidence.scope.assignments_by_pin.get(expected_pin)
            or observation.assignments
            != connector_footprint_peer_pin_assignments(pin_nets, expected_pin)
        ):
            raise ValueError("Connector peer metadata must match current native records")

    assignments = tuple(item.assignments for item in evidence.observations)
    missing_by_observation = tuple(
        tuple(
            field
            for field, value in (
                ("pin_function", item.function),
                ("pin_electrical_type", item.electrical_type),
            )
            if native_pin_metadata_is_missing(value)
        )
        for item in evidence.observations
    )
    if evidence.kind in {"known_split", "known_open"}:
        if any(missing_by_observation):
            raise ValueError("Known connector metadata findings require complete native metadata")
        expected_mismatches = tuple(
            field
            for field in ("pin_function", "pin_electrical_type")
            if len(_non_missing_metadata_values(evidence.observations, field)) > 1
        )
        if expected_mismatches != evidence.metadata_mismatch_fields or not expected_mismatches:
            raise ValueError("Connector peer metadata mismatch fields must match native values")
    elif not any(missing_by_observation):
        raise ValueError("Missing connector metadata findings require absent native metadata")

    if evidence.kind in {"known_split", "missing_split"}:
        valid_assignments = (
            all(len(nets) == 1 for nets in assignments)
            and len({nets[0] for nets in assignments if nets}) > 1
        )
    else:
        assigned = tuple(nets for nets in assignments if nets)
        valid_assignments = (
            bool(assigned)
            and len(assigned) < len(assignments)
            and all(len(nets) == 1 for nets in assigned)
            and len({nets[0] for nets in assigned}) == 1
        )
    if not valid_assignments:
        raise ValueError("Connector peer metadata assignments no longer match this finding state")

    if evidence.kind == "missing_open":
        for field in ("pin_function", "pin_electrical_type"):
            if len(_non_missing_metadata_values(evidence.observations, field)) > 1:
                raise ValueError("Missing metadata open findings require agreement where present")

    current_anchors = connector_footprint_peer_common_anchor_pin_numbers(
        inventory.pin_numbers,
        evidence.pin_number,
        scope_references,
        inventory.displayed_numbers_by_reference,
        pin_nets,
    )
    if current_anchors != evidence.common_anchor_pin_numbers or not current_anchors:
        raise ValueError("Connector peer metadata anchor pins must match current native nets")


def project_connector_footprint_peer_metadata_evidence(
    source: ConnectorFootprintPeerMetadataEvidence,
) -> CandidateEvidenceProjection:
    """Project the existing rule-specific evidence fields from typed source data."""
    _validate_current_metadata_evidence(source)
    evidence: dict[str, tuple[str, ...]] = {
        "value": (source.group.value,),
        "footprint": (source.group.footprint,),
        "pin_number": (source.pin_number,),
    }
    if source.kind in {"known_split", "known_open"}:
        evidence["metadata_mismatch_fields"] = source.metadata_mismatch_fields
    else:
        evidence["missing_metadata"] = tuple(
            f"{item.pin}: {field}"
            for item in source.observations
            for field, value in (
                ("pin_function", item.function),
                ("pin_electrical_type", item.electrical_type),
            )
            if native_pin_metadata_is_missing(value)
        )
        evidence["peer_identity_basis"] = (
            "part_id" if source.group.part_id is not None else "footprint_value",
        )
        if source.group.part_id is not None:
            evidence["part_id"] = (source.group.part_id,)

    missing = source.kind in {"missing_split", "missing_open"}
    evidence["peer_pin_metadata"] = tuple(
        f"{item.pin}: function={_metadata_evidence_value(item.function, missing_state=missing)}; "
        f"electrical_type={_metadata_evidence_value(item.electrical_type, missing_state=missing)}"
        for item in source.observations
    )
    assignment_key = "assignments"
    evidence[assignment_key] = tuple(
        f"{item.pin}={item.assignments[0] if item.assignments else '<unassigned>'}"
        for item in source.observations
    )
    symbols_key = "symbols" if source.kind == "missing_open" else "peer_symbols"
    evidence[symbols_key] = tuple(f"{item.reference}={item.symbol}" for item in source.observations)
    evidence["common_anchor_pin_numbers"] = source.common_anchor_pin_numbers
    if source.scope.peer_assignment_group is not None:
        evidence["peer_assignment_group"] = (source.scope.peer_assignment_group,)
        evidence["peer_assignment_basis"] = source.scope.peer_assignment_basis
    return CandidateEvidenceProjection(rule_id=_RULE_IDS[source.kind], evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerMetadataCandidate(Candidate):
    """Candidate projected from one current connector peer metadata comparison."""

    source_evidence: ConnectorFootprintPeerMetadataEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorFootprintPeerMetadataEvidence,
        *,
        subject: str,
        message: str,
    ) -> ConnectorFootprintPeerMetadataCandidate:
        projection = project_connector_footprint_peer_metadata_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_footprint_peer_metadata_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError(
                "Connector peer metadata fields must match the current source projection"
            )
