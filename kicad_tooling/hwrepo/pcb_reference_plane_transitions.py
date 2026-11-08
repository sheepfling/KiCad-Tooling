"""Opt-in review for appreciable route coverage by alternate adjacent zone nets."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_reference_plane_models import (
    PcbReferencePlaneCoverageEntry,
    PcbReferencePlaneCoverageReport,
)

RULE_ID: DesignLintRuleId = "pcb.alternate_reference_plane_run"


@dataclass(frozen=True, slots=True)
class PcbAlternateReferenceRunMeasurement:
    """Exact per-net and per-layer sum of alternate filled-zone centerline coverage."""

    alternate_net: str
    reference_layer: str
    minimum_length_um: int
    track_coverage_nm: tuple[tuple[str, Fraction], ...]

    def __post_init__(self) -> None:
        if not self.track_coverage_nm or any(amount <= 0 for _, amount in self.track_coverage_nm):
            raise ValueError("Alternate reference-run measurements need positive coverage")
        track_ids = tuple(track_id.casefold() for track_id, _ in self.track_coverage_nm)
        if len(set(track_ids)) != len(track_ids):
            raise ValueError("Alternate reference-run measurements cannot repeat a track")

    @property
    def total_coverage_nm(self) -> Fraction:
        return sum((amount for _, amount in self.track_coverage_nm), Fraction(0))

    @property
    def meets_threshold(self) -> bool:
        return self.total_coverage_nm >= self.minimum_length_um * 1000


def alternate_reference_plane_run_measurements(
    entry: PcbReferencePlaneCoverageEntry,
) -> tuple[PcbAlternateReferenceRunMeasurement, ...]:
    """Apply the authored aggregate-length threshold independently per net and layer."""
    threshold_um = entry.minimum_alternate_reference_length_um
    if threshold_um is None:
        return ()
    grouped: dict[tuple[str, str], tuple[set[str], list[tuple[str, Fraction]]]] = {}
    for track in entry.tracks:
        for coverage in track.alternate_reference_coverages:
            key = (track.reference_layer.casefold(), coverage.net.casefold())
            display_nets, contributions = grouped.setdefault(key, (set(), []))
            display_nets.add(coverage.net)
            contributions.append(
                (
                    track.track_uuid,
                    track.segment_length_nm
                    * Fraction(
                        coverage.covered_fraction_numerator,
                        coverage.covered_fraction_denominator,
                    ),
                )
            )

    measurements: list[PcbAlternateReferenceRunMeasurement] = []
    for (_layer_key, _net_key), (display_nets, contributions) in sorted(grouped.items()):
        measurements.append(
            PcbAlternateReferenceRunMeasurement(
                alternate_net=min(display_nets, key=lambda net: (net.casefold(), net)),
                reference_layer=next(
                    track.reference_layer
                    for track in entry.tracks
                    if track.reference_layer.casefold() == _layer_key
                    and any(
                        item.net.casefold() == _net_key
                        for item in track.alternate_reference_coverages
                    )
                ),
                minimum_length_um=threshold_um,
                track_coverage_nm=tuple(
                    sorted(contributions, key=lambda item: (item[0].casefold(), item[0]))
                ),
            )
        )
    return tuple(measurements)


@dataclass(frozen=True, slots=True)
class PcbAlternateReferenceRunEvidence:
    """Source-bound exact coverage measurement for one alternate net and layer."""

    report: PcbReferencePlaneCoverageReport
    entry: PcbReferencePlaneCoverageEntry
    measurement: PcbAlternateReferenceRunMeasurement

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Alternate reference-run evidence requires a native scan")
        if self.entry not in self.report.entries:
            raise ValueError("Alternate reference-run entry must belong to its source report")
        if self.measurement not in alternate_reference_plane_run_measurements(self.entry):
            raise ValueError("Alternate reference-run measurement must derive from the entry")
        excluded_nets = {self.entry.signal_net.casefold(), self.entry.reference_net.casefold()}
        if self.measurement.alternate_net.casefold() in excluded_nets:
            raise ValueError("Alternate reference-run net must differ from signal and reference")
        if not self.measurement.meets_threshold:
            raise ValueError(
                "Alternate reference-run evidence does not meet its authored threshold"
            )


def project_pcb_alternate_reference_run(
    source: PcbAlternateReferenceRunEvidence,
) -> CandidateEvidenceProjection:
    """Project exact measured route contributions and authored scope into lint evidence."""
    entry = source.entry
    measurement = source.measurement
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "requirement_id": (entry.id,),
            "signal_net": (entry.signal_net,),
            "signal_layers": entry.signal_layers,
            "reference_net": (entry.reference_net,),
            "alternate_net": (measurement.alternate_net,),
            "adjacent_reference_layer": (measurement.reference_layer,),
            "minimum_alternate_reference_length_um": (str(measurement.minimum_length_um),),
            "observed_alternate_reference_coverage_nm": (str(measurement.total_coverage_nm),),
            "contributing_tracks": tuple(
                f"{track_id}:{amount}nm" for track_id, amount in measurement.track_coverage_nm
            ),
            "coverage_status": (entry.status,),
            "basis": (entry.basis,),
            "metric": (
                "Sum of exact per-track centerline fractions inside filled adjacent-layer zones "
                + "for this alternate net; contributions can be disjoint and are not a continuity proof",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbAlternateReferenceRunCandidate(Candidate):
    """Alternate-net coverage finding retaining its typed source report and entry."""

    source_evidence: PcbAlternateReferenceRunEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbAlternateReferenceRunEvidence,
    ) -> PcbAlternateReferenceRunCandidate:
        projection = project_pcb_alternate_reference_run(source_evidence)
        measurement = source_evidence.measurement
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.entry.id}: {source_evidence.entry.signal_net} over "
                f"{measurement.alternate_net} on {measurement.reference_layer}"
            ),
            message=(
                f"Review {measurement.total_coverage_nm / 1000} µm of mapped "
                f"{source_evidence.entry.signal_net} track centerline measured over filled "
                f"{measurement.alternate_net} copper on adjacent {measurement.reference_layer}; "
                f"the project-authored review threshold is {measurement.minimum_length_um} µm. "
                "This total is summed across observed straight track items, so intervals may be "
                "disjoint and the measurement does not establish copper continuity, return "
                "adequacy, or intent."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_alternate_reference_run(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Alternate reference-run evidence must match its source projection")


def alternate_reference_plane_run_candidates(
    report: PcbReferencePlaneCoverageReport,
) -> tuple[PcbAlternateReferenceRunCandidate, ...]:
    """Emit opt-in review candidates whose exact coverage sums meet authored bounds."""
    candidates = (
        PcbAlternateReferenceRunCandidate.from_source_evidence(
            PcbAlternateReferenceRunEvidence(report=report, entry=entry, measurement=measurement)
        )
        for entry in report.entries
        for measurement in alternate_reference_plane_run_measurements(entry)
        if measurement.meets_threshold
    )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                item.evidence["contributing_tracks"],
            ),
        )
    )
