"""Review electrical-type disagreement on otherwise matching connector aliases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .connector_footprint_peer_groups import (
    ConnectorFootprintPeerGroup,
    complete_connector_footprint_peer_pin_inventory,
    connector_footprint_peer_candidate_groups,
)
from .connector_identity import native_pin_metadata_is_missing
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_electrical_type_disagreement"
PeerPinRecord: TypeAlias = tuple[str, str, str, str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinTypeObservation:
    """One peer's source-observed pin role, type, assignment, and symbol."""

    reference: str
    pin: str
    function: str
    electrical_type: str
    net: str
    symbol: str


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinTypeEvidence:
    """Validated source evidence for one electrical-type alias disagreement."""

    observed: NetlistContract
    group: ConnectorFootprintPeerGroup
    pin_number: str
    observations: tuple[ConnectorFootprintPeerPinTypeObservation, ...]
    common_anchor_pin_numbers: tuple[str, ...]
    declared_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "common_anchor_pin_numbers", tuple(self.common_anchor_pin_numbers))
        object.__setattr__(self, "declared_references", tuple(self.declared_references))
        _validate_type_evidence(self)

    @property
    def projection(self) -> CandidateEvidenceProjection:
        """Return stable fields derived from the validated native source."""
        return CandidateEvidenceProjection(
            rule_id=RULE_ID,
            evidence={
                "value": (self.group.value,),
                "footprint": (self.group.footprint,),
                "pin_number": (self.pin_number,),
                "pin_function": tuple(item.function for item in self.observations),
                "peer_pin_electrical_types": tuple(
                    f"{item.pin}={item.electrical_type}" for item in self.observations
                ),
                "assignments": tuple(f"{item.pin}={item.net}" for item in self.observations),
                "symbols": tuple(f"{item.reference}={item.symbol}" for item in self.observations),
                "common_anchor_pin_numbers": self.common_anchor_pin_numbers,
            },
        )


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinTypeCandidate(Candidate):
    """Review candidate whose fields are bound to the current native netlist."""

    source_evidence: ConnectorFootprintPeerPinTypeEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorFootprintPeerPinTypeEvidence,
    ) -> ConnectorFootprintPeerPinTypeCandidate:
        """Build a localized prompt from validated native evidence."""
        projection = source_evidence.projection
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.group.value} [{source_evidence.group.footprint}] "
                f"pin {source_evidence.pin_number}"
            ),
            message=(
                "Fitted connector aliases with the same value, footprint, complete pin inventory, "
                "and matching native pin functions assign this pin to the same net but declare "
                "different native electrical types. Review the approved symbol pinouts and the "
                "intended electrical role; similarity does not establish which type is correct."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = self.source_evidence.projection
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Connector peer type finding must match its native source evidence")


def connector_footprint_peer_pin_electrical_type_disagreements(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Review one-pin electrical-type differences across otherwise matching aliases.

    Peers must share the target pin's native function and exact assigned net,
    while every pin's native function agrees and only the target electrical
    type differs. At least one other pin must be a common assigned metadata
    anchor. Identity similarity remains a review clue, not a correctness claim.
    """
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
    }
    symbols = {
        reference.casefold(): value for reference, value in observed.component_symbols.items()
    }
    pin_nets = netlist_pin_net_index(observed)
    candidates: list[Candidate] = []

    for group in connector_footprint_peer_candidate_groups(observed, declared_references):
        inventory = complete_connector_footprint_peer_pin_inventory(observed, group.references)
        if inventory is None:
            continue
        display_numbers = inventory.displayed_numbers_by_reference
        peer_records: dict[str, tuple[PeerPinRecord, ...]] = {}
        incomplete_metadata = False
        for pin_number in inventory.pin_numbers:
            records: list[PeerPinRecord] = []
            for reference in group.references:
                pin = f"{reference}.{display_numbers[reference.casefold()][pin_number.casefold()]}"
                pin_key = pin.casefold()
                function = functions.get(pin_key)
                pin_type = electrical_types.get(pin_key)
                if native_pin_metadata_is_missing(function) or native_pin_metadata_is_missing(
                    pin_type
                ):
                    incomplete_metadata = True
                    break
                assert function is not None and pin_type is not None
                records.append(
                    (
                        reference,
                        pin,
                        str(function),
                        str(pin_type),
                        tuple(
                            sorted(
                                pin_nets.get(pin_key, ()),
                                key=lambda item: (item.casefold(), item),
                            )
                        ),
                    )
                )
            if incomplete_metadata:
                break
            peer_records[pin_number.casefold()] = tuple(records)
        if incomplete_metadata:
            continue
        if any(
            len({function.strip().casefold() for _, _, function, _, _ in records}) != 1
            for records in peer_records.values()
        ):
            continue

        for pin_number in inventory.pin_numbers:
            peer_pin_rows = peer_records[pin_number.casefold()]
            type_values = {pin_type.strip().casefold() for _, _, _, pin_type, _ in peer_pin_rows}
            if len(type_values) < 2:
                continue
            if any(
                len(
                    {
                        pin_type.strip().casefold()
                        for _, _, _, pin_type, _ in peer_records[other_pin.casefold()]
                    }
                )
                != 1
                for other_pin in inventory.pin_numbers
                if other_pin.casefold() != pin_number.casefold()
            ):
                continue
            assignments = {nets[0] for _, _, _, _, nets in peer_pin_rows if len(nets) == 1}
            if len(assignments) != 1 or any(len(nets) != 1 for _, _, _, _, nets in peer_pin_rows):
                continue

            anchors = tuple(
                sorted(
                    (
                        candidate_pin
                        for candidate_pin in inventory.pin_numbers
                        if candidate_pin.casefold() != pin_number.casefold()
                        and _is_common_metadata_anchor(peer_records[candidate_pin.casefold()])
                    ),
                    key=lambda item: (item.casefold(), item),
                )
            )
            if not anchors:
                continue

            evidence = ConnectorFootprintPeerPinTypeEvidence(
                observed=observed,
                group=group,
                pin_number=display_numbers[group.references[0].casefold()][pin_number.casefold()],
                observations=tuple(
                    ConnectorFootprintPeerPinTypeObservation(
                        reference=reference,
                        pin=pin,
                        function=function,
                        electrical_type=pin_type,
                        net=nets[0],
                        symbol=symbols[reference.casefold()],
                    )
                    for reference, pin, function, pin_type, nets in peer_pin_rows
                ),
                common_anchor_pin_numbers=anchors,
                declared_references=declared_references,
            )
            candidates.append(ConnectorFootprintPeerPinTypeCandidate.from_source_evidence(evidence))

    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(item.evidence["peer_pin_electrical_types"]),
            ),
        )
    )


def _is_common_metadata_anchor(
    records: tuple[PeerPinRecord, ...],
) -> bool:
    functions = {function.strip().casefold() for _, _, function, _, _ in records}
    electrical_types = {pin_type.strip().casefold() for _, _, _, pin_type, _ in records}
    assignments = {nets[0] for _, _, _, _, nets in records if len(nets) == 1}
    return (
        len(functions) == 1
        and len(electrical_types) == 1
        and len(assignments) == 1
        and all(len(nets) == 1 for _, _, _, _, nets in records)
    )


def _validate_type_evidence(evidence: ConnectorFootprintPeerPinTypeEvidence) -> None:
    """Reject candidate evidence if its peer group or native source has changed."""
    current_groups = connector_footprint_peer_candidate_groups(
        evidence.observed,
        evidence.declared_references,
    )
    if evidence.group not in current_groups:
        raise ValueError("Connector peer type evidence must match a current fitted alias group")
    inventory = complete_connector_footprint_peer_pin_inventory(
        evidence.observed,
        evidence.group.references,
    )
    if inventory is None:
        raise ValueError("Connector peer type evidence requires a complete pin inventory")
    display_numbers = inventory.displayed_numbers_by_reference
    target = evidence.pin_number.casefold()
    if target not in {number.casefold() for number in inventory.pin_numbers}:
        raise ValueError("Connector peer type evidence pin must remain in the current inventory")
    if display_numbers[evidence.group.references[0].casefold()][target] != evidence.pin_number:
        raise ValueError("Connector peer type evidence must retain native pin-number spelling")

    functions = {pin.casefold(): value for pin, value in evidence.observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in evidence.observed.pin_electrical_types.items()
    }
    symbols = {
        reference.casefold(): value
        for reference, value in evidence.observed.component_symbols.items()
    }
    pin_nets = netlist_pin_net_index(evidence.observed)
    target_types: set[str] = set()
    target_functions: set[str] = set()
    actual_anchors: list[str] = []
    for pin_number in inventory.pin_numbers:
        records: list[PeerPinRecord] = []
        for reference in evidence.group.references:
            pin = f"{reference}.{display_numbers[reference.casefold()][pin_number.casefold()]}"
            function = functions.get(pin.casefold())
            pin_type = electrical_types.get(pin.casefold())
            nets = tuple(pin_nets.get(pin.casefold(), ()))
            if native_pin_metadata_is_missing(function) or native_pin_metadata_is_missing(pin_type):
                raise ValueError("Connector peer type comparison requires complete native metadata")
            assert function is not None and pin_type is not None
            records.append((reference, pin, str(function), str(pin_type), nets))
        function_values = {function.strip().casefold() for _, _, function, _, _ in records}
        type_values = {pin_type.strip().casefold() for _, _, _, pin_type, _ in records}
        if len(function_values) != 1:
            raise ValueError("Connector peer type comparison requires matching pin functions")
        if pin_number.casefold() == target:
            target_functions = function_values
            target_types = type_values
        elif len(type_values) != 1:
            raise ValueError("Only the reviewed connector pin may differ in electrical type")
        if pin_number.casefold() != target and _is_common_metadata_anchor(tuple(records)):
            actual_anchors.append(
                display_numbers[evidence.group.references[0].casefold()][pin_number.casefold()]
            )

    expected: list[ConnectorFootprintPeerPinTypeObservation] = []
    for reference in evidence.group.references:
        pin = f"{reference}.{display_numbers[reference.casefold()][target]}"
        nets = tuple(
            sorted(
                pin_nets.get(pin.casefold(), ()),
                key=lambda item: (item.casefold(), item),
            )
        )
        function = functions.get(pin.casefold())
        pin_type = electrical_types.get(pin.casefold())
        if (
            native_pin_metadata_is_missing(function)
            or native_pin_metadata_is_missing(pin_type)
            or len(nets) != 1
        ):
            raise ValueError("Connector peer type evidence requires complete assigned native pins")
        assert function is not None and pin_type is not None
        expected.append(
            ConnectorFootprintPeerPinTypeObservation(
                reference=reference,
                pin=pin,
                function=str(function),
                electrical_type=str(pin_type),
                net=nets[0],
                symbol=symbols[reference.casefold()],
            )
        )
    current_types = {item.electrical_type.strip().casefold() for item in expected}
    current_functions = {item.function.strip().casefold() for item in expected}
    if (
        tuple(expected) != evidence.observations
        or current_types != target_types
        or current_functions != target_functions
        or len(target_types) < 2
        or len(target_functions) != 1
        or len({item.net for item in expected}) != 1
    ):
        raise ValueError(
            "Connector peer type evidence must match current native assignments and roles"
        )

    expected_anchors = tuple(sorted(actual_anchors, key=lambda item: (item.casefold(), item)))
    if not expected_anchors or evidence.common_anchor_pin_numbers != expected_anchors:
        raise ValueError("Connector peer type evidence requires current common metadata anchors")
