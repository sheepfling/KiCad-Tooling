"""Canonical typed-finding construction and fingerprints for fabrication analysis."""

from __future__ import annotations

import hashlib
import json

from .fabrication_connectivity_models import (
    FabricationConnectivityDrillEvidence,
    FabricationConnectivityFinding,
    FabricationConnectivityLandCoverageEvidence,
)


def finding_fingerprint(
    code: str,
    net: str | None,
    contacts: tuple[str, ...],
    drill_evidence: FabricationConnectivityDrillEvidence | None = None,
    raster_phase: str | None = None,
    raster_density: int | None = None,
    missing_layers: tuple[str, ...] = (),
    identity_location_mm: tuple[float, float] | None = None,
    land_coverage_evidence: FabricationConnectivityLandCoverageEvidence | None = None,
) -> str:
    """Hash stable source and artifact evidence fields for one finding."""
    payload: dict[str, object] = {"code": code, "net": net, "contacts": sorted(contacts)}
    if drill_evidence is not None:
        payload["drill_evidence"] = drill_evidence.model_dump(mode="json")
    if raster_phase is not None:
        payload["raster_phase"] = raster_phase
    if raster_density is not None:
        payload["raster_density"] = raster_density
    if land_coverage_evidence is not None:
        payload["land_coverage_evidence"] = land_coverage_evidence.model_dump(mode="json")
    if missing_layers:
        payload["missing_layers"] = sorted(missing_layers)
    if (
        code
        in {
            "SOURCE_LAND_FLASH_MISSING",
            "SOURCE_LAND_GEOMETRY_UNREVIEWED",
        }
        and identity_location_mm is not None
    ):
        payload["land_location_nm"] = [round(value * 1_000_000) for value in identity_location_mm]
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def make_connectivity_finding(
    code: str,
    contact_labels: tuple[str, ...],
    net: str | None = None,
    location: tuple[float, float] | None = None,
    drill_evidence: FabricationConnectivityDrillEvidence | None = None,
    raster_phase: str | None = None,
    raster_density: int | None = None,
    missing_layers: tuple[str, ...] = (),
    land_coverage_evidence: FabricationConnectivityLandCoverageEvidence | None = None,
) -> FabricationConnectivityFinding:
    """Create one normalized typed observation using its canonical identity."""
    contacts = tuple(sorted(contact_labels))
    return FabricationConnectivityFinding(
        code=code,  # type: ignore[arg-type]
        fingerprint=finding_fingerprint(
            code,
            net,
            contacts,
            drill_evidence,
            raster_phase,
            raster_density,
            missing_layers,
            location,
            land_coverage_evidence,
        ),
        net=net,
        contacts=contacts,
        location_mm=location,
        drill_evidence=drill_evidence,
        land_coverage_evidence=land_coverage_evidence,
        raster_phase=raster_phase,  # type: ignore[arg-type]
        raster_density=raster_density,  # type: ignore[arg-type]
        missing_layers=missing_layers,
    )
