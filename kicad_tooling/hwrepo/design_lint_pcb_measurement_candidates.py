"""Theme-specific candidate translators for PCB measurements and rule coverage."""

from __future__ import annotations

from .design_lint_pcb_decoupling_candidate_evidence import (
    PcbDecouplingCandidate,
    PcbDecouplingFindingEvidence,
)
from .design_lint_pcb_inputs import PcbCandidateInputs
from .design_lint_pcb_protection_path_candidate_evidence import (
    PcbProtectionPathCandidate,
    PcbProtectionPathFindingEvidence,
)
from .design_lint_pcb_reference_plane_candidate_evidence import (
    PcbReferencePlaneCandidate,
    PcbReferencePlaneFindingEvidence,
    reference_plane_below_threshold_track_uuids,
)
from .design_lint_pcb_thermal_via_candidate_evidence import (
    PcbThermalViaCandidate,
    PcbThermalViaFindingEvidence,
)
from .design_lint_pcb_track_width_candidate_evidence import (
    PcbTrackWidthCandidate,
    PcbTrackWidthFindingEvidence,
)
from .design_lint_types import Candidate
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_protection_path_models import PcbProtectionPathCoverageReport
from .pcb_reference_plane_islands import unanchored_reference_zone_island_candidates
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_reference_plane_transitions import alternate_reference_plane_run_candidates
from .pcb_thermal_via_models import PcbThermalViaCoverageReport
from .pcb_track_width_models import PcbTrackWidthCoverageReport


def scan_pcb_measurement_candidates(inputs: PcbCandidateInputs) -> tuple[Candidate, ...]:
    """Route the PCB group's resolved measurement coverage to its translators."""
    return pcb_measurement_coverage_candidates(
        pcb_decoupling_coverage=inputs.decoupling,
        pcb_protection_path_coverage=inputs.protection_path,
        pcb_track_width_coverage=inputs.track_width,
        pcb_reference_plane_coverage=inputs.reference_plane,
        pcb_thermal_via_coverage=inputs.thermal_via,
    )


def pcb_measurement_coverage_candidates(
    *,
    pcb_decoupling_coverage: PcbDecouplingCoverageReport | None = None,
    pcb_protection_path_coverage: PcbProtectionPathCoverageReport | None = None,
    pcb_track_width_coverage: PcbTrackWidthCoverageReport | None = None,
    pcb_reference_plane_coverage: PcbReferencePlaneCoverageReport | None = None,
    pcb_thermal_via_coverage: PcbThermalViaCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Translate PCB measurement coverage gaps into review candidates."""
    found: list[Candidate] = []
    if pcb_decoupling_coverage is not None:
        for entry in pcb_decoupling_coverage.entries:
            if entry.status == "COMPLETE" and entry.max_distance_um is not None:
                continue
            found.append(
                PcbDecouplingCandidate.from_source_evidence(
                    PcbDecouplingFindingEvidence(
                        report=pcb_decoupling_coverage,
                        entry=entry,
                    ),
                    subject=f"{entry.id}: IC supply {entry.ic_supply_pad}",
                    message=(
                        "Review the mapped decoupling capacitor placement and copper paths. "
                        "The supply-pad and optional connected return-via distances are geometric "
                        "screens; they do not estimate loop inductance or prove adequate decoupling."
                    ),
                )
            )
    if pcb_protection_path_coverage is not None:
        for entry in pcb_protection_path_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            found.append(
                PcbProtectionPathCandidate.from_source_evidence(
                    PcbProtectionPathFindingEvidence(
                        report=pcb_protection_path_coverage,
                        entry=entry,
                    ),
                    subject=(
                        f"{entry.id}: {entry.connector_signal_pad} to {entry.protection_signal_pad}"
                    ),
                    message=(
                        "Review the mapped connector-to-protection pad path and reference-via "
                        "coverage against the project limits. Pad-center distance is a straight-line "
                        "screen, not routed copper length; native connectivity does not prove that "
                        "the protector intercepts every transient or that the device is effective."
                    ),
                )
            )
    if pcb_track_width_coverage is not None:
        for entry in pcb_track_width_coverage.entries:
            below = tuple(item for item in entry.tracks if item.below_minimum)
            if entry.status == "COMPLETE" and not below:
                continue
            found.append(
                PcbTrackWidthCandidate.from_source_evidence(
                    PcbTrackWidthFindingEvidence(
                        report=pcb_track_width_coverage,
                        entry=entry,
                    ),
                    subject=(
                        f"{entry.id}: all native track items"
                        if entry.net == "*"
                        else f"{entry.id}: net {entry.net}"
                    ),
                    message=(
                        "Review the mapped PCB track widths against the project's explicit "
                        "track-width "
                        "screen. This measurement does not calculate current capacity or "
                        "temperature rise."
                    ),
                )
            )
    if pcb_reference_plane_coverage is not None:
        for entry in pcb_reference_plane_coverage.entries:
            if entry.status == "COMPLETE" and not reference_plane_below_threshold_track_uuids(
                entry
            ):
                continue
            source_evidence = PcbReferencePlaneFindingEvidence(
                report=pcb_reference_plane_coverage,
                entry=entry,
            )
            message = (
                "Review the mapped signal-track centerline coverage over immediately "
                "adjacent filled reference copper. This geometric screen can highlight "
                "possible plane interruptions, but it does not establish a continuous "
                "return-current path or assess the electrical effect."
            )
            if source_evidence.endpoint_via_hole_candidates:
                message += (
                    " The native contours place mapped endpoint signal-via centers inside "
                    "reference-zone holes, but do not identify which clearance created a hole "
                    "when clearances merge. Those intervals remain uncovered; inspect the "
                    "geometry before interpreting them as a return-path interruption."
                )
            if entry.review_excluded_short_tracks and entry.excluded_short_track_uuids:
                message += (
                    " Short segments below the configured minimum were excluded and are included "
                    "in this review because the project requested coverage review."
                )
            found.append(
                PcbReferencePlaneCandidate.from_source_evidence(
                    source_evidence,
                    subject=(
                        f"{entry.id}: {entry.signal_net} over "
                        f"{', '.join(entry.signal_layers)} / {entry.reference_net}"
                    ),
                    message=message,
                )
            )
        found.extend(alternate_reference_plane_run_candidates(pcb_reference_plane_coverage))
        found.extend(unanchored_reference_zone_island_candidates(pcb_reference_plane_coverage))
    if pcb_thermal_via_coverage is not None:
        for entry in pcb_thermal_via_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            found.append(
                PcbThermalViaCandidate.from_source_evidence(
                    PcbThermalViaFindingEvidence(
                        report=pcb_thermal_via_coverage,
                        entry=entry,
                    ),
                    subject=f"{entry.id}: thermal pad {entry.pad}",
                    message=(
                        "Review native-connected via count and via-center distance for the exact "
                        "mapped thermal pad and copper-layer spans. This is a project-authored "
                        "geometry/connectivity screen; it does not estimate temperature or establish "
                        "thermal adequacy."
                    ),
                )
            )
    return tuple(found)
