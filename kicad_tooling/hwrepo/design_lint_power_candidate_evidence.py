"""Typed source projections for schematic power and supply candidate findings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

from .component_pin_patterns import RepeatedComponentSupplyPins
from .component_power_input_domains import SplitPowerInputDomains
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .net_dc_reference import ConnectorCapacitorOnlyNet
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
)

_SAME_VOLTAGE_POWER_INPUTS: DesignLintRuleId = "component.same_voltage_power_inputs_split"
_IC_RAIL_CAPACITOR_GAP: DesignLintRuleId = "power.ic_rail_without_fitted_capacitor"
_POWER_INPUT_SOURCE_PATH_GAP: DesignLintRuleId = "power.input_without_supported_source_path"
_CONNECTOR_CAPACITOR_ONLY_NET: DesignLintRuleId = "net.connector_capacitor_only_no_dc_anchor"
_REPEATED_SUPPLY_PIN_FUNCTION: DesignLintRuleId = "component.repeated_supply_pin_function"
_NUMBERED_POWER_RAILS: DesignLintRuleId = "net.numbered_power_rails"


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
