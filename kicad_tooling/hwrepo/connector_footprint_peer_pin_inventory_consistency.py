"""Review one named pin present in only one exact-part connector peer symbol."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import TypeAlias

from .connector_footprint_peer_groups import (
    ConnectorFootprintPeerGroup,
    complete_connector_footprint_peer_pin_inventories,
    connector_footprint_peer_candidate_groups,
)
from .connector_identity import native_pin_metadata_is_missing, pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_inventory_disagreement"


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerInventoryObservation:
    """Native function, type, and assignment for one shared or extra pin."""

    reference: str
    pin: str
    function: str
    electrical_type: str
    nets: tuple[str, ...]


PeerInventoryRows: TypeAlias = tuple[
    tuple[str, tuple[ConnectorFootprintPeerInventoryObservation, ...]], ...
]


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinInventoryEvidence:
    """Validated source evidence for an exact-part peer inventory difference."""

    observed: NetlistContract
    group: ConnectorFootprintPeerGroup
    extra_pin_number: str
    extra_pin_reference: str
    peer_pin_inventories: tuple[str, ...]
    extra_pin_observation: ConnectorFootprintPeerInventoryObservation
    common_anchor_pin_number: str
    common_anchor_observations: tuple[ConnectorFootprintPeerInventoryObservation, ...]
    declared_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "peer_pin_inventories", tuple(self.peer_pin_inventories))
        object.__setattr__(
            self, "common_anchor_observations", tuple(self.common_anchor_observations)
        )
        object.__setattr__(self, "declared_references", tuple(self.declared_references))
        _validate_inventory_evidence(self)

    @property
    def projection(self) -> CandidateEvidenceProjection:
        """Project stable fields directly from the validated native source."""
        assert self.group.part_id is not None
        extra_assignment = self.extra_pin_observation.nets
        return CandidateEvidenceProjection(
            rule_id=RULE_ID,
            evidence={
                "value": (self.group.value,),
                "footprint": (self.group.footprint,),
                "part_id": (self.group.part_id,),
                "peer_identity_basis": ("part_id",),
                "peer_pin_inventories": self.peer_pin_inventories,
                "extra_pin": (self.extra_pin_observation.pin,),
                "extra_pin_function": (self.extra_pin_observation.function,),
                "extra_pin_electrical_type": (self.extra_pin_observation.electrical_type,),
                "extra_pin_assignments": tuple(
                    f"{self.extra_pin_observation.pin}={net}" for net in extra_assignment
                )
                or (f"{self.extra_pin_observation.pin}=<no-net-assignment>",),
                "common_anchor_pin_number": (self.common_anchor_pin_number,),
                "common_anchor_assignments": tuple(
                    f"{item.pin}={item.nets[0]}" for item in self.common_anchor_observations
                ),
            },
        )


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinInventoryCandidate(Candidate):
    """Review candidate whose public fields remain bound to native source."""

    source_evidence: ConnectorFootprintPeerPinInventoryEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorFootprintPeerPinInventoryEvidence,
    ) -> ConnectorFootprintPeerPinInventoryCandidate:
        projection = source_evidence.projection
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.group.value} [{source_evidence.group.footprint}] "
                f"pin {source_evidence.extra_pin_number}"
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
                f"pin {self.source_evidence.extra_pin_number}"
            )
            or self.message != _candidate_message(self.source_evidence)
            or self.evidence != projection.evidence
        ):
            raise ValueError(
                "Connector peer inventory finding must match its native source evidence"
            )


def connector_footprint_peer_pin_inventory_disagreements(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Review one named native pin omitted by another exact-part peer symbol.

    Require fitted aliases with one matching nonempty PART_ID, value, and
    footprint. Exactly one peer may have one additional pin; every common pin
    must have matching native function and electrical-type metadata, the extra
    pin must have one exact net assignment, and one common net assignment
    anchors the comparison. This is a symbol-review cue, not proof that either
    library symbol is incorrect.
    """
    candidates: list[Candidate] = []
    for group in connector_footprint_peer_candidate_groups(
        observed,
        declared_references,
        include_part_id_peers=True,
    ):
        if group.part_id is None:
            continue
        mismatch = _eligible_inventory_mismatch(observed, group)
        if mismatch is None:
            continue
        extra_pin_number, extra_pin_reference, inventories, extra, anchor_number, anchors = mismatch
        evidence = ConnectorFootprintPeerPinInventoryEvidence(
            observed=observed,
            group=group,
            extra_pin_number=extra_pin_number,
            extra_pin_reference=extra_pin_reference,
            peer_pin_inventories=inventories,
            extra_pin_observation=extra,
            common_anchor_pin_number=anchor_number,
            common_anchor_observations=anchors,
            declared_references=declared_references,
        )
        candidates.append(
            ConnectorFootprintPeerPinInventoryCandidate.from_source_evidence(evidence)
        )

    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(item.evidence["peer_pin_inventories"]),
            ),
        )
    )


def _eligible_inventory_mismatch(
    observed: NetlistContract,
    group: ConnectorFootprintPeerGroup,
) -> (
    tuple[
        str,
        str,
        tuple[str, ...],
        ConnectorFootprintPeerInventoryObservation,
        str,
        tuple[ConnectorFootprintPeerInventoryObservation, ...],
    ]
    | None
):
    """Return one anchored named pin absent from the other complete inventories."""
    if group.part_id is None or not group.part_id.strip():
        return None
    inventories = complete_connector_footprint_peer_pin_inventories(observed, group.references)
    if inventories is None:
        return None
    pin_sets = {
        reference: frozenset(numbers)
        for reference, numbers in inventories.displayed_numbers_by_reference.items()
    }
    outliers: list[tuple[str, frozenset[str], frozenset[str]]] = []
    for reference, numbers in pin_sets.items():
        other_sets = {pins for peer, pins in pin_sets.items() if peer != reference}
        if len(other_sets) != 1:
            continue
        base = next(iter(other_sets))
        if numbers > base and len(numbers - base) == 1:
            outliers.append((reference, numbers, base))
    if len(outliers) != 1:
        return None
    outlier, _, base = outliers[0]
    extra_numbers = pin_sets[outlier] - base
    if len(extra_numbers) != 1:
        return None
    extra_key = next(iter(extra_numbers))
    extra_display = inventories.displayed_numbers_by_reference[outlier][extra_key]
    extra_reference = next(
        reference for reference in group.references if reference.casefold() == outlier
    )
    pin_functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
    }
    pin_nets = netlist_pin_net_index(observed)
    extra_pin = f"{extra_reference}.{extra_display}"
    extra_function = pin_functions.get(extra_pin.casefold())
    extra_type = electrical_types.get(extra_pin.casefold())
    if (
        native_pin_metadata_is_missing(extra_function)
        or native_pin_metadata_is_missing(extra_type)
        or pin_function_is_generic(str(extra_function))
    ):
        return None
    extra = ConnectorFootprintPeerInventoryObservation(
        reference=outlier,
        pin=extra_pin,
        function=str(extra_function),
        electrical_type=str(extra_type),
        nets=tuple(
            sorted(
                pin_nets.get(extra_pin.casefold(), ()),
                key=lambda net: (net.casefold(), net),
            )
        ),
    )
    if len(extra.nets) != 1 or not extra.nets[0].strip():
        return None
    common_rows = _common_pin_rows(
        group.references,
        base,
        inventories.displayed_numbers_by_reference,
        pin_functions,
        electrical_types,
        pin_nets,
    )
    anchors = tuple((number, rows) for number, rows in common_rows if _one_common_assignment(rows))
    if not anchors:
        return None
    anchor_number, anchor_rows = anchors[0]
    inventory_evidence = tuple(
        f"{reference}="
        + ",".join(
            sorted(
                inventories.displayed_numbers_by_reference[reference.casefold()].values(),
                key=lambda item: (item.casefold(), item),
            )
        )
        for reference in group.references
    )
    return (
        extra_display,
        extra_reference,
        inventory_evidence,
        extra,
        anchor_number,
        anchor_rows,
    )


def _common_pin_rows(
    references: tuple[str, ...],
    pin_numbers: frozenset[str],
    displayed: Mapping[str, Mapping[str, str]],
    pin_functions: dict[str, str],
    electrical_types: dict[str, str],
    pin_nets: Mapping[str, AbstractSet[str]],
) -> PeerInventoryRows:
    """Collect complete, matching metadata for common pins across all peers."""
    rows: list[tuple[str, tuple[ConnectorFootprintPeerInventoryObservation, ...]]] = []
    for number in sorted(pin_numbers, key=lambda item: (item.casefold(), item)):
        observations: list[ConnectorFootprintPeerInventoryObservation] = []
        for reference in references:
            display_number = displayed[reference.casefold()][number]
            pin = f"{reference}.{display_number}"
            function = pin_functions.get(pin.casefold())
            electrical_type = electrical_types.get(pin.casefold())
            if native_pin_metadata_is_missing(function) or native_pin_metadata_is_missing(
                electrical_type
            ):
                return ()
            observations.append(
                ConnectorFootprintPeerInventoryObservation(
                    reference=reference,
                    pin=pin,
                    function=str(function),
                    electrical_type=str(electrical_type),
                    nets=tuple(
                        sorted(
                            pin_nets.get(pin.casefold(), ()),
                            key=lambda net: (net.casefold(), net),
                        )
                    ),
                )
            )
        if (
            len({item.function.strip().casefold() for item in observations}) != 1
            or len({item.electrical_type.strip().casefold() for item in observations}) != 1
        ):
            return ()
        rows.append((number, tuple(observations)))
    return tuple(rows)


def _one_common_assignment(
    observations: tuple[ConnectorFootprintPeerInventoryObservation, ...],
) -> bool:
    """Require one exact nonempty net on every peer for an identity anchor."""
    return (
        bool(observations)
        and all(len(item.nets) == 1 and item.nets[0].strip() for item in observations)
        and len({item.nets[0] for item in observations}) == 1
    )


def _candidate_message(evidence: ConnectorFootprintPeerPinInventoryEvidence) -> str:
    """Describe the discrepancy without deciding which peer symbol is wrong."""
    return (
        "Fitted connector peers with the same exact PART_ID, value, and footprint have "
        "one named native pin in a peer symbol inventory that the other peers omit. "
        "Review the approved part pinout and symbol definitions; similarity metadata "
        "does not establish whether the pin is missing or intentionally omitted."
    )


def _validate_inventory_evidence(evidence: ConnectorFootprintPeerPinInventoryEvidence) -> None:
    """Reject findings whose peer grouping, pin set, metadata, or anchor changed."""
    current_groups = connector_footprint_peer_candidate_groups(
        evidence.observed,
        evidence.declared_references,
        include_part_id_peers=True,
    )
    if evidence.group.part_id is None or evidence.group not in current_groups:
        raise ValueError("Connector peer inventory evidence requires a current exact PART_ID group")
    mismatch = _eligible_inventory_mismatch(evidence.observed, evidence.group)
    if mismatch is None:
        raise ValueError("Connector peer inventory evidence requires one anchored pin difference")
    extra_number, extra_reference, inventories, extra, anchor_number, anchors = mismatch
    if (
        evidence.extra_pin_number != extra_number
        or evidence.extra_pin_reference.casefold() != extra_reference.casefold()
        or evidence.peer_pin_inventories != inventories
        or evidence.extra_pin_observation != extra
        or evidence.common_anchor_pin_number != anchor_number
        or evidence.common_anchor_observations != anchors
    ):
        raise ValueError("Connector peer inventory evidence must match current native pin data")
