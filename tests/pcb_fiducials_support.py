"""Minimal native-shape inputs for board-fiducial lint regressions."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from kicad_tooling.hwrepo.pcb_connectivity_observations import PcbFootprintPlacementObservation
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_fiducial_models import (
    PcbFiducialMap,
    PcbFiducialRequirement,
    PcbFiducialSide,
)

BOARD_PATH = "synthetic/controller.kicad_pcb"
BOARD_SHA256 = "b" * 64
NETLIST_SHA256 = "a" * 64
SNAPSHOT_SHA256 = "c" * 64
PROBE_SHA256 = "d" * 64
IMAGE = "registry.example/kicad:10.0.5@sha256:" + "e" * 64
FIDUCIAL_FOOTPRINT = "Synthetic:Fiducial_1mm_Mask2mm"


def requirement_map(*, minimum: int = 2, side: PcbFiducialSide = "front") -> PcbFiducialMap:
    return PcbFiducialMap(
        requirements=(
            PcbFiducialRequirement(
                id="board-fiducials",
                basis="Synthetic regression threshold; not assembly guidance",
                minimum_count=minimum,
                accepted_footprints=(FIDUCIAL_FOOTPRINT,),
                side=side,
            ),
        )
    )


def snapshot(
    rows: tuple[tuple[str, str, bool, str], ...] | None = None,
) -> PcbConnectivitySnapshot:
    """Build one schema-15 footprint inventory with no unrelated copper evidence."""
    if rows is None:
        rows = (
            ("FID1", FIDUCIAL_FOOTPRINT, False, "F.Cu"),
            ("FID2", FIDUCIAL_FOOTPRINT, False, "B.Cu"),
            ("FID3", FIDUCIAL_FOOTPRINT, True, "F.Cu"),
            ("H1", "Synthetic:MountingHole", False, "F.Cu"),
        )
    return PcbConnectivitySnapshot(
        schema_version="15",
        board_sha256=BOARD_SHA256,
        kicad_version="10.0.5",
        image=IMAGE,
        probe_sha256=PROBE_SHA256,
        zones_refilled=True,
        pads=(),
        net_ties=(),
        zones=(),
        vias=(),
        access_probe_observations=(),
        access_probe_requests_sha256=None,
        tracks=(),
        copper_layers=("F.Cu", "B.Cu"),
        rule_areas=(),
        footprints=tuple(
            PcbFootprintPlacementObservation(
                reference=reference,
                footprint=footprint,
                dnp=dnp,
                value="synthetic",
                position_nm=(index * 1_000_000, index * 2_000_000),
                orientation_microdegrees=0,
                side=side,
            )
            for index, (reference, footprint, dnp, side) in enumerate(rows)
        ),
        touch_pad_clearance_observations=(),
        touch_pad_clearance_requests_sha256=None,
    )


def source_evidence(board: PcbConnectivitySnapshot | None = None) -> PcbGeometrySourceEvidence:
    observed = snapshot() if board is None else board
    return PcbGeometrySourceEvidence(
        board_path=BOARD_PATH,
        board_sha256=BOARD_SHA256,
        snapshot_relative_path="build/design-lint/fiducials/snapshot.json",
        snapshot_path=Path("build/design-lint/fiducials/snapshot.json"),
        snapshot_sha256=SNAPSHOT_SHA256,
        probe_sha256=PROBE_SHA256,
        snapshot=observed,
        command=CommandEvidence(
            argv=("synthetic-native-probe",),
            started_utc="2026-11-10T00:00:00Z",
            returncode=0,
        ),
        command_path=Path("build/design-lint/fiducials/native.command.json"),
        command_sha256="f" * 64,
    )
