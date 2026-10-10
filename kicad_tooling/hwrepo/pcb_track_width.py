"""Deterministic review of project-mapped native PCB track widths."""

from __future__ import annotations

from .models import (
    PcbConnectivitySnapshot,
)
from .pcb_track_width_models import (
    PcbTrackWidthCoverageEntry,
    PcbTrackWidthMap,
    PcbTrackWidthMeasurement,
)


def pcb_track_width_entries(
    specification: PcbTrackWidthMap,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbTrackWidthCoverageEntry, ...]:
    """Compare exact native track-item widths with authored per-net screens."""
    entries: list[PcbTrackWidthCoverageEntry] = []
    for requirement in specification.requirements:
        observed = sorted(
            (
                item
                for item in snapshot.tracks
                if item.net is not None and item.net.casefold() == requirement.net.casefold()
            ),
            key=lambda item: item.uuid.casefold(),
        )
        tracks = tuple(
            PcbTrackWidthMeasurement(
                track_uuid=item.uuid,
                layer=item.layer,
                width_nm=item.width_nm,
                minimum_width_um=requirement.minimum_width_um,
                start_nm=item.start_nm,
                end_nm=item.end_nm,
                below_minimum=item.width_nm < requirement.minimum_width_um * 1000,
            )
            for item in observed
        )
        issues = (
            ()
            if tracks
            else (
                f"No native track items were observed on mapped net {requirement.net}; "
                + "the route may be zone-only or outside this track-width screen",
            )
        )
        entries.append(
            PcbTrackWidthCoverageEntry(
                id=requirement.id,
                status="COMPLETE" if tracks else "INCOMPLETE",
                basis=requirement.basis,
                net=requirement.net,
                minimum_width_um=requirement.minimum_width_um,
                tracks=tracks,
                issues=issues,
            )
        )
    return tuple(entries)
