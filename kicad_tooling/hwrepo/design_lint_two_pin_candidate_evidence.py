"""Typed source projections for same-net two-pin component findings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .component_roles import component_role_binding_evidence
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .two_pin_components import TwoPinComponentOnSameNet

_TWO_PIN_RULES: Mapping[str, DesignLintRuleId] = MappingProxyType(
    {
        "diode": "component.two_pin_diode_same_net",
        "crystal": "component.two_pin_crystal_same_net",
        "fuse": "component.two_pin_fuse_same_net",
        "polyfuse": "component.two_pin_fuse_same_net",
        "ferrite_bead": "component.two_pin_ferrite_same_net",
        "switch": "component.two_pin_switch_same_net",
    }
)
_TWO_PIN_PASSIVE_KINDS = frozenset({"resistor", "capacitor", "inductor", "varistor", "thermistor"})


@dataclass(frozen=True, slots=True)
class TwoPinComponentFindingEvidence:
    """One exact same-net component record from the native two-pin scan."""

    component: TwoPinComponentOnSameNet

    def __post_init__(self) -> None:
        if self.component.kind not in _TWO_PIN_RULES and (
            self.component.kind not in _TWO_PIN_PASSIVE_KINDS
        ):
            raise ValueError(f"Unsupported same-net component kind: {self.component.kind}")


def project_two_pin_component_evidence(
    source: TwoPinComponentFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project a scanned component into its kind-specific stable report fields."""
    component = source.component
    rule_id = _TWO_PIN_RULES.get(component.kind, "component.two_pin_passive_same_net")
    kind_field = "component_kind" if component.kind in _TWO_PIN_RULES else "passive_kind"
    evidence = {
        "symbol": (component.symbol,),
        "value": (component.value,),
        kind_field: (component.kind,),
        "net": (component.net,),
        "pin_assignments": tuple(
            f"{component.reference}.{number} -> {component.net}" for number in component.pin_numbers
        ),
    }
    if component.role_binding is not None:
        evidence.update(component_role_binding_evidence(component.role_binding))
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class TwoPinSameNetCandidate(Candidate):
    """Two-pin finding retaining its exact typed same-net scan record."""

    source_evidence: TwoPinComponentFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: TwoPinComponentFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> TwoPinSameNetCandidate:
        projection = project_two_pin_component_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_two_pin_component_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Two-pin fields must match their typed source projection")
