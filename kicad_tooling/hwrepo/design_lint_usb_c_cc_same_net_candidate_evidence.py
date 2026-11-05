"""Typed source evidence for USB-C connector and controller CC pairs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .bus_signal_roles import usb_c_cc_role
from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .connector_identity import connector_candidate_references
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

USB_C_CC_CONNECTOR_SAME_NET_RULE_ID: DesignLintRuleId = "bus.usb_c_cc_same_net"
USB_C_CC_CONTROLLER_SAME_NET_RULE_ID: DesignLintRuleId = "bus.usb_c_cc_controller_same_net"


@dataclass(frozen=True, slots=True)
class UsbCcPinEvidence:
    """One current native CC pin and its exported function name."""

    pin: str
    function: str


def _current_reference(observed: NetlistContract, reference: str) -> str:
    matches = tuple(key for key in observed.components if key.casefold() == reference.casefold())
    if len(matches) != 1:
        raise ValueError("USB-C CC evidence requires one current fitted component")
    current = matches[0]
    if current.casefold() in {item.casefold() for item in observed.dnp_components}:
        raise ValueError("USB-C CC evidence requires a fitted component")
    return current


def _cc_roles(
    observed: NetlistContract,
    reference: str,
    *,
    skip_empty_number: bool,
) -> dict[str, list[UsbCcPinEvidence]]:
    roles: dict[str, list[UsbCcPinEvidence]] = {}
    for pin, function in observed.pin_functions.items():
        pin_reference, separator, number = pin.rpartition(".")
        role = usb_c_cc_role(function)
        if (
            separator
            and not (skip_empty_number and not number)
            and pin_reference.casefold() == reference.casefold()
            and role is not None
        ):
            roles.setdefault(role, []).append(UsbCcPinEvidence(pin=pin, function=function))
    return roles


def _validate_cc_pair(
    observed: NetlistContract,
    *,
    reference: str,
    cc1: UsbCcPinEvidence,
    cc2: UsbCcPinEvidence,
    net: str,
    require_all_role_pins_in_inventory: bool,
    exclude_two_output_pins: bool,
) -> None:
    roles = _cc_roles(
        observed,
        reference,
        skip_empty_number=not require_all_role_pins_in_inventory,
    )
    cc1_roles, cc2_roles = roles.get("CC1", ()), roles.get("CC2", ())
    if len(cc1_roles) != 1 or len(cc2_roles) != 1:
        raise ValueError("USB-C CC evidence requires one current CC1/CC2 role pair")
    if cc1_roles[0] != cc1 or cc2_roles[0] != cc2:
        raise ValueError("USB-C CC pins must match their current native functions")

    inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
    if inventory is None:
        raise ValueError("USB-C CC evidence requires a unique native pin inventory")
    inventory_numbers = {number.casefold() for number in inventory}
    role_pins = (*cc1_roles, *cc2_roles)
    pins_to_check = (
        tuple(pin for role in roles.values() for pin in role)
        if require_all_role_pins_in_inventory
        else role_pins
    )
    if any(pin.pin.rpartition(".")[2].casefold() not in inventory_numbers for pin in pins_to_check):
        raise ValueError("USB-C CC role pins must match the current native inventory")

    assignments = netlist_pin_net_index(observed)
    cc1_nets = assignments.get(cc1.pin.casefold(), set())
    cc2_nets = assignments.get(cc2.pin.casefold(), set())
    if len(cc1_nets) != 1 or len(cc2_nets) != 1 or cc1_nets != cc2_nets:
        raise ValueError("USB-C CC net must match both unique current assignments")
    if next(iter(cc1_nets)) != net:
        raise ValueError("USB-C CC net evidence must preserve its exact native name")

    if exclude_two_output_pins:
        pin_types = {
            pin.casefold(): value.strip().casefold()
            for pin, value in observed.pin_electrical_types.items()
        }
        if pin_types.get(cc1.pin.casefold()) == pin_types.get(cc2.pin.casefold()) == "output":
            raise ValueError("Two native outputs are excluded from the controller CC finding")


@dataclass(frozen=True, slots=True)
class UsbCcConnectorSameNetEvidence:
    """A recognized fitted connector with CC1 and CC2 on one net."""

    observed: NetlistContract
    reference: str
    reviewed_connector_references: tuple[str, ...]
    cc1: UsbCcPinEvidence
    cc2: UsbCcPinEvidence
    net: str

    def __post_init__(self) -> None:
        current = _current_reference(self.observed, self.reference)
        if current != self.reference:
            raise ValueError("USB-C connector reference must preserve native spelling")
        connector_references = connector_candidate_references(
            self.observed,
            self.reviewed_connector_references,
        )
        if current.casefold() not in {item.casefold() for item in connector_references}:
            raise ValueError("USB-C CC source must remain in the recognized connector scope")
        _validate_cc_pair(
            self.observed,
            reference=current,
            cc1=self.cc1,
            cc2=self.cc2,
            net=self.net,
            require_all_role_pins_in_inventory=False,
            exclude_two_output_pins=False,
        )


@dataclass(frozen=True, slots=True)
class UsbCcControllerSameNetEvidence:
    """A fitted U/IC controller with CC1 and CC2 on one net."""

    observed: NetlistContract
    reference: str
    cc1: UsbCcPinEvidence
    cc2: UsbCcPinEvidence
    net: str

    def __post_init__(self) -> None:
        current = _current_reference(self.observed, self.reference)
        if current != self.reference or not is_integrated_circuit_reference(current):
            raise ValueError("USB-C controller source requires a fitted U/IC component")
        _validate_cc_pair(
            self.observed,
            reference=current,
            cc1=self.cc1,
            cc2=self.cc2,
            net=self.net,
            require_all_role_pins_in_inventory=True,
            exclude_two_output_pins=True,
        )


UsbCcSameNetEvidence: TypeAlias = UsbCcConnectorSameNetEvidence | UsbCcControllerSameNetEvidence


def project_usb_c_cc_same_net_evidence(
    source: UsbCcSameNetEvidence,
) -> CandidateEvidenceProjection:
    """Project connector/controller CC evidence into existing rule fields."""
    if isinstance(source, UsbCcConnectorSameNetEvidence):
        return CandidateEvidenceProjection(
            rule_id=USB_C_CC_CONNECTOR_SAME_NET_RULE_ID,
            evidence={
                "connector": (source.reference,),
                "CC1_pin": (source.cc1.pin,),
                "CC1_function": (source.cc1.function,),
                "CC2_pin": (source.cc2.pin,),
                "CC2_function": (source.cc2.function,),
                "net": (source.net,),
            },
        )
    return CandidateEvidenceProjection(
        rule_id=USB_C_CC_CONTROLLER_SAME_NET_RULE_ID,
        evidence={
            "component": (source.reference,),
            "CC1_pin": (source.cc1.pin,),
            "CC1_function": (source.cc1.function,),
            "CC2_pin": (source.cc2.pin,),
            "CC2_function": (source.cc2.function,),
            "net": (source.net,),
        },
    )


@dataclass(frozen=True, slots=True)
class UsbCcSameNetCandidate(Candidate):
    """Candidate with a connector/controller source-bound CC pair."""

    source_evidence: UsbCcSameNetEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbCcSameNetEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbCcSameNetCandidate:
        projection = project_usb_c_cc_same_net_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_c_cc_same_net_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB-C CC fields must match their typed source projection")
