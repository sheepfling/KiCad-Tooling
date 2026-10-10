"""Theme-specific candidate translators for PCB measurements and rule coverage."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import (
    PcbProtectionPathCoverageReport,
)
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_track_width_models import PcbTrackWidthCoverageReport


def pcb_measurement_coverage_candidates(
    *,
    pcb_decoupling_coverage: PcbDecouplingCoverageReport | None = None,
    pcb_protection_path_coverage: PcbProtectionPathCoverageReport | None = None,
    pcb_track_width_coverage: PcbTrackWidthCoverageReport | None = None,
    pcb_reference_plane_coverage: PcbReferencePlaneCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Translate PCB measurement coverage gaps into review candidates."""
    found: list[Candidate] = []
    if pcb_decoupling_coverage is not None:
        for entry in pcb_decoupling_coverage.entries:
            if entry.status == "COMPLETE" and entry.max_distance_um is not None:
                continue
            measured: list[str] = []
            for candidate in entry.candidates:
                distance = (
                    "unavailable"
                    if candidate.distance_nm is None
                    else f"{candidate.distance_nm // 1000}.{candidate.distance_nm % 1000:03d} um"
                )
                via_distance = (
                    "unavailable"
                    if candidate.return_via_distance_nm is None
                    else f"{candidate.return_via_distance_nm // 1000}.{candidate.return_via_distance_nm % 1000:03d} um"
                )
                via_id = candidate.nearest_return_via_id or "unavailable"
                state = "eligible" if candidate.eligible else "not eligible"
                measured.append(
                    f"{candidate.reference}: supply-pad distance {distance}; "
                    f"connected return vias {candidate.connected_return_via_count}; "
                    f"nearest return via {via_id} at {via_distance}; {state}"
                )
            found.append(
                Candidate(
                    rule_id="pcb.decoupling_proximity",
                    subject=f"{entry.id}: IC supply {entry.ic_supply_pad}",
                    message=(
                        "Review the mapped decoupling capacitor placement and copper paths. "
                        "The supply-pad and optional connected return-via distances are geometric "
                        "screens; they do not estimate loop inductance or prove adequate decoupling."
                    ),
                    evidence={
                        "ic_supply_pad": (entry.ic_supply_pad,),
                        "ic_return_pad": (entry.ic_return_pad,),
                        "supply_net": (entry.ic_supply_net,),
                        "return_net": (entry.ic_return_net,),
                        "selection": (entry.selection,),
                        "maximum_center_distance_um": (
                            "not configured"
                            if entry.max_distance_um is None
                            else str(entry.max_distance_um),
                        ),
                        "maximum_return_via_distance_um": (
                            "not configured"
                            if entry.max_return_via_distance_um is None
                            else str(entry.max_return_via_distance_um),
                        ),
                        "selected_capacitors": entry.selected_capacitors,
                        "candidate_distances": tuple(measured),
                        "issues": entry.issues
                        + tuple(
                            issue for candidate in entry.candidates for issue in candidate.issues
                        ),
                        "distance_basis": (
                            "Euclidean distance between native IC supply-pad center and native capacitor supply-pad center",
                        ),
                        "return_via_distance_basis": (
                            "Euclidean distance from the native capacitor return-pad center to a via listed in that pad's native copper-connectivity component",
                        ),
                    },
                )
            )
    if pcb_protection_path_coverage is not None:
        for entry in pcb_protection_path_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            entry_distance = (
                "unavailable"
                if entry.connector_to_protection_distance_nm is None
                else f"{entry.connector_to_protection_distance_nm} nm"
            )
            nearest_via_distance = (
                "unavailable"
                if entry.nearest_reference_via_distance_nm is None
                else f"{entry.nearest_reference_via_distance_nm} nm"
            )
            via_count = (
                "not configured"
                if entry.reference_vias_within_radius is None
                else f"{entry.reference_vias_within_radius} within {entry.reference_via_radius_um} um"
            )
            found.append(
                Candidate(
                    rule_id="pcb.protection_entry_path",
                    subject=(
                        f"{entry.id}: {entry.connector_signal_pad} to {entry.protection_signal_pad}"
                    ),
                    message=(
                        "Review the mapped connector-to-protection pad path and reference-via "
                        "coverage against the project limits. Pad-center distance is a straight-line "
                        "screen, not routed copper length; native connectivity does not prove that "
                        "the protector intercepts every transient or that the device is effective."
                    ),
                    evidence={
                        "connector_signal_pad": (entry.connector_signal_pad,),
                        "protection_signal_pad": (entry.protection_signal_pad,),
                        "protection_reference_pad": (entry.protection_reference_pad,),
                        "signal_net": (entry.signal_net,),
                        "reference_net": (entry.reference_net,),
                        "connector_footprint": (
                            entry.expected_connector_footprint,
                            entry.observed_connector_footprint or "missing",
                        ),
                        "protection_footprint": (
                            entry.expected_protection_footprint,
                            entry.observed_protection_signal_footprint or "missing",
                            entry.observed_protection_reference_footprint or "missing",
                        ),
                        "observed_pad_nets": (
                            f"{entry.connector_signal_pad}={entry.observed_connector_signal_net or 'unconnected'}",
                            f"{entry.protection_signal_pad}={entry.observed_protection_signal_net or 'unconnected'}",
                            f"{entry.protection_reference_pad}={entry.observed_protection_reference_net or 'unconnected'}",
                        ),
                        "native_signal_path_connected": (
                            "yes" if entry.native_signal_path_connected else "no",
                        ),
                        "connector_to_protection_pad_center_distance": (entry_distance,),
                        "maximum_project_distance_um": (
                            "not configured"
                            if entry.max_entry_distance_um is None
                            else str(entry.max_entry_distance_um),
                        ),
                        "native_connected_reference_vias": (
                            str(entry.connected_reference_via_count),
                        ),
                        "reference_vias_within_project_radius": (via_count,),
                        "nearest_connected_reference_via_distance": (nearest_via_distance,),
                        "minimum_vias_in_project_radius": (
                            "not configured"
                            if entry.minimum_reference_vias is None
                            else str(entry.minimum_reference_vias),
                        ),
                        "issues": entry.issues,
                    },
                )
            )
    if pcb_track_width_coverage is not None:
        for entry in pcb_track_width_coverage.entries:
            below = tuple(item for item in entry.tracks if item.below_minimum)
            if entry.status == "COMPLETE" and not below:
                continue
            measured_tracks = tuple(
                f"{item.track_uuid} {item.layer}: "
                f"{item.width_nm // 1000}.{item.width_nm % 1000:03d} um; "
                f"minimum {item.minimum_width_um} um; "
                f"start {item.start_nm[0]},{item.start_nm[1]} nm; "
                f"end {item.end_nm[0]},{item.end_nm[1]} nm"
                for item in entry.tracks
            )
            found.append(
                Candidate(
                    rule_id="pcb.minimum_track_width",
                    subject=f"{entry.id}: net {entry.net}",
                    message=(
                        "Review the mapped PCB track widths against the project's explicit net "
                        "screen. This measurement does not calculate current capacity or "
                        "temperature rise."
                    ),
                    evidence={
                        "net": (entry.net,),
                        "minimum_track_width_um": (str(entry.minimum_width_um),),
                        "measured_tracks": measured_tracks,
                        "below_minimum_track_uuids": tuple(item.track_uuid for item in below),
                        "coverage_status": (entry.status,),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                        "metric": (
                            "KiCad native track item GetWidth in integer nanometers compared "
                            + "with the project-authored minimum",
                        ),
                    },
                )
            )
    if pcb_reference_plane_coverage is not None:
        for entry in pcb_reference_plane_coverage.entries:
            by_track: dict[str, list[bool]] = {}
            for item in entry.tracks:
                by_track.setdefault(item.track_uuid, []).append(item.below_minimum)
            below_track_uuids = tuple(
                sorted(
                    (track_uuid for track_uuid, layers in by_track.items() if all(layers)),
                    key=str.casefold,
                )
            )
            if entry.status == "COMPLETE" and not below_track_uuids:
                continue
            measurements = tuple(
                f"{item.track_uuid}: {item.signal_layer} over {item.reference_layer}; "
                f"covered {item.covered_fraction_numerator}/"
                f"{item.covered_fraction_denominator}; "
                f"minimum {entry.minimum_referenced_fraction}; "
                f"zones {', '.join(item.reference_zone_uuids) or 'none'}; "
                f"endpoint vias {', '.join(item.endpoint_via_ids) or 'none'}; "
                "endpoint via centers in reference holes "
                f"{', '.join(item.endpoint_via_ids_with_center_in_reference_holes) or 'none'}"
                for item in entry.tracks
            )
            endpoint_via_hole_candidates = tuple(
                sorted(
                    {
                        via_id
                        for item in entry.tracks
                        if item.track_uuid in below_track_uuids
                        for via_id in item.endpoint_via_ids_with_center_in_reference_holes
                    },
                    key=str.casefold,
                )
            )
            message = (
                "Review the mapped signal-track centerline coverage over immediately "
                "adjacent filled reference copper. This geometric screen can highlight "
                "possible plane interruptions, but it does not establish a continuous "
                "return-current path or assess the electrical effect."
            )
            if endpoint_via_hole_candidates:
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
                Candidate(
                    rule_id="pcb.reference_plane_coverage",
                    subject=(
                        f"{entry.id}: {entry.signal_net} over "
                        f"{', '.join(entry.signal_layers)} / {entry.reference_net}"
                    ),
                    message=message,
                    evidence={
                        "signal_net": (entry.signal_net,),
                        "signal_layers": entry.signal_layers,
                        "reference_net": (entry.reference_net,),
                        "minimum_track_length_um": (str(entry.minimum_track_length_um),),
                        "minimum_referenced_fraction": (str(entry.minimum_referenced_fraction),),
                        "review_excluded_short_tracks": (
                            str(entry.review_excluded_short_tracks).lower(),
                        ),
                        "measured_tracks": measurements,
                        "below_threshold_track_uuids": below_track_uuids,
                        "endpoint_via_hole_candidates": endpoint_via_hole_candidates,
                        "excluded_short_track_uuids": entry.excluded_short_track_uuids,
                        "coverage_status": (entry.status,),
                        "basis": (entry.basis,),
                        "issues": entry.issues,
                        "metric": (
                            "Exact rational share of each native straight-track centerline "
                            + "inside the union of filled same-net zones on each immediately "
                            "adjacent copper layer, measured independently per layer",
                        ),
                    },
                )
            )
    return tuple(found)
