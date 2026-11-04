"""Typed source evidence and the stable report projection for I2C pull-up candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .design_lint_types import Candidate, CandidateEvidenceProjection
from .i2c_pullup_heuristics import (
    I2cLowEquivalentResistanceObservation,
    I2cMultiplePullupRailFamilies,
    I2cPullupGap,
)
from .i2c_pullup_voltage_models import I2cPullupVoltageCoverageEntry

I2cPullupCandidateEvidence: TypeAlias = (
    I2cPullupGap
    | I2cLowEquivalentResistanceObservation
    | I2cMultiplePullupRailFamilies
    | I2cPullupVoltageCoverageEntry
)

I2cPullupEvidenceProjection = CandidateEvidenceProjection


def project_i2c_pullup_evidence(
    source: I2cPullupCandidateEvidence,
) -> I2cPullupEvidenceProjection:
    """Keep source records authoritative and centralize their legacy wire mapping."""
    if isinstance(source, I2cPullupGap):
        return I2cPullupEvidenceProjection(
            rule_id="bus.i2c_missing_pullup",
            evidence={
                "SDA": (source.sda_net,),
                "SCL": (source.scl_net,),
                "pins": (*source.sda_pins, *source.scl_pins),
                "missing_pullups": source.missing_lines,
            },
        )
    if isinstance(source, I2cLowEquivalentResistanceObservation):
        return I2cPullupEvidenceProjection(
            rule_id="bus.i2c_low_equivalent_resistance",
            evidence={
                "SDA": (source.sda_net,),
                "SCL": (source.scl_net,),
                "lines": tuple(item.line for item in source.lines),
                "pins": (*source.sda_pins, *source.scl_pins),
                "equivalent_ohms": tuple(
                    f"{item.line}={item.equivalent_resistance_ohms:.6g}Ω" for item in source.lines
                ),
                "pullup_resistors": tuple(
                    f"{' + '.join(path.references)}={path.resistance_ohms:.6g}Ω to {path.rail_net}"
                    for line in source.lines
                    for path in line.pullup_paths
                ),
            },
        )
    if isinstance(source, I2cMultiplePullupRailFamilies):
        return I2cPullupEvidenceProjection(
            rule_id="bus.i2c_multiple_pullup_rail_families",
            evidence={
                "SDA": (source.sda_net,),
                "SCL": (source.scl_net,),
                "pins": source.pins,
                "rail_families": source.rail_families,
                "pullup_paths": source.pullup_paths,
            },
        )
    if source.status != "OPEN":
        raise ValueError("Only open I2C pull-up voltage coverage creates a finding")
    return I2cPullupEvidenceProjection(
        rule_id="bus.i2c_pullup_input_limit_coverage",
        evidence={
            "SDA": (source.sda_net,),
            "SCL": (source.scl_net,),
            "line": (source.line,),
            "signal_net": (source.signal_net,),
            "pullup_rails": source.pullup_rails,
            "endpoint_pins": source.endpoint_pins,
            "covered_input_pins": source.covered_input_pins,
            "missing_input_pins": source.missing_input_pins,
            "issues": source.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class I2cPullupCandidate(Candidate):
    """Candidate that retains typed source evidence beside its stable wire view."""

    source_evidence: I2cPullupCandidateEvidence

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_i2c_pullup_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("I2C pull-up candidate rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("I2C pull-up finding evidence must match its typed source projection")

    @classmethod
    def from_source_evidence(
        cls,
        *,
        source_evidence: I2cPullupCandidateEvidence,
        subject: str,
        message: str,
    ) -> I2cPullupCandidate:
        """Construct the compatibility evidence only from an owning typed record."""
        projection = project_i2c_pullup_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )
