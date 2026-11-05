"""Typed source evidence for CAN controller TX/RX same-net findings."""

from __future__ import annotations

from dataclasses import dataclass

from .can_signal_functions import can_channel_label, can_signal_role_and_channel
from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

CAN_TX_RX_SAME_NET_RULE_ID: DesignLintRuleId = "bus.can_tx_rx_same_net"


def _current_reference(observed: NetlistContract, reference: str) -> str:
    references = tuple(
        item for item in observed.components if item.casefold() == reference.casefold()
    )
    if len(references) != 1:
        raise ValueError("CAN TX/RX evidence requires one current component")
    current = references[0]
    if not is_integrated_circuit_reference(current):
        raise ValueError("CAN TX/RX evidence requires an integrated circuit")
    if current.casefold() in {item.casefold() for item in observed.dnp_components}:
        raise ValueError("CAN TX/RX evidence requires a fitted component")
    return current


def _assignments(observed: NetlistContract, pin: str) -> frozenset[str]:
    return frozenset(
        net
        for net, pins in observed.nets.items()
        if any(current_pin.casefold() == pin.casefold() for current_pin in pins)
    )


def _electrical_type(observed: NetlistContract, pin: str) -> str:
    return {
        current_pin.casefold(): value.strip().casefold()
        for current_pin, value in observed.pin_electrical_types.items()
    }.get(pin.casefold(), "unknown")


@dataclass(frozen=True, slots=True)
class CanTxRxEndpoint:
    """One native CAN controller transmit or receive endpoint."""

    pin: str
    function: str
    electrical_type: str


@dataclass(frozen=True, slots=True)
class CanTxRxSameNetEvidence:
    """A unique fitted CAN TX/RX role pair assigned to one exact net."""

    observed: NetlistContract
    reference: str
    channel: str
    tx: CanTxRxEndpoint
    rx: CanTxRxEndpoint
    net: str

    def __post_init__(self) -> None:
        reference = _current_reference(self.observed, self.reference)
        if reference != self.reference:
            raise ValueError("CAN TX/RX reference must preserve native spelling")

        inventory_matches = tuple(
            numbers
            for component, numbers in self.observed.component_pin_numbers.items()
            if component.casefold() == reference.casefold()
        )
        if len(inventory_matches) != 1:
            raise ValueError("CAN TX/RX evidence requires a unique native pin inventory")
        inventory = {number.casefold() for number in inventory_matches[0]}

        for role, endpoint in (("tx", self.tx), ("rx", self.rx)):
            pin_reference, separator, number = endpoint.pin.rpartition(".")
            functions = tuple(
                (pin, function)
                for pin, function in self.observed.pin_functions.items()
                if pin.casefold() == endpoint.pin.casefold()
            )
            identity = can_signal_role_and_channel(endpoint.function)
            if (
                not separator
                or pin_reference.casefold() != reference.casefold()
                or number.casefold() not in inventory
                or len(functions) != 1
                or functions[0][1] != endpoint.function
                or identity != (role, self.channel)
            ):
                raise ValueError("CAN TX/RX endpoint must match its current native role and pin")
            if _assignments(self.observed, endpoint.pin) != frozenset((self.net,)):
                raise ValueError("CAN TX/RX net must match both unique native assignments")
            if _electrical_type(self.observed, endpoint.pin) != endpoint.electrical_type:
                raise ValueError("CAN TX/RX electrical type must match its current native pin")

        roles: dict[str, set[tuple[str, str, str, str]]] = {"tx": set(), "rx": set()}
        for pin, function in self.observed.pin_functions.items():
            pin_reference, separator, number = pin.rpartition(".")
            if not separator or pin_reference.casefold() != reference.casefold():
                continue
            if number.casefold() not in inventory:
                continue
            assignments = _assignments(self.observed, pin)
            if len(assignments) != 1:
                continue
            identity = can_signal_role_and_channel(function)
            if identity is None or identity[1] != self.channel:
                continue
            role, _channel = identity
            roles[role].add(
                (
                    pin,
                    function,
                    next(iter(assignments)),
                    _electrical_type(self.observed, pin),
                )
            )

        if roles["tx"] != {
            (self.tx.pin, self.tx.function, self.net, self.tx.electrical_type)
        } or roles["rx"] != {(self.rx.pin, self.rx.function, self.net, self.rx.electrical_type)}:
            raise ValueError("CAN TX/RX evidence requires one current role pin per channel")
        if self.tx.electrical_type == self.rx.electrical_type == "output":
            raise ValueError("Two native CAN outputs are excluded from this same-net finding")


def project_can_tx_rx_same_net_evidence(
    source: CanTxRxSameNetEvidence,
) -> CandidateEvidenceProjection:
    """Project current CAN endpoints into the established candidate fields."""
    return CandidateEvidenceProjection(
        rule_id=CAN_TX_RX_SAME_NET_RULE_ID,
        evidence={
            "component": (source.reference,),
            "channel": (can_channel_label(source.channel),),
            "tx_pin": (source.tx.pin,),
            "tx_function": (source.tx.function,),
            "tx_electrical_type": (source.tx.electrical_type,),
            "rx_pin": (source.rx.pin,),
            "rx_function": (source.rx.function,),
            "rx_electrical_type": (source.rx.electrical_type,),
            "net": (source.net,),
        },
    )


@dataclass(frozen=True, slots=True)
class CanTxRxSameNetCandidate(Candidate):
    """Candidate whose role pair and evidence remain bound to one netlist."""

    source_evidence: CanTxRxSameNetEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: CanTxRxSameNetEvidence,
        *,
        subject: str,
        message: str,
    ) -> CanTxRxSameNetCandidate:
        projection = project_can_tx_rx_same_net_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_can_tx_rx_same_net_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("CAN TX/RX fields must match their typed source projection")
