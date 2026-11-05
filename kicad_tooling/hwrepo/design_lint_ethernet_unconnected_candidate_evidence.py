"""Source-bound evidence projections for open Ethernet interface pairs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .bus_signal_pairs import ethernet_data_pair_function_role, ethernet_management_function_role
from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

EthernetDirection: TypeAlias = Literal["TX", "RX"]
EthernetPolarity: TypeAlias = Literal["positive", "negative"]
EthernetManagementRole: TypeAlias = Literal["clock", "data"]

ETHERNET_MANAGEMENT_UNCONNECTED_RULE_ID: DesignLintRuleId = (
    "bus.ethernet_management_unconnected_pin"
)
ETHERNET_DATA_UNCONNECTED_RULE_ID: DesignLintRuleId = "bus.ethernet_data_unconnected_pin"


def _current_reference(observed: NetlistContract, reference: str) -> str:
    references = tuple(
        item for item in observed.components if item.casefold() == reference.casefold()
    )
    if len(references) != 1:
        raise ValueError("Ethernet open-pair evidence requires one current component")
    current = references[0]
    if not is_integrated_circuit_reference(current):
        raise ValueError("Ethernet open-pair evidence requires an integrated circuit")
    if current.casefold() in {item.casefold() for item in observed.dnp_components}:
        raise ValueError("Ethernet open-pair evidence requires a fitted component")
    return current


def _pin_parts(pin: str) -> tuple[str, str]:
    reference, separator, number = pin.rpartition(".")
    if not separator or not reference or not number:
        raise ValueError("Ethernet open-pair evidence requires reference-qualified pins")
    return reference, number


def _current_inventory(
    observed: NetlistContract,
    *,
    reference: str,
    inventory: tuple[str, ...],
) -> None:
    matches = tuple(
        value
        for key, value in observed.component_pin_numbers.items()
        if key.casefold() == reference.casefold()
    )
    if len(matches) != 1 or matches[0] != inventory or not inventory:
        raise ValueError("Ethernet open-pair inventory must match the current component")

    inventory_numbers = {number.casefold() for number in inventory}
    observed_numbers: list[str] = []
    for pin in observed.pin_functions:
        pin_reference, separator, number = pin.rpartition(".")
        if separator and pin_reference.casefold() == reference.casefold():
            observed_numbers.append(number.casefold())
    if (
        len(inventory_numbers) != len(inventory)
        or len(observed_numbers) != len(set(observed_numbers))
        or inventory_numbers != set(observed_numbers)
    ):
        raise ValueError("Ethernet open-pair evidence requires a complete native pin inventory")


def _current_function(
    observed: NetlistContract,
    *,
    pin: str,
    function: str,
    reference: str,
) -> None:
    matches = tuple(
        (current_pin, current_function)
        for current_pin, current_function in observed.pin_functions.items()
        if current_pin.casefold() == pin.casefold()
    )
    if len(matches) != 1 or matches[0][1] != function:
        raise ValueError("Ethernet open-pair functions must match the current native pin map")
    pin_reference, _number = _pin_parts(matches[0][0])
    if pin_reference.casefold() != reference.casefold():
        raise ValueError("Ethernet open-pair pins must belong to the same component")


def _current_assignments(observed: NetlistContract, pin: str) -> frozenset[str]:
    return frozenset(
        net
        for net, pins in observed.nets.items()
        if any(current_pin.casefold() == pin.casefold() for current_pin in pins)
    )


def _validate_open_pair(
    observed: NetlistContract,
    *,
    reference: str,
    inventory: tuple[str, ...],
    open_pin: str,
    open_function: str,
    paired_pin: str,
    paired_function: str,
    paired_net: str,
) -> None:
    current_reference = _current_reference(observed, reference)
    if current_reference.casefold() != reference.casefold():
        raise ValueError("Ethernet open-pair reference must match the current component")
    _current_inventory(observed, reference=reference, inventory=inventory)
    _current_function(observed, pin=open_pin, function=open_function, reference=reference)
    _current_function(observed, pin=paired_pin, function=paired_function, reference=reference)

    open_reference, _open_number = _pin_parts(open_pin)
    paired_reference, _paired_number = _pin_parts(paired_pin)
    if (
        open_reference.casefold() != reference.casefold()
        or paired_reference.casefold() != reference.casefold()
        or open_pin.casefold() == paired_pin.casefold()
    ):
        raise ValueError("Ethernet open-pair pins must be distinct pins on the same component")
    if _current_assignments(observed, open_pin):
        raise ValueError("Ethernet open-pair candidate pin must remain unassigned")
    if _current_assignments(observed, paired_pin) != frozenset((paired_net,)):
        raise ValueError("Ethernet paired net must match the current unique assignment")


@dataclass(frozen=True, slots=True)
class EthernetDataOpenPairEvidence:
    """One open Ethernet TX/RX polarity pin beside its assigned mate."""

    observed: NetlistContract
    reference: str
    component_pin_inventory: tuple[str, ...]
    direction: EthernetDirection
    polarity: EthernetPolarity
    open_pin: str
    open_function: str
    paired_pin: str
    paired_function: str
    paired_net: str

    def __post_init__(self) -> None:
        _validate_open_pair(
            self.observed,
            reference=self.reference,
            inventory=self.component_pin_inventory,
            open_pin=self.open_pin,
            open_function=self.open_function,
            paired_pin=self.paired_pin,
            paired_function=self.paired_function,
            paired_net=self.paired_net,
        )
        open_role = ethernet_data_pair_function_role(self.open_function)
        paired_role = ethernet_data_pair_function_role(self.paired_function)
        if (
            open_role != (self.direction, self.polarity)
            or paired_role is None
            or paired_role[0] != self.direction
            or paired_role[1] == self.polarity
        ):
            raise ValueError("Ethernet data evidence requires one complementary TX/RX pair")
        roles = {
            role: tuple(
                pin
                for pin, function in self.observed.pin_functions.items()
                if pin.rpartition(".")[0].casefold() == self.reference.casefold()
                and ethernet_data_pair_function_role(function) == (self.direction, role)
            )
            for role in ("positive", "negative")
        }
        if (
            len(roles["positive"]) != 1
            or len(roles["negative"]) != 1
            or {pin.casefold() for pin in roles[self.polarity]} != {self.open_pin.casefold()}
            or {
                pin.casefold()
                for pin in roles["negative" if self.polarity == "positive" else "positive"]
            }
            != {self.paired_pin.casefold()}
        ):
            raise ValueError("Ethernet data evidence requires unique complementary role pins")


@dataclass(frozen=True, slots=True)
class EthernetManagementOpenPairEvidence:
    """One open Ethernet MDC/MDIO pin beside its assigned management mate."""

    observed: NetlistContract
    reference: str
    component_pin_inventory: tuple[str, ...]
    open_role: EthernetManagementRole
    open_pin: str
    open_function: str
    paired_pin: str
    paired_function: str
    paired_net: str

    def __post_init__(self) -> None:
        _validate_open_pair(
            self.observed,
            reference=self.reference,
            inventory=self.component_pin_inventory,
            open_pin=self.open_pin,
            open_function=self.open_function,
            paired_pin=self.paired_pin,
            paired_function=self.paired_function,
            paired_net=self.paired_net,
        )
        open_role = ethernet_management_function_role(self.open_function)
        paired_role = ethernet_management_function_role(self.paired_function)
        if open_role != self.open_role or paired_role is None or paired_role == self.open_role:
            raise ValueError("Ethernet management evidence requires one MDC/MDIO role pair")
        roles = {
            role: tuple(
                pin
                for pin, function in self.observed.pin_functions.items()
                if pin.rpartition(".")[0].casefold() == self.reference.casefold()
                and ethernet_management_function_role(function) == role
            )
            for role in ("clock", "data")
        }
        if (
            len(roles["clock"]) != 1
            or len(roles["data"]) != 1
            or {pin.casefold() for pin in roles[self.open_role]} != {self.open_pin.casefold()}
            or {pin.casefold() for pin in roles["data" if self.open_role == "clock" else "clock"]}
            != {self.paired_pin.casefold()}
        ):
            raise ValueError("Ethernet management evidence requires unique MDC and MDIO pins")


EthernetUnconnectedPairEvidence: TypeAlias = (
    EthernetDataOpenPairEvidence | EthernetManagementOpenPairEvidence
)


def project_ethernet_unconnected_evidence(
    source: EthernetUnconnectedPairEvidence,
) -> CandidateEvidenceProjection:
    """Project a typed Ethernet pair into its stable rule-specific evidence fields."""
    if isinstance(source, EthernetDataOpenPairEvidence):
        return CandidateEvidenceProjection(
            rule_id=ETHERNET_DATA_UNCONNECTED_RULE_ID,
            evidence={
                source.open_pin: (),
                "ethernet_direction": (source.direction,),
                "ethernet_polarity": (source.polarity,),
                "function": (source.open_function,),
                "paired_pin": (source.paired_pin,),
                "paired_function": (source.paired_function,),
                "paired_net": (source.paired_net,),
                "component_pin_inventory": tuple(
                    sorted(number.casefold() for number in source.component_pin_inventory)
                ),
            },
        )
    return CandidateEvidenceProjection(
        rule_id=ETHERNET_MANAGEMENT_UNCONNECTED_RULE_ID,
        evidence={
            source.open_pin: (),
            "function": (source.open_function,),
            "ethernet_management_role": (source.open_role,),
            "paired_pin": (source.paired_pin,),
            "paired_function": (source.paired_function,),
            "paired_net": (source.paired_net,),
            "component_pin_inventory": tuple(
                sorted(number.casefold() for number in source.component_pin_inventory)
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class EthernetUnconnectedCandidate(Candidate):
    """Candidate whose evidence is checked against its exact current netlist."""

    source_evidence: EthernetUnconnectedPairEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: EthernetUnconnectedPairEvidence,
        *,
        subject: str,
        message: str,
    ) -> EthernetUnconnectedCandidate:
        projection = project_ethernet_unconnected_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_ethernet_unconnected_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Ethernet open-pair fields must match their typed source projection")
