"""Typed source evidence and report projection for thermal-pad scope prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .pcb_thermal_via_models import PcbThermalViaMap

RULE_ID: DesignLintRuleId = "pcb.explicit_thermal_pad_scope_unreviewed"
_EXPLICIT_THERMAL_PAD_FUNCTIONS = frozenset({"ep", "epad", "exposedpad", "thermalpad"})
_REVIEW_MESSAGE = (
    "The native schematic names this fitted footprint pin as an exposed or thermal pad, but no "
    "exact PCB thermal-via map requirement covers it. Review whether the pad needs an "
    "independently based via requirement; this prompt does not imply that vias are required or "
    "adequate."
)
_REVIEW_BOUNDARY = (
    "Explicit function-name match only; no thermal requirement or via adequacy is inferred."
)


def is_explicit_thermal_pad_function(function: str) -> bool:
    """Match only exported EP-like labels after case and separator normalization."""
    key = re.sub(r"[\s_-]+", "", function.casefold())
    return key in _EXPLICIT_THERMAL_PAD_FUNCTIONS


@dataclass(frozen=True, slots=True)
class PcbExplicitThermalPadScopeEvidence:
    """Retain the observed netlist and authored map behind one review prompt."""

    observed: NetlistContract
    thermal_via_map: PcbThermalViaMap | None
    pin: str
    function: str
    footprint: str

    def __post_init__(self) -> None:
        if self.observed.pin_functions.get(self.pin) != self.function:
            raise ValueError("Thermal-pad evidence function must match the observed netlist")
        reference, separator, number = self.pin.rpartition(".")
        if not separator or not reference or not number:
            raise ValueError("Thermal-pad evidence requires an exact reference.pin identity")
        component = next(
            (
                item
                for candidate_reference, item in self.observed.components.items()
                if candidate_reference.casefold() == reference.casefold()
            ),
            None,
        )
        if component is None or component.footprint != self.footprint or not self.footprint.strip():
            raise ValueError("Thermal-pad evidence footprint must match a fitted netlist component")
        if reference.casefold() in {item.casefold() for item in self.observed.dnp_components}:
            raise ValueError("DNP components cannot produce thermal-pad scope prompts")
        if not is_explicit_thermal_pad_function(self.function):
            raise ValueError("Thermal-pad evidence requires an explicitly recognized pin function")
        if self.thermal_via_map is not None and any(
            item.pad.casefold() == self.pin.casefold() for item in self.thermal_via_map.requirements
        ):
            raise ValueError("Mapped thermal pads cannot produce an unmapped-scope prompt")


def project_explicit_thermal_pad_scope_evidence(
    source: PcbExplicitThermalPadScopeEvidence,
) -> CandidateEvidenceProjection:
    """Project the established prompt fields from retained source records."""
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "pin": (source.pin,),
            "pin_function": (source.function,),
            "footprint": (source.footprint,),
            "review_state": ("no exact thermal-via requirement covers this pin",),
            "review_boundary": (_REVIEW_BOUNDARY,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbExplicitThermalPadScopeCandidate(Candidate):
    """Review candidate whose fields are checked against its retained inputs."""

    source_evidence: PcbExplicitThermalPadScopeEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbExplicitThermalPadScopeEvidence,
    ) -> PcbExplicitThermalPadScopeCandidate:
        projection = project_explicit_thermal_pad_scope_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.pin}: {source_evidence.function} ({source_evidence.footprint})"
            ),
            message=_REVIEW_MESSAGE,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_explicit_thermal_pad_scope_evidence(self.source_evidence)
        expected_subject = (
            f"{self.source_evidence.pin}: {self.source_evidence.function} "
            f"({self.source_evidence.footprint})"
        )
        if (
            self.rule_id != projection.rule_id
            or self.subject != expected_subject
            or self.message != _REVIEW_MESSAGE
            or self.evidence != projection.evidence
        ):
            raise ValueError("Thermal-pad candidate must match its retained source projection")
