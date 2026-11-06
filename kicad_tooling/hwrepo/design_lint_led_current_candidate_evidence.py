"""Typed source evidence and report projection for mapped LED current findings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .led_current_models import LedCurrentMap, LedCurrentRangeEntry
from .led_current_range import evaluate_led_current_requirement, led_current_map_sha256
from .netlist_contract_models import NetlistContract

_RULE_ID: DesignLintRuleId = "component.mapped_led_current_range_mismatch"
_MESSAGE = (
    "The source-bound LED path is incomplete or its tolerance-corner current estimate falls "
    "outside the project-authored window. Review the exact LED, resistor, source-voltage and "
    "forward-voltage requirements. This ideal DC estimate does not establish electrical safety, "
    "brightness, dynamic behavior, or PCB continuity."
)


def _copy_netlist_source(source: NetlistContract) -> NetlistContract:
    """Retain an independent typed copy of the normalized native netlist."""
    return source.model_copy(deep=True)


@dataclass(frozen=True, slots=True)
class LedCurrentRangeFindingEvidence:
    """Authored LED map, normalized netlist source, and one matching evaluation."""

    led_map: LedCurrentMap
    observed: NetlistContract
    netlist_sha256: str | None
    entry: LedCurrentRangeEntry

    def __post_init__(self) -> None:
        led_map = self.led_map.model_copy(deep=True)
        observed = _copy_netlist_source(self.observed)
        entry = self.entry.model_copy(deep=True)
        object.__setattr__(self, "led_map", led_map)
        object.__setattr__(self, "observed", observed)
        object.__setattr__(self, "entry", entry)

        if entry.netlist_sha256 != self.netlist_sha256:
            raise ValueError("LED current evidence digest must match its native source identity")
        map_sha256 = led_current_map_sha256(led_map)
        if entry.map_sha256 != map_sha256:
            raise ValueError("LED current evidence map digest must match the authored map")
        requirement = next((item for item in led_map.leds if item.id == entry.id), None)
        if requirement is None:
            raise ValueError("LED current evidence entry must belong to the retained authored map")
        expected_entry = evaluate_led_current_requirement(
            requirement,
            observed,
            map_sha256=map_sha256,
            netlist_sha256=self.netlist_sha256,
            map_basis=led_map.basis,
        )
        if entry != expected_entry:
            raise ValueError("LED current evidence result must match its retained map and netlist")
        if entry.status == "MATCHED":
            raise ValueError("Matched LED current paths cannot produce a finding candidate")

    @property
    def subject(self) -> str:
        """Return the established LED-current finding subject."""
        return f"{self.entry.led_reference}: mapped LED current range"


def project_led_current_range_evidence(
    source: LedCurrentRangeFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the validated source record into the stable report evidence fields."""
    entry = source.entry
    evidence: Mapping[str, tuple[str, ...]] = {
        "map_id": (entry.id,),
        "map_sha256": (entry.map_sha256,),
        "netlist_sha256": (entry.netlist_sha256 or "unavailable",),
        "map_basis": (entry.map_basis,),
        "led_reference": (entry.led_reference,),
        "resistor_reference": (entry.resistor_reference,),
        "source_net": (entry.source_net,),
        "return_net": (entry.return_net,),
        "led_side_net": (entry.led_side_net,),
        "source_voltage_v": (f"{entry.source_minimum_v:g}–{entry.source_maximum_v:g}",),
        "source_voltage_basis": (entry.source_voltage_basis,),
        "forward_voltage_v": (
            f"{entry.forward_voltage_minimum_v:g}–{entry.forward_voltage_maximum_v:g}",
        ),
        "forward_voltage_basis": (entry.forward_voltage_basis,),
        "target_current_ma": (
            f"{entry.target_current_minimum_ma:g}–{entry.target_current_maximum_ma:g}",
        ),
        "target_current_basis": (entry.target_current_basis,),
        "resistor_nominal_ohms": (
            "unavailable" if entry.resistance_ohms is None else f"{entry.resistance_ohms:g}",
        ),
        "resistor_range_ohms": (
            f"{entry.minimum_nominal_resistance_ohms:g}–{entry.maximum_nominal_resistance_ohms:g}",
        ),
        "resistor_tolerance": (f"{entry.maximum_tolerance_percent:g}% ({entry.tolerance_basis})",),
        "calculated_current_ma": (
            "unavailable"
            if entry.calculated_current_minimum_ma is None
            or entry.calculated_current_maximum_ma is None
            else (
                f"{entry.calculated_current_minimum_ma:g}–{entry.calculated_current_maximum_ma:g}"
            ),
        ),
        "pin_nets": tuple(
            f"{pin}={','.join(nets) or '<unconnected>'}"
            for pin, nets in sorted(entry.pin_nets.items())
        ),
        "issues": entry.issues,
    }
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class LedCurrentRangeCandidate(Candidate):
    """Candidate whose stable report mapping derives from retained typed sources."""

    source_evidence: LedCurrentRangeFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: LedCurrentRangeFindingEvidence,
    ) -> LedCurrentRangeCandidate:
        projection = project_led_current_range_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=source_evidence.subject,
            message=_MESSAGE,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_led_current_range_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != self.source_evidence.subject
            or self.message != _MESSAGE
            or self.evidence != projection.evidence
        ):
            raise ValueError("LED current candidate must match its retained source projection")


def led_current_range_candidate(
    source_evidence: LedCurrentRangeFindingEvidence,
) -> LedCurrentRangeCandidate:
    """Build a policy-neutral LED-current candidate from verified source evidence."""
    return LedCurrentRangeCandidate.from_source_evidence(source_evidence)
