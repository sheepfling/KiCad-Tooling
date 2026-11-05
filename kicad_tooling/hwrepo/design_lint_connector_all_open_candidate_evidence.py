"""Typed native evidence for generic connector peer pins open everywhere."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .connector_identity import native_pin_metadata_is_missing, pin_function_is_generic
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

ALL_OPEN_GENERIC_CONNECTOR_RULE_ID: DesignLintRuleId = "connector.generic_peer_pin_all_open"
ConnectorPeerIdentityBasis = Literal["exact_symbol", "part_id"]


@dataclass(frozen=True, slots=True)
class ConnectorPeerOpenPin:
    """One current peer pin and its exact native net assignment."""

    pin: str
    assignments: tuple[str, ...]
    pin_function: str | None
    pin_electrical_type: str


@dataclass(frozen=True, slots=True)
class ConnectorSharedAnchor:
    """One pin on every peer that shares one exact native net."""

    pins: tuple[str, ...]
    net: str

    def __post_init__(self) -> None:
        if not self.net or len(self.pins) < 2:
            raise ValueError("A shared connector anchor requires peer pins and one native net")
        if len({pin.casefold() for pin in self.pins}) != len(self.pins):
            raise ValueError("A shared connector anchor cannot repeat a native pin")
        if self.pins != tuple(sorted(self.pins, key=lambda item: (item.casefold(), item))):
            raise ValueError("Shared connector anchor pins must be ordered by native reference")

    @property
    def display(self) -> str:
        return " / ".join(self.pins) + f" -> {self.net}"


@dataclass(frozen=True, slots=True)
class ConnectorAllOpenPeerPinEvidence:
    """Current source for an all-open peer contact review finding."""

    observed: NetlistContract
    identity_basis: ConnectorPeerIdentityBasis
    identity: str
    pin_number: str
    pin_electrical_type: str
    open_pins: tuple[ConnectorPeerOpenPin, ...]
    shared_anchors: tuple[ConnectorSharedAnchor, ...]
    peer_symbols: tuple[str, ...] = ()
    peer_assignment_group: str | None = None
    peer_assignment_basis: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.identity or not self.pin_number or not self.pin_electrical_type:
            raise ValueError("Connector peer evidence requires identity and pin metadata")
        if self.identity_basis not in {"exact_symbol", "part_id"}:
            raise ValueError("Connector peer identity basis must be exact_symbol or part_id")
        if self.pin_electrical_type != self.pin_electrical_type.strip().casefold():
            raise ValueError("Connector pin electrical type must be normalized")
        if len(self.open_pins) < 2:
            raise ValueError("All-open connector evidence requires at least two peer pins")
        pins = tuple(item.pin for item in self.open_pins)
        if pins != tuple(sorted(pins, key=lambda item: (item.casefold(), item))):
            raise ValueError("Open connector peer pins must be ordered deterministically")
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("Open connector peer evidence cannot repeat a native pin")
        if any(item.assignments for item in self.open_pins):
            raise ValueError("Every retained connector peer pin must remain open")

        references = tuple(pin.rpartition(".")[0] for pin in pins)
        if any(not reference for reference in references):
            raise ValueError("Connector peer pins must retain reference and pin number")
        if any(pin.rpartition(".")[2].casefold() != self.pin_number.casefold() for pin in pins):
            raise ValueError("Connector peer pins must retain one common native pin number")
        reference_keys = {reference.casefold() for reference in references}
        component_keys = {reference.casefold() for reference in self.observed.components}
        dnp_keys = {reference.casefold() for reference in self.observed.dnp_components}
        if not reference_keys <= component_keys or reference_keys & dnp_keys:
            raise ValueError("Connector peer evidence requires current fitted components")

        symbols = {
            reference.casefold(): symbol
            for reference, symbol in self.observed.component_symbols.items()
        }
        functions = {pin.casefold(): value for pin, value in self.observed.pin_functions.items()}
        electrical_types = {
            pin.casefold(): value.strip().casefold()
            for pin, value in self.observed.pin_electrical_types.items()
        }
        inventories = {
            reference.casefold(): tuple(numbers)
            for reference, numbers in self.observed.component_pin_numbers.items()
        }
        current_pin_nets = netlist_pin_net_index(self.observed)
        for peer_pin, reference in zip(self.open_pins, references, strict=True):
            pin = peer_pin.pin
            if symbols.get(reference.casefold()) is None:
                raise ValueError("Connector peer evidence requires current native symbols")
            if not any(
                number.casefold() == self.pin_number.casefold()
                for number in inventories.get(reference.casefold(), ())
            ):
                raise ValueError("Connector peer pin must exist in the current native inventory")
            if current_pin_nets.get(pin.casefold(), set()):
                raise ValueError("Connector peer pin must remain unassigned in the native netlist")
            if functions.get(pin.casefold()) != peer_pin.pin_function:
                raise ValueError("Connector peer pin function must match the current netlist")
            if not pin_function_is_generic(peer_pin.pin_function):
                raise ValueError("Connector peer pin function must remain absent or generic")
            if (
                electrical_types.get(pin.casefold()) != peer_pin.pin_electrical_type
                or peer_pin.pin_electrical_type != self.pin_electrical_type
            ):
                raise ValueError("Connector peer pin type must match the current netlist")

        peer_symbols = tuple(
            sorted(set(self.peer_symbols), key=lambda item: (item.casefold(), item))
        )
        if self.peer_symbols != peer_symbols:
            raise ValueError("Connector peer symbols must be unique and deterministically ordered")
        if self.identity_basis == "exact_symbol":
            if self.peer_symbols or any(
                symbols[reference.casefold()].casefold() != self.identity.casefold()
                for reference in references
            ):
                raise ValueError("Exact-symbol identity must match every current peer symbol")
        else:
            components = {
                reference.casefold(): component
                for reference, component in self.observed.components.items()
            }
            peers = tuple(components[reference.casefold()] for reference in references)
            if not self.peer_symbols or any(
                component.part_id is None
                or component.part_id.casefold() != self.identity.casefold()
                for component in peers
            ):
                raise ValueError("PART_ID identity must match every current peer component")
            if len({(item.value, item.footprint) for item in peers}) != 1:
                raise ValueError("PART_ID connector peers must retain matching value and footprint")
            matching_identity_symbols = {
                symbols[reference.casefold()]
                for reference, component in self.observed.components.items()
                if component.part_id is not None
                and component.part_id.casefold() == self.identity.casefold()
                and (component.value, component.footprint) == (peers[0].value, peers[0].footprint)
                and reference.casefold() in symbols
            }
            current_scope_symbols = {symbols[reference.casefold()] for reference in references}
            if (
                not current_scope_symbols <= set(self.peer_symbols)
                or not set(self.peer_symbols) <= matching_identity_symbols
            ):
                raise ValueError("PART_ID peer symbols must match current native components")
            source_functions = tuple(pin.pin_function for pin in self.open_pins)
            if (
                any(native_pin_metadata_is_missing(function) for function in source_functions)
                or len(
                    {
                        " ".join(function.strip().casefold().split())
                        for function in source_functions
                        if function is not None
                    }
                )
                != 1
            ):
                raise ValueError("PART_ID peer pin functions must match across the source group")

        if not self.shared_anchors:
            raise ValueError("All-open connector findings require at least one shared anchor")
        anchor_displays = tuple(anchor.display for anchor in self.shared_anchors)
        expected_anchor_order = (
            sorted(anchor_displays)
            if self.identity_basis == "part_id"
            else sorted(anchor_displays, key=lambda item: (item.casefold(), item))
        )
        if anchor_displays != tuple(expected_anchor_order):
            raise ValueError("Shared connector anchors must be ordered deterministically")
        for anchor in self.shared_anchors:
            anchor_references = tuple(pin.rpartition(".")[0].casefold() for pin in anchor.pins)
            if set(anchor_references) != reference_keys or len(anchor_references) != len(
                references
            ):
                raise ValueError("A shared connector anchor must contain one pin per peer")
            if any(
                not any(
                    number.casefold() == pin.rpartition(".")[2].casefold()
                    for number in inventories.get(pin.rpartition(".")[0].casefold(), ())
                )
                or current_pin_nets.get(pin.casefold(), set()) != {anchor.net}
                for pin in anchor.pins
            ):
                raise ValueError("Shared connector anchor must match each current native net")

        if self.peer_assignment_group is None:
            if self.peer_assignment_basis:
                raise ValueError("Unscoped connector peers cannot retain group review evidence")
        elif not self.peer_assignment_basis:
            raise ValueError("Scoped connector peers require their assignment review basis")


def project_connector_all_open_peer_pin_evidence(
    source: ConnectorAllOpenPeerPinEvidence,
) -> CandidateEvidenceProjection:
    """Project typed connector peer evidence into the stable report fields."""
    evidence: dict[str, tuple[str, ...]] = {item.pin: item.assignments for item in source.open_pins}
    evidence.update(
        {
            "symbol": (
                source.identity
                if source.identity_basis == "exact_symbol"
                else "multiple connector symbols",
            ),
            "pin_number": (source.pin_number,),
            "shared_anchor_contacts": tuple(anchor.display for anchor in source.shared_anchors),
        }
    )
    if source.pin_electrical_type != "passive":
        evidence["pin_electrical_type"] = (source.pin_electrical_type,)
    if source.identity_basis == "part_id":
        evidence.update(
            {
                "peer_identity_basis": ("part_id",),
                "peer_identity": (source.identity,),
                "peer_symbols": source.peer_symbols,
            }
        )
    if source.peer_assignment_group is not None:
        evidence["peer_assignment_group"] = (source.peer_assignment_group,)
        evidence["peer_assignment_basis"] = source.peer_assignment_basis
    return CandidateEvidenceProjection(
        rule_id=ALL_OPEN_GENERIC_CONNECTOR_RULE_ID,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class ConnectorAllOpenPeerPinCandidate(Candidate):
    """Candidate whose report fields are projected from current peer evidence."""

    source_evidence: ConnectorAllOpenPeerPinEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorAllOpenPeerPinEvidence,
        *,
        subject: str,
        message: str,
    ) -> ConnectorAllOpenPeerPinCandidate:
        projection = project_connector_all_open_peer_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_all_open_peer_pin_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Connector all-open candidate must match its typed source projection")
