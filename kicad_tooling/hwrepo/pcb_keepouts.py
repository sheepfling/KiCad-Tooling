"""Compare project-reviewed keepout signatures with native PCB rule areas."""

from __future__ import annotations

import hashlib
import json

from .models import (
    PcbConnectivitySnapshot,
    PcbKeepoutCoverageEntry,
    PcbKeepoutMap,
    PcbRuleAreaObservation,
)


def pcb_rule_area_geometry_sha256(area: PcbRuleAreaObservation) -> str:
    """Hash canonical native polygon outlines and holes, independent of item order."""
    polygons = [
        {
            "outline_nm": [list(point) for point in polygon.outline_nm],
            "holes_nm": sorted([list(point) for point in hole] for hole in polygon.holes_nm),
        }
        for polygon in area.polygons
    ]
    polygons.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    payload = json.dumps(polygons, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def pcb_keepout_entries(
    mapping: PcbKeepoutMap, snapshot: PcbConnectivitySnapshot
) -> tuple[PcbKeepoutCoverageEntry, ...]:
    """Match every named, reviewed keepout to one exact native geometry and policy record."""
    areas_by_name: dict[str, list[PcbRuleAreaObservation]] = {}
    for area in snapshot.rule_areas:
        areas_by_name.setdefault(area.name.casefold(), []).append(area)

    entries: list[PcbKeepoutCoverageEntry] = []
    for requirement in mapping.requirements:
        issues: list[str] = []
        area: PcbRuleAreaObservation | None = None
        matches = areas_by_name.get(requirement.name.casefold(), [])
        if snapshot.schema_version not in {"11", "12"}:
            issues.append("Native PCB snapshot schema 11 or newer rule-area evidence is required")
        elif not matches:
            issues.append(f"No native rule area is named {requirement.name!r}")
        elif len(matches) > 1:
            identities = ", ".join(sorted(item.uuid for item in matches))
            issues.append(
                f"Rule-area name {requirement.name!r} is ambiguous across UUIDs: {identities}"
            )
        else:
            area = matches[0]

        observed_geometry_sha256 = None if area is None else pcb_rule_area_geometry_sha256(area)
        observed_layers = () if area is None else area.layers
        if area is not None:
            if observed_geometry_sha256 != requirement.geometry_sha256:
                issues.append(
                    "Native rule-area polygon geometry differs from the reviewed signature"
                )
            if {item.casefold() for item in observed_layers} != {
                item.casefold() for item in requirement.layers
            }:
                issues.append(
                    "Native rule-area copper layers differ: expected "
                    f"{sorted(requirement.layers, key=str.casefold)}, observed "
                    f"{sorted(observed_layers, key=str.casefold)}"
                )
            for label, expected, observed in (
                ("tracks", requirement.forbids_tracks, area.forbids_tracks),
                ("vias", requirement.forbids_vias, area.forbids_vias),
                ("pads", requirement.forbids_pads, area.forbids_pads),
                ("zone fills", requirement.forbids_zone_fills, area.forbids_zone_fills),
                ("footprints", requirement.forbids_footprints, area.forbids_footprints),
            ):
                if observed != expected:
                    issues.append(
                        f"Native rule-area restriction for {label} is {observed}; expected {expected}"
                    )

        entries.append(
            PcbKeepoutCoverageEntry(
                id=requirement.id,
                basis=requirement.basis,
                name=requirement.name,
                expected_geometry_sha256=requirement.geometry_sha256,
                observed_uuid=None if area is None else area.uuid,
                observed_geometry_sha256=observed_geometry_sha256,
                expected_layers=requirement.layers,
                observed_layers=observed_layers,
                expected_forbids_tracks=requirement.forbids_tracks,
                expected_forbids_vias=requirement.forbids_vias,
                expected_forbids_pads=requirement.forbids_pads,
                expected_forbids_zone_fills=requirement.forbids_zone_fills,
                expected_forbids_footprints=requirement.forbids_footprints,
                observed_forbids_tracks=None if area is None else area.forbids_tracks,
                observed_forbids_vias=None if area is None else area.forbids_vias,
                observed_forbids_pads=None if area is None else area.forbids_pads,
                observed_forbids_zone_fills=None if area is None else area.forbids_zone_fills,
                observed_forbids_footprints=None if area is None else area.forbids_footprints,
                status="COMPLETE" if not issues else "INCOMPLETE",
                issues=tuple(issues),
            )
        )
    return tuple(entries)
