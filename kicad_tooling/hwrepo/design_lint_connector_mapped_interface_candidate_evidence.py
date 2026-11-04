"""Typed source records and report projections for mapped connector-pin reviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import pin_function_is_generic
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .named_rail_roles import NamedRailRoleClue, named_rail_role_clue
from .netlist_contract_models import NetlistContract

MappedInterfacePinRule: TypeAlias = Literal[
    "connector.mapped_interface_signal_unassigned",
    "connector.mapped_interface_shield_unassigned",
    "connector.mapped_interface_power_contact_unassigned",
    "connector.mapped_interface_other_unassigned",
    "connector.mapped_interface_other_named_rail",
    "connector.mapped_interface_supply_on_return_net",
    "connector.mapped_interface_signal_on_named_rail",
    "connector.mapped_interface_shield_on_return_net",
    "connector.mapped_interface_shield_on_supply_rail",
]

_UNASSIGNED_SIGNAL: MappedInterfacePinRule = "connector.mapped_interface_signal_unassigned"
_UNASSIGNED_SHIELD: MappedInterfacePinRule = "connector.mapped_interface_shield_unassigned"
_UNASSIGNED_POWER: MappedInterfacePinRule = "connector.mapped_interface_power_contact_unassigned"
_UNASSIGNED_OTHER: MappedInterfacePinRule = "connector.mapped_interface_other_unassigned"
_OTHER_NAMED_RAIL: MappedInterfacePinRule = "connector.mapped_interface_other_named_rail"
_SUPPLY_RETURN_NET: MappedInterfacePinRule = "connector.mapped_interface_supply_on_return_net"
_SIGNAL_NAMED_RAIL: MappedInterfacePinRule = "connector.mapped_interface_signal_on_named_rail"
_SHIELD_RETURN_NET: MappedInterfacePinRule = "connector.mapped_interface_shield_on_return_net"
_SHIELD_SUPPLY_RAIL: MappedInterfacePinRule = "connector.mapped_interface_shield_on_supply_rail"


@dataclass(frozen=True, slots=True)
class MappedInterfacePinFindingEvidence:
    """One finding bound to its netlist, coverage report, and matched pin record."""

    observed: NetlistContract
    coverage: ConnectorCoverageReport
    mapped_pin: ConnectorMappedPinEvidence
    rule_id: MappedInterfacePinRule
    net_label_role_clue: NamedRailRoleClue | None = None
    excluded_pins: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.rule_id not in {
            _UNASSIGNED_SIGNAL,
            _UNASSIGNED_SHIELD,
            _UNASSIGNED_POWER,
            _UNASSIGNED_OTHER,
            _OTHER_NAMED_RAIL,
            _SUPPLY_RETURN_NET,
            _SIGNAL_NAMED_RAIL,
            _SHIELD_RETURN_NET,
            _SHIELD_SUPPLY_RAIL,
        }:
            raise ValueError("Mapped connector evidence requires a supported finding rule")
        pin = self.mapped_pin.component_pin
        if source_matched_connector_pin_evidence(self.observed, self.coverage).get(pin) != (
            self.mapped_pin
        ):
            raise ValueError("Mapped connector finding must match current source evidence")
        if pin.rsplit(".", maxsplit=1)[0].casefold() in {
            reference.casefold() for reference in self.observed.dnp_components
        }:
            raise ValueError("Unpopulated connector pins cannot support mapped-pin findings")
        if pin.casefold() in self.excluded_pins:
            raise ValueError("Excluded connector pins cannot support mapped-pin findings")
        if self.mapped_pin.unconnected_reason is not None:
            raise ValueError("Intentional-open connector pins cannot support mapped-pin findings")

        role = self.mapped_pin.role
        if self.rule_id in {_UNASSIGNED_SIGNAL, _SIGNAL_NAMED_RAIL}:
            expected_role = "signal"
        elif self.rule_id in {_UNASSIGNED_SHIELD, _SHIELD_RETURN_NET, _SHIELD_SUPPLY_RAIL}:
            expected_role = "shield"
        elif self.rule_id == _SUPPLY_RETURN_NET:
            expected_role = "supply"
        elif self.rule_id == _UNASSIGNED_POWER:
            if role not in {"supply", "return"}:
                raise ValueError("Open power-contact findings require a supply or return role")
            expected_role = role
        else:
            expected_role = "other"
        if role != expected_role:
            raise ValueError("Mapped connector finding role must match its rule")

        needs_complete_coverage = self.rule_id not in {_UNASSIGNED_SIGNAL, _UNASSIGNED_SHIELD}
        if needs_complete_coverage and self.coverage.status != "COMPLETE":
            raise ValueError("This mapped connector finding requires complete coverage")

        unassigned = self.rule_id in {
            _UNASSIGNED_SIGNAL,
            _UNASSIGNED_SHIELD,
            _UNASSIGNED_POWER,
            _UNASSIGNED_OTHER,
        }
        if unassigned and self.mapped_pin.nets:
            raise ValueError("Unassigned connector findings require an open native pin")
        if not unassigned and len(self.mapped_pin.nets) != 1:
            raise ValueError("Named-rail connector findings require one native net")

        generic_role = self.rule_id in {
            _UNASSIGNED_SIGNAL,
            _UNASSIGNED_POWER,
            _UNASSIGNED_OTHER,
            _OTHER_NAMED_RAIL,
            _SUPPLY_RETURN_NET,
            _SIGNAL_NAMED_RAIL,
        }
        if generic_role and not pin_function_is_generic(self.mapped_pin.symbol_function):
            raise ValueError("This mapped connector finding requires a generic symbol function")
        if self.rule_id == _UNASSIGNED_SIGNAL and self.observed.pin_electrical_types.get(pin) in {
            "power_in",
            "power_out",
        }:
            raise ValueError("Native power pins cannot support an unassigned signal finding")

        actual_clue = None
        if not unassigned:
            actual_clue = named_rail_role_clue(self.mapped_pin.nets[0])
            if actual_clue is None:
                raise ValueError("Named-rail connector findings require a recognized label clue")
        expected_clue = actual_clue
        if self.rule_id in {_SUPPLY_RETURN_NET, _SHIELD_RETURN_NET}:
            expected_clue = "return-like"
        elif self.rule_id == _SHIELD_SUPPLY_RAIL:
            expected_clue = "supply-like"
        if expected_clue != actual_clue or expected_clue != self.net_label_role_clue:
            raise ValueError("Mapped connector net-label clue must match the native net")

        if self.rule_id != _UNASSIGNED_POWER and self.excluded_pins:
            raise ValueError("Pin exclusions only apply to open power-contact findings")


def project_mapped_interface_pin_evidence(
    source: MappedInterfacePinFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project a typed mapped-pin finding into the established report fields."""
    pin = source.mapped_pin.component_pin
    mapped = source.mapped_pin
    evidence: dict[str, tuple[str, ...]] = {
        "component_pin": (pin,),
        "interface_pin_number": (str(mapped.interface_pin_number),),
        "interface_signal": (str(mapped.interface_signal),),
        "interface_role": (str(mapped.role),),
    }
    if source.rule_id in {
        _UNASSIGNED_POWER,
        _SUPPLY_RETURN_NET,
        _SIGNAL_NAMED_RAIL,
        _SHIELD_RETURN_NET,
        _SHIELD_SUPPLY_RAIL,
    }:
        evidence["interface_voltage_domain"] = (str(mapped.voltage_domain or "<missing>"),)
    evidence["native_pin_function"] = (mapped.symbol_function or "<missing>",)
    if source.rule_id in {_UNASSIGNED_SIGNAL, _UNASSIGNED_SHIELD, _UNASSIGNED_POWER}:
        evidence["native_pin_electrical_type"] = (
            source.observed.pin_electrical_types.get(pin) or "<missing>",
        )
    evidence["assigned_nets"] = tuple(mapped.nets)
    if source.net_label_role_clue is not None:
        evidence["net_label_role_clue"] = (f"{source.net_label_role_clue} label",)
    evidence["interface_catalog_sha256"] = (str(source.coverage.interface_catalog_sha256),)
    return CandidateEvidenceProjection(rule_id=source.rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class MappedInterfacePinCandidate(Candidate):
    """Mapped connector review finding retaining its exact typed source record."""

    source_evidence: MappedInterfacePinFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: MappedInterfacePinFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> MappedInterfacePinCandidate:
        projection = project_mapped_interface_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_mapped_interface_pin_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Mapped connector fields must match their typed source projection")
