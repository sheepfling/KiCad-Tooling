"""Typed source projections for CAN and RS-485 line pins on named rails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .bus_signal_roles import can_function_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .named_rail_pin_evidence import (
    NamedRailPinSource,
    named_rail_pin_evidence_matches_source,
)
from .rs485_data_functions import explicit_rs485_transceiver_identity
from .rs485_line_functions import rs485_bus_line_role

CanLineRole = Literal["CANH", "CANL"]
Rs485LineRole = Literal["a", "b"]

CAN_LINE_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.can_line_on_named_rail"
RS485_LINE_NAMED_RAIL_RULE_ID: DesignLintRuleId = "bus.rs485_line_on_named_rail"


@dataclass(frozen=True, slots=True)
class CanLineNamedRailPeer:
    """One uniquely recognized complementary CAN line pin."""

    role: CanLineRole
    pin: str
    function: str


@dataclass(frozen=True, slots=True)
class Rs485LineNamedRailPeer:
    """One uniquely recognized complementary RS-485 line pin and identity."""

    role: Rs485LineRole
    pin: str
    function: str
    identity_basis: str


def can_line_named_rail_peer(
    pin_source: NamedRailPinSource,
) -> CanLineNamedRailPeer | None:
    """Resolve the exact CAN line pair from one current named-rail pin source."""
    if not named_rail_pin_evidence_matches_source(pin_source.observed, pin_source.evidence):
        return None
    evidence = pin_source.evidence
    role = can_function_role(evidence.function)
    if role == "CANH":
        complementary_role: CanLineRole = "CANL"
    elif role == "CANL":
        complementary_role = "CANH"
    else:
        return None

    pair: dict[CanLineRole, list[tuple[str, str]]] = {"CANH": [], "CANL": []}
    for pin, function in pin_source.observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        pin_role = can_function_role(function)
        if (
            separator
            and number
            and reference.casefold() == evidence.reference.casefold()
            and pin_role in pair
        ):
            pair[pin_role].append((pin, function))

    if len(pair["CANH"]) != 1 or len(pair["CANL"]) != 1:
        return None
    line_high, line_low = pair["CANH"][0], pair["CANL"][0]
    if (line_high if role == "CANH" else line_low) != (evidence.pin, evidence.function):
        return None
    inventory = set(evidence.inventory)
    if any(
        pin.rpartition(".")[2].casefold() not in inventory
        for pin, _function in (line_high, line_low)
    ):
        return None

    peer_pin, peer_function = pair[complementary_role][0]
    return CanLineNamedRailPeer(role=role, pin=peer_pin, function=peer_function)


def rs485_line_named_rail_peer(
    pin_source: NamedRailPinSource,
) -> Rs485LineNamedRailPeer | None:
    """Resolve the exact identified RS-485 A/B pair from a current source pin."""
    if not named_rail_pin_evidence_matches_source(pin_source.observed, pin_source.evidence):
        return None
    evidence = pin_source.evidence
    identity = explicit_rs485_transceiver_identity(pin_source.observed, evidence.reference)
    role = rs485_bus_line_role(evidence.function)
    if identity is None or role is None:
        return None

    pair: dict[Rs485LineRole, list[tuple[str, str]]] = {"a": [], "b": []}
    for pin, function in pin_source.observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        pin_role = rs485_bus_line_role(function)
        if (
            separator
            and number
            and reference.casefold() == evidence.reference.casefold()
            and pin_role in pair
        ):
            pair[pin_role].append((pin, function))

    if len(pair["a"]) != 1 or len(pair["b"]) != 1:
        return None
    line_a, line_b = pair["a"][0], pair["b"][0]
    if (line_a if role == "a" else line_b) != (evidence.pin, evidence.function):
        return None
    inventory = set(evidence.inventory)
    if any(
        pin.rpartition(".")[2].casefold() not in inventory for pin, _function in (line_a, line_b)
    ):
        return None

    peer_pin, peer_function = line_b if role == "a" else line_a
    return Rs485LineNamedRailPeer(
        role=role,
        pin=peer_pin,
        function=peer_function,
        identity_basis=identity,
    )


@dataclass(frozen=True, slots=True)
class CanLineNamedRailEvidence:
    """A CANH/CANL source pair with one line assigned to a named rail."""

    pin: NamedRailPinSource
    peer: CanLineNamedRailPeer

    def __post_init__(self) -> None:
        if can_line_named_rail_peer(self.pin) != self.peer:
            raise ValueError("CAN named-rail line evidence must match its current native pair")


@dataclass(frozen=True, slots=True)
class Rs485LineNamedRailEvidence:
    """An identified RS-485 A/B source pair with one line on a named rail."""

    pin: NamedRailPinSource
    peer: Rs485LineNamedRailPeer

    def __post_init__(self) -> None:
        if rs485_line_named_rail_peer(self.pin) != self.peer:
            raise ValueError("RS-485 named-rail line evidence must match its current native pair")


NamedRailLineEvidence: TypeAlias = CanLineNamedRailEvidence | Rs485LineNamedRailEvidence


def project_named_rail_line_evidence(
    source: NamedRailLineEvidence,
) -> CandidateEvidenceProjection:
    """Project pair-level source records into the existing rule evidence fields."""
    source.__post_init__()
    pin = source.pin.evidence
    evidence: dict[str, tuple[str, ...]] = {
        "pin": (pin.pin,),
        "pin_function": (pin.function,),
        "assigned_net": (pin.net_name,),
        "net_label_role_clue": (pin.rail_role,),
        "component_pin_inventory": pin.inventory,
    }
    if isinstance(source, CanLineNamedRailEvidence):
        rule_id = CAN_LINE_NAMED_RAIL_RULE_ID
        evidence.update(
            {
                "can_line_role": (source.peer.role,),
                "complementary_line_pin": (source.peer.pin,),
                "complementary_line_function": (source.peer.function,),
            }
        )
    else:
        rule_id = RS485_LINE_NAMED_RAIL_RULE_ID
        evidence.update(
            {
                "rs485_line_role": (source.peer.role,),
                "complementary_line_pin": (source.peer.pin,),
                "complementary_line_function": (source.peer.function,),
                "identity_basis": (source.peer.identity_basis,),
            }
        )
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class NamedRailLineCandidate(Candidate):
    """Candidate that retains and revalidates its complete native line pair."""

    source_evidence: NamedRailLineEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: NamedRailLineEvidence,
        *,
        subject: str,
        message: str,
    ) -> NamedRailLineCandidate:
        projection = project_named_rail_line_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_named_rail_line_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Named-rail line fields must match their typed source projection")
