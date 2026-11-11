"""Typed source projections for schematic power and supply candidate findings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

from .component_pin_patterns import RepeatedComponentSupplyPins
from .component_power_input_domains import SplitPowerInputDomains
from .design_lint_ic_decoupling_candidate_evidence import IcDecouplingFindingEvidence
from .design_lint_power_pin_role_evidence import (
    NamedPowerPinNetRoleConflictEvidence,
    NamedSupplyPinNegativeRailEvidence,
)
from .design_lint_regulator_passive_candidate_evidence import (
    RegulatorPassivePinRoleFindingEvidence,
    RegulatorPassiveTopologyFindingEvidence,
)
from .design_lint_regulator_support_candidate_evidence import (
    RegulatorSupportPinNetCoverageFindingEvidence,
    RegulatorSupportPinNetFindingEvidence,
    RegulatorSupportPinRoleFindingEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .net_dc_reference import ConnectorCapacitorOnlyNet
from .power_component_supply_range import ComponentSupplyVoltageRangeIssue
from .power_component_supply_range_coverage import ComponentSupplyRangePinCoverageIssue
from .power_component_supply_range_map_coverage import ComponentSupplyRangeMapCoverageIssue
from .power_decoupling import PowerRailCapacitorGap
from .power_pin_paths import PowerInputSourcePathGap
from .power_rail_models import NumberedPowerRailGroup

PowerCandidateSource: TypeAlias = (
    SplitPowerInputDomains
    | PowerRailCapacitorGap
    | PowerInputSourcePathGap
    | ConnectorCapacitorOnlyNet
    | RepeatedComponentSupplyPins
    | NumberedPowerRailGroup
    | NamedPowerPinNetRoleConflictEvidence
    | NamedSupplyPinNegativeRailEvidence
    | IcDecouplingFindingEvidence
    | RegulatorPassiveTopologyFindingEvidence
    | RegulatorPassivePinRoleFindingEvidence
    | RegulatorSupportPinRoleFindingEvidence
    | RegulatorSupportPinNetFindingEvidence
    | RegulatorSupportPinNetCoverageFindingEvidence
    | ComponentSupplyVoltageRangeIssue
    | ComponentSupplyRangePinCoverageIssue
    | ComponentSupplyRangeMapCoverageIssue
)

_SAME_VOLTAGE_POWER_INPUTS: DesignLintRuleId = "component.same_voltage_power_inputs_split"
_IC_RAIL_CAPACITOR_GAP: DesignLintRuleId = "power.ic_rail_without_fitted_capacitor"
_POWER_INPUT_SOURCE_PATH_GAP: DesignLintRuleId = "power.input_without_supported_source_path"
_CONNECTOR_CAPACITOR_ONLY_NET: DesignLintRuleId = "net.connector_capacitor_only_no_dc_anchor"
_REPEATED_SUPPLY_PIN_FUNCTION: DesignLintRuleId = "component.repeated_supply_pin_function"
_NUMBERED_POWER_RAILS: DesignLintRuleId = "net.numbered_power_rails"
_POWER_PIN_NET_ROLE_CONFLICT: DesignLintRuleId = "power.pin_function_net_role_conflict"
_NAMED_SUPPLY_PIN_ON_NEGATIVE_RAIL: DesignLintRuleId = "power.named_supply_pin_on_negative_rail"
_IC_DECOUPLING_BELOW_MINIMUM: DesignLintRuleId = "power.ic_decoupling_below_project_minimum"
_REGULATOR_PASSIVE_TOPOLOGY_MISMATCH: DesignLintRuleId = (
    "power.regulator_required_passive_topology_mismatch"
)
_REGULATOR_PIN_ROLE_MISMATCH: DesignLintRuleId = "power.regulator_pin_role_mismatch"
_REGULATOR_SUPPORT_PIN_ROLE_MISMATCH: DesignLintRuleId = "power.regulator_support_pin_role_mismatch"
_REGULATOR_SUPPORT_PIN_NET_MISMATCH: DesignLintRuleId = "power.regulator_support_pin_net_mismatch"
_REGULATOR_SUPPORT_PIN_NET_COVERAGE_MISSING: DesignLintRuleId = (
    "power.regulator_support_pin_net_map_coverage_missing"
)


def _string_tuples(values: Mapping[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Project typed net and pin maps into the report's stable string fields."""
    return {str(key): tuple(str(value) for value in items) for key, items in values.items()}


def project_power_candidate_evidence(
    source: PowerCandidateSource,
) -> CandidateEvidenceProjection:
    """Map a typed power scan record to its established rule and evidence fields."""
    if isinstance(source, SplitPowerInputDomains):
        return CandidateEvidenceProjection(
            rule_id=_SAME_VOLTAGE_POWER_INPUTS,
            evidence=_string_tuples(source.pins),
        )
    if isinstance(source, PowerRailCapacitorGap):
        evidence = {
            "net": (source.net,),
            "power_input_pins": source.input_pins,
            "component_references": source.component_references,
        }
        return CandidateEvidenceProjection(rule_id=_IC_RAIL_CAPACITOR_GAP, evidence=evidence)
    if isinstance(source, PowerInputSourcePathGap):
        anchor_state = "recognized" if source.source_nets else "not_recognized"
        evidence = {
            "net": (source.net,),
            "power_input_pins": source.input_pins,
            "fitted_capacitors_to_return": source.capacitor_references,
            "recognized_source_nets": source.source_nets,
            "source_anchor_state": (anchor_state,),
        }
        return CandidateEvidenceProjection(rule_id=_POWER_INPUT_SOURCE_PATH_GAP, evidence=evidence)
    if isinstance(source, ConnectorCapacitorOnlyNet):
        evidence = {
            "net": (source.net,),
            "connector_pins": source.connector_pins,
            "capacitor_pins": source.capacitor_pins,
            "component_symbols": source.component_symbols,
        }
        return CandidateEvidenceProjection(rule_id=_CONNECTOR_CAPACITOR_ONLY_NET, evidence=evidence)
    if isinstance(source, RepeatedComponentSupplyPins):
        return CandidateEvidenceProjection(
            rule_id=_REPEATED_SUPPLY_PIN_FUNCTION,
            evidence=_string_tuples(source.pins),
        )
    if isinstance(source, NamedPowerPinNetRoleConflictEvidence):
        return CandidateEvidenceProjection(
            rule_id=_POWER_PIN_NET_ROLE_CONFLICT,
            evidence={
                source.pin: (
                    f"native_function={source.function}",
                    f"pin_role={source.pin_role}",
                ),
                "assigned_net": (source.net,),
                "opposite_net_role_sources": source.opposite_role_sources,
            },
        )
    if isinstance(source, NamedSupplyPinNegativeRailEvidence):
        return CandidateEvidenceProjection(
            rule_id=_NAMED_SUPPLY_PIN_ON_NEGATIVE_RAIL,
            evidence={
                source.pin: (
                    f"native_function={source.function}",
                    f"supply_function_key={source.supply_function_key}",
                ),
                "assigned_net": (source.net,),
                "negative_rail_key": (source.negative_rail_key,),
            },
        )
    if isinstance(source, IcDecouplingFindingEvidence):
        requirement = source.requirement
        evidence = {
            "requirement_id": (requirement.id,),
            "basis": (requirement.basis,),
            "ic_reference": (requirement.ic_reference,),
            "power_pin": (requirement.power_pin,),
            "power_net": (requirement.power_net,),
            "return_net": (requirement.return_net,),
            "capacitor_references": tuple(item.reference for item in requirement.capacitors),
            "capacitor_values_pf": tuple(
                f"{item.reference}="
                f"{item.capacitance_pf if item.capacitance_pf is not None else 'unsupported'}"
                for item in source.review.capacitor_values
            ),
            "minimum_total_capacitance_pf": (str(source.minimum_pf),),
            "observed_total_capacitance_pf": (
                () if source.total_pf is None else (str(source.total_pf),)
            ),
            "requirement_sha256": (source.requirement_sha256,),
            "mapping_issues": source.review.issues,
        }
        return CandidateEvidenceProjection(rule_id=_IC_DECOUPLING_BELOW_MINIMUM, evidence=evidence)
    if isinstance(source, RegulatorPassiveTopologyFindingEvidence):
        requirement = source.requirement
        evidence = {
            "topology_id": (requirement.id,),
            "regulator": (requirement.regulator.reference,),
            "required_passive_roles": tuple(
                f"{item.role}:{item.component.reference}" for item in requirement.required_passives
            ),
            "approved_alternatives": tuple(
                f"{alternative.id}:{alternative.basis}"
                for alternative in requirement.approved_alternatives
            ),
            "components": source.component_references,
            "issues": source.issues,
            "map_sha256": (source.map_sha256,),
        }
        return CandidateEvidenceProjection(
            rule_id=_REGULATOR_PASSIVE_TOPOLOGY_MISMATCH,
            evidence=evidence,
        )
    if isinstance(source, RegulatorPassivePinRoleFindingEvidence):
        requirement = source.requirement
        return CandidateEvidenceProjection(
            rule_id=_REGULATOR_PIN_ROLE_MISMATCH,
            evidence={
                "topology_id": (requirement.id,),
                "regulator": (requirement.regulator.reference,),
                "components": source.component_references,
                "issues": source.issues,
                "map_sha256": (source.map_sha256,),
            },
        )
    if isinstance(source, RegulatorSupportPinRoleFindingEvidence):
        topology = source.topology
        component = source.component
        return CandidateEvidenceProjection(
            rule_id=_REGULATOR_SUPPORT_PIN_ROLE_MISMATCH,
            evidence={
                "topology_id": (topology.id,),
                "regulator": (topology.regulator_reference,),
                "support_role": (component.role,),
                "component": (component.reference,),
                "issues": source.issues,
                "map_sha256": (source.map_sha256,),
            },
        )
    if isinstance(source, RegulatorSupportPinNetFindingEvidence):
        topology = source.topology
        component = source.component
        return CandidateEvidenceProjection(
            rule_id=_REGULATOR_SUPPORT_PIN_NET_MISMATCH,
            evidence={
                "topology_id": (topology.id,),
                "regulator": (topology.regulator_reference,),
                "support_role": (component.role,),
                "component": (component.reference,),
                "issues": source.issues,
                "map_sha256": (source.map_sha256,),
            },
        )
    if isinstance(source, RegulatorSupportPinNetCoverageFindingEvidence):
        topology = source.topology
        component = source.component
        return CandidateEvidenceProjection(
            rule_id=_REGULATOR_SUPPORT_PIN_NET_COVERAGE_MISSING,
            evidence={
                "topology_id": (topology.id,),
                "regulator": (topology.regulator_reference,),
                "support_role": (component.role,),
                "component": (component.reference,),
                "issues": source.issues,
                "maps_sha256": (source.maps_sha256,),
            },
        )
    if isinstance(source, ComponentSupplyVoltageRangeIssue):
        requirement = source.requirement
        return CandidateEvidenceProjection(
            rule_id="power.component_supply_voltage_outside_range",
            evidence={
                "requirement_id": (requirement.id,),
                "component": (requirement.reference,),
                "pin": (requirement.pin,),
                "expected_pin_function": (requirement.expected_pin_function,),
                "reviewed_range_v": (
                    f"{requirement.minimum_voltage_v:g}..{requirement.maximum_voltage_v:g}",
                ),
                "range_source": (requirement.range_source,),
                "range_conditions": (requirement.range_conditions,),
                "assigned_net": () if source.actual_net is None else (source.actual_net,),
                "net_label_voltage_v": (
                    () if source.actual_voltage_v is None else (f"{source.actual_voltage_v:g}",)
                ),
                "issues": source.issues,
                "map_sha256": (source.map_sha256,),
            },
        )
    if isinstance(source, ComponentSupplyRangePinCoverageIssue):
        return CandidateEvidenceProjection(
            rule_id="power.component_supply_range_pin_coverage",
            evidence={
                "component": (source.reference,),
                "symbol": (source.symbol,),
                "native_power_input_pins": source.native_power_input_pins,
                "mapped_range_pins": source.mapped_range_pins,
                "unmapped_power_input_pins": source.unmapped_power_input_pins,
                "pin_type_unavailable_pins": source.pin_type_unavailable_pins,
                "pin_inventory_unavailable": ("true",) if source.pin_inventory_unavailable else (),
                "pin_inventory_disagreement_pins": source.pin_inventory_disagreement_pins,
                "map_sha256": (source.map_sha256,),
            },
        )
    if isinstance(source, ComponentSupplyRangeMapCoverageIssue):
        return CandidateEvidenceProjection(
            rule_id="power.component_supply_range_map_coverage",
            evidence={
                "component": (source.reference,),
                "symbol": (source.symbol,) if source.symbol else (),
                "native_power_input_pins": source.native_power_input_pins,
                "stale_map_identity": ("true",) if source.stale_map_identity else (),
                "map_sha256": (source.map_sha256,),
            },
        )
    return CandidateEvidenceProjection(
        rule_id=_NUMBERED_POWER_RAILS,
        evidence=_string_tuples(source.nets),
    )


@dataclass(frozen=True, slots=True)
class PowerCandidate(Candidate):
    """Power finding that retains the source record behind its report fields."""

    source_evidence: PowerCandidateSource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PowerCandidateSource,
        *,
        subject: str,
        message: str,
    ) -> PowerCandidate:
        projection = project_power_candidate_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_power_candidate_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Power candidate fields must match their typed source projection")
