"""Deterministic board-level fiducial counts against authored requirements."""

from __future__ import annotations

from typing import cast

from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence, map_sha256
from .model_primitives import Digest
from .pcb_fiducial_models import (
    PcbFiducialCoverageEntry,
    PcbFiducialCoverageReport,
    PcbFiducialMap,
    PcbFiducialMode,
    PcbFiducialObservation,
    PcbFiducialSnapshotSchema,
)


def _side_matches(requested: str, observed: str) -> bool:
    if requested == "either":
        return True
    return (requested == "front" and observed == "F.Cu") or (
        requested == "back" and observed == "B.Cu"
    )


def pcb_fiducial_entries(
    requirements: PcbFiducialMap,
    evidence: PcbGeometrySourceEvidence,
) -> tuple[PcbFiducialCoverageEntry, ...]:
    """Count fitted exact-footprint placements on each authored board side."""
    footprints = evidence.snapshot.footprints
    entries: list[PcbFiducialCoverageEntry] = []
    for requirement in requirements.requirements:
        accepted = {item.strip().casefold() for item in requirement.accepted_footprints}
        observations = tuple(
            sorted(
                (
                    PcbFiducialObservation(
                        reference=item.reference,
                        footprint=item.footprint,
                        side=item.side,
                        position_nm=item.position_nm,
                    )
                    for item in footprints
                    if not item.dnp
                    and item.footprint.casefold() in accepted
                    and _side_matches(requirement.side, item.side)
                ),
                key=lambda item: (item.reference.casefold(), item.reference),
            )
        )
        count = len(observations)
        issues = (
            ()
            if count >= requirement.minimum_count
            else (
                (
                    f"Found {count} fitted board fiducial footprints; "
                    f"{requirement.minimum_count} required"
                ),
            )
        )
        entries.append(
            PcbFiducialCoverageEntry(
                id=requirement.id,
                status="COMPLETE" if not issues else "INCOMPLETE",
                basis=requirement.basis,
                minimum_count=requirement.minimum_count,
                accepted_footprints=requirement.accepted_footprints,
                side=requirement.side,
                observed_count=count,
                observations=observations,
                issues=issues,
            )
        )
    return tuple(entries)


def evaluate_pcb_fiducials(
    requirements: PcbFiducialMap,
    mode: PcbFiducialMode,
    evidence: PcbGeometrySourceEvidence,
    netlist_sha256: Digest,
) -> PcbFiducialCoverageReport:
    """Bind authored fiducial counts to the verified native PCB snapshot."""
    if mode == "off":
        return PcbFiducialCoverageReport(status="DISABLED", mode=mode)
    if evidence.snapshot.schema_version not in {"12", "13", "14", "15", "16", "17", "18", "19"}:
        return PcbFiducialCoverageReport(
            status="BLOCKED",
            mode=mode,
            map_sha256=map_sha256(requirements),
            board_path=evidence.board_path,
            board_sha256=evidence.board_sha256,
            snapshot_path=evidence.snapshot_relative_path,
            snapshot_sha256=evidence.snapshot_sha256,
            kicad_version=evidence.snapshot.kicad_version,
            image=evidence.snapshot.image,
            probe_sha256=evidence.probe_sha256,
            netlist_sha256=netlist_sha256,
            issue=(
                "Native PCB snapshot predates the schema 12 footprint placement inventory; "
                "fiducial count is unavailable"
            ),
        )
    entries = pcb_fiducial_entries(requirements, evidence)
    return PcbFiducialCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode=mode,
        map_sha256=map_sha256(requirements),
        board_path=evidence.board_path,
        board_sha256=evidence.board_sha256,
        snapshot_path=evidence.snapshot_relative_path,
        snapshot_sha256=evidence.snapshot_sha256,
        snapshot_schema=cast(PcbFiducialSnapshotSchema, evidence.snapshot.schema_version),
        kicad_version=evidence.snapshot.kicad_version,
        image=evidence.snapshot.image,
        probe_sha256=evidence.probe_sha256,
        netlist_sha256=netlist_sha256,
        entries=entries,
    )
