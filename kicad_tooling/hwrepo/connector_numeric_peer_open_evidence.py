"""Typed source evidence for numeric-only connector peer-open reviews."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from .connector_footprint_peer_groups import (
    ConnectorFootprintPeerPinInventory,
    complete_connector_footprint_peer_pin_inventory,
)
from .connector_identity import native_pin_metadata_is_missing
from .connector_peer_pin_scan import scan_connector_part_id_peer_pins
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

CONNECTOR_PEER_NUMERIC_SIGNAL_TYPES = frozenset(
    {"passive", "input", "output", "bidirectional", "tri_state", "open_collector", "open_emitter"}
)
_RULE_ID = "connector.generic_peer_pin_open_outlier"


@dataclass(frozen=True, slots=True)
class ConnectorNumericPeerAnchor:
    """One exact assigned net shared by every peer in the comparison scope."""

    pin_number: str
    pins: tuple[str, ...]
    net: str

    @property
    def display(self) -> str:
        return f"{' / '.join(self.pins)} -> {self.net}"


@dataclass(frozen=True, slots=True)
class ConnectorNumericPeerOpenEvidence:
    """Native connector assignment and metadata evidence for one open outlier."""

    observed: NetlistContract
    symbol: str
    pin_number: str
    electrical_type: str
    assignments: Mapping[str, tuple[str, ...]]
    pin_metadata: Mapping[str, tuple[str, str]]
    shared_anchors: tuple[ConnectorNumericPeerAnchor, ...]
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()
    peer_identity_basis: Literal["exact_symbol", "part_id"] = "exact_symbol"
    peer_identity: str = ""
    peer_symbols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        assignments = MappingProxyType(
            {
                pin: tuple(nets)
                for pin, nets in sorted(
                    self.assignments.items(), key=lambda item: (item[0].casefold(), item[0])
                )
            }
        )
        metadata = MappingProxyType(
            {
                pin: tuple(values)
                for pin, values in sorted(
                    self.pin_metadata.items(), key=lambda item: (item[0].casefold(), item[0])
                )
            }
        )
        object.__setattr__(self, "assignments", assignments)
        object.__setattr__(self, "pin_metadata", metadata)
        self._validate_source()

    def _validate_source(self) -> None:
        references = tuple(
            sorted(
                {pin.rpartition(".")[0] for pin in self.assignments},
                key=lambda item: (item.casefold(), item),
            )
        )
        if len(references) < 2 or any(not pin.rpartition(".")[2] for pin in self.assignments):
            raise ValueError(
                "Numeric peer-open evidence needs at least two identified connector pins"
            )
        if any(
            pin.rpartition(".")[2].casefold() != self.pin_number.casefold()
            for pin in self.assignments
        ):
            raise ValueError("Numeric peer-open evidence must retain one native pin number")
        if not any(not nets for nets in self.assignments.values()) or not any(
            nets for nets in self.assignments.values()
        ):
            raise ValueError("Numeric peer-open evidence needs assigned and open peer contacts")
        assigned = {nets for nets in self.assignments.values() if nets}
        if len(assigned) != 1 or any(len(nets) > 1 for nets in self.assignments.values()):
            raise ValueError("Numeric peer-open evidence needs one unambiguous assigned peer net")

        symbols = {
            reference.casefold(): symbol
            for reference, symbol in self.observed.component_symbols.items()
        }
        components = {
            reference.casefold(): component
            for reference, component in self.observed.components.items()
        }
        observed_symbols = tuple(
            sorted(
                {symbols.get(reference.casefold(), "") for reference in references},
                key=lambda item: (item.casefold(), item),
            )
        )
        if self.peer_identity_basis == "exact_symbol":
            if any(
                symbols.get(reference.casefold(), "").casefold() != self.symbol.casefold()
                for reference in references
            ):
                raise ValueError("Numeric peer-open evidence must retain one exact native symbol")
        elif self.peer_identity_basis == "part_id":
            part_id = self.peer_identity.strip()
            if (
                not part_id
                or len(observed_symbols) < 2
                or tuple(item.casefold() for item in observed_symbols)
                != tuple(item.casefold() for item in self.peer_symbols)
                or any(
                    component is None
                    or (component.part_id or "").strip().casefold() != part_id.casefold()
                    for component in (
                        components.get(reference.casefold()) for reference in references
                    )
                )
                or self.symbol != "multiple connector symbols"
            ):
                raise ValueError("Numeric peer-open evidence must retain one exact native PART_ID")
            scan = scan_connector_part_id_peer_pins(self.observed, references)
            if not any(
                group.part_id.casefold() == part_id.casefold()
                and group.pin_number.casefold() == self.pin_number.casefold()
                and {pin.rpartition(".")[0].casefold() for pin in group.assignments}
                >= {reference.casefold() for reference in references}
                for group in scan.pin_groups
            ):
                raise ValueError("Numeric PART_ID peer evidence must match eligible native aliases")
        else:
            raise ValueError("Numeric peer-open evidence has an unsupported peer identity basis")
        if any(
            reference.casefold() in {item.casefold() for item in self.observed.dnp_components}
            for reference in references
        ):
            raise ValueError("Numeric peer-open evidence cannot include DNP connector instances")

        inventory = complete_connector_footprint_peer_pin_inventory(self.observed, references)
        if inventory is None or self.pin_number.casefold() not in {
            number.casefold() for number in inventory.pin_numbers
        }:
            raise ValueError("Numeric peer-open evidence needs a complete matching pin inventory")
        expected_metadata = complete_connector_numeric_peer_pin_metadata(
            self.observed, inventory, references
        )
        if expected_metadata is None or dict(expected_metadata) != dict(self.pin_metadata):
            raise ValueError("Numeric peer-open evidence must match complete native pin metadata")

        function_by_pin = {pin.casefold(): values[0] for pin, values in self.pin_metadata.items()}
        type_by_pin = {
            pin.casefold(): values[1].strip().casefold()
            for pin, values in self.pin_metadata.items()
        }
        target_pins = tuple(self.assignments)
        target_functions = {function_by_pin.get(pin.casefold(), "").strip() for pin in target_pins}
        target_types = {type_by_pin.get(pin.casefold(), "") for pin in target_pins}
        if (
            len(target_functions) != 1
            or re.fullmatch(r"[0-9]+", next(iter(target_functions), "")) is None
            or len(target_types) != 1
            or next(iter(target_types), "") != self.electrical_type.strip().casefold()
            or self.electrical_type.strip().casefold() not in CONNECTOR_PEER_NUMERIC_SIGNAL_TYPES
        ):
            raise ValueError(
                "Numeric peer-open evidence needs matching numeric-only native metadata"
            )

        pin_index = netlist_pin_net_index(self.observed)
        for pin, nets in self.assignments.items():
            current = tuple(
                sorted(
                    pin_index.get(pin.casefold(), frozenset()),
                    key=lambda net: (net.casefold(), net),
                )
            )
            if current != nets:
                raise ValueError("Numeric peer-open evidence must match current native assignments")

        if not self.shared_anchors:
            raise ValueError("Numeric peer-open evidence needs a shared assigned anchor")
        target_number = self.pin_number.casefold()
        scope_references = {reference.casefold() for reference in references}
        for anchor in self.shared_anchors:
            if anchor.pin_number.casefold() == target_number:
                raise ValueError("A target contact cannot anchor its own peer comparison")
            if {pin.rpartition(".")[0].casefold() for pin in anchor.pins} != scope_references:
                raise ValueError("Shared anchors must cover exactly the compared connector peers")
            for pin in anchor.pins:
                current = pin_index.get(pin.casefold(), frozenset())
                if current != frozenset({anchor.net}):
                    raise ValueError("Shared anchors must retain one current exact native net")
        if (self.peer_assignment_group is None) != (not self.peer_assignment_basis):
            raise ValueError("Peer assignment evidence must include both group and review basis")


def complete_connector_numeric_peer_pin_metadata(
    observed: NetlistContract,
    inventory: ConnectorFootprintPeerPinInventory,
    references: tuple[str, ...],
) -> Mapping[str, tuple[str, str]] | None:
    """Return complete exact-symbol function/type metadata keyed by native pin."""
    pin_numbers = inventory.pin_numbers
    displayed = inventory.displayed_numbers_by_reference
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
    }
    metadata: dict[str, tuple[str, str]] = {}
    signatures: dict[str, tuple[tuple[str, str], ...]] = {}
    for reference in references:
        native_numbers = displayed.get(reference.casefold())
        if native_numbers is None:
            return None
        signature: list[tuple[str, str]] = []
        for number in pin_numbers:
            pin = f"{reference}.{native_numbers[number.casefold()]}"
            function = functions.get(pin.casefold())
            electrical_type = electrical_types.get(pin.casefold())
            if native_pin_metadata_is_missing(function) or native_pin_metadata_is_missing(
                electrical_type
            ):
                return None
            assert function is not None and electrical_type is not None
            metadata[pin] = (function, electrical_type)
            signature.append((function.strip().casefold(), electrical_type.strip().casefold()))
        signatures[reference.casefold()] = tuple(signature)
    if len(set(signatures.values())) != 1:
        return None
    return MappingProxyType(metadata)


def project_connector_numeric_peer_open_evidence(
    source: ConnectorNumericPeerOpenEvidence,
) -> CandidateEvidenceProjection:
    """Project numeric peer-open evidence into stable report fields."""
    evidence = dict(source.assignments)
    open_pins = tuple(pin for pin, nets in source.assignments.items() if not nets)
    assigned_net = next(nets[0] for nets in source.assignments.values() if nets)
    metadata_by_pin = {pin.casefold(): values for pin, values in source.pin_metadata.items()}
    evidence.update(
        {
            "symbol": (source.symbol,),
            "peer_identity_basis": (source.peer_identity_basis,),
            "pin_number": (source.pin_number,),
            "open_outlier_pins": open_pins,
            "assigned_peer_pins": tuple(pin for pin, nets in source.assignments.items() if nets),
            "assigned_net": (assigned_net,),
            "native_pin_functions": tuple(
                f"{pin}={metadata_by_pin[pin.casefold()][0]}" for pin in source.assignments
            ),
            "native_pin_electrical_types": tuple(
                f"{pin}={metadata_by_pin[pin.casefold()][1]}" for pin in source.assignments
            ),
            "shared_anchor_contacts": tuple(anchor.display for anchor in source.shared_anchors),
        }
    )
    if source.peer_identity_basis == "part_id":
        evidence["peer_identity"] = (source.peer_identity,)
        evidence["peer_symbols"] = source.peer_symbols
    if source.peer_assignment_group is not None:
        evidence["peer_assignment_group"] = (source.peer_assignment_group,)
        evidence["peer_assignment_basis"] = source.peer_assignment_basis
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorNumericPeerOpenCandidate(Candidate):
    """Candidate retaining validated native source evidence."""

    source_evidence: ConnectorNumericPeerOpenEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorNumericPeerOpenEvidence,
        *,
        subject: str,
        message: str,
    ) -> ConnectorNumericPeerOpenCandidate:
        projection = project_connector_numeric_peer_open_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_numeric_peer_open_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Numeric connector peer candidate must match its source projection")
