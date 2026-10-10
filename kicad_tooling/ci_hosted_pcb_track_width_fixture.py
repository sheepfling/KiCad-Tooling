"""Native exact-boundary and fault controls for mapped PCB track width."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_pcb_fixture_support import (
    HostedPcbFixtureFailure,
    capture_verified_pcb_snapshot,
    prepare_pcb_fixture,
)
from .hwrepo.evidence import digest
from .hwrepo.pcb_track_width import pcb_track_width_entries
from .hwrepo.pcb_track_width_models import PcbTrackWidthMap, PcbTrackWidthRequirement

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def track_width_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Check the authored width boundary and a one-micrometre fault control."""
    context = prepare_pcb_fixture(
        root,
        project=project,
        image=image,
        log=log,
        lane="PCB track-width",
        scratch_prefix="pcb-track-width",
    )
    root = context.root
    config = context.config
    source = context.fixture_root / "pcb-decoupling-placement.kicad_pcb"
    relative_project = context.scratch.relative_to(root) / "track-width.kicad_pro"
    board = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(source, board)
    source_hash = digest(board)
    fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
    boundary_map = PcbTrackWidthMap(
        basis="Synthetic exact-width boundary control",
        requirements=(
            PcbTrackWidthRequirement(
                id="vdd-boundary",
                basis="Synthetic 250 um boundary fixture",
                net="VDD",
                minimum_width_um=250,
            ),
        ),
    )
    fault_map = PcbTrackWidthMap(
        basis="Synthetic below-width fault control",
        requirements=(
            PcbTrackWidthRequirement(
                id="vdd-fault",
                basis="Synthetic 251 um threshold against a 250 um track",
                net="VDD",
                minimum_width_um=251,
            ),
        ),
    )
    try:
        retained_snapshot = None
        for repeat in ("first", "repeat"):
            snapshot = capture_verified_pcb_snapshot(
                context,
                fixture_config,
                context.scratch / f"receipt-{repeat}",
                expected_board_sha256=source_hash,
                purpose="PCB track-width fixture",
            )
            track_inventory = {item.net: item for item in snapshot.tracks}
            if set(track_inventory) != {"VDD", "GND", "DATA"} or any(
                item.width_nm != 250_000 or item.layer != "F.Cu"
                for item in track_inventory.values()
            ):
                raise ValueError(
                    "Native track inventory differs from the synthetic 250 um VDD/GND/DATA fixture"
                )
            boundary = pcb_track_width_entries(boundary_map, snapshot)
            fault = pcb_track_width_entries(fault_map, snapshot)
            if (
                len(boundary) != 1
                or boundary[0].status != "COMPLETE"
                or len(boundary[0].tracks) != 1
                or boundary[0].tracks[0].below_minimum
                or len(fault) != 1
                or fault[0].status != "COMPLETE"
                or len(fault[0].tracks) != 1
                or not fault[0].tracks[0].below_minimum
            ):
                raise ValueError("Native track-width fault/boundary controls changed")
            if retained_snapshot is None:
                retained_snapshot = snapshot
            elif retained_snapshot != snapshot:
                raise ValueError("Repeated native track inventory changed for identical input")
        log.event(
            "pcb-track-width-fixture/screen",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            measured_width_nm=250_000,
            boundary_minimum_um=250,
            fault_minimum_um=251,
            repeatable="true",
            receipt=(context.scratch.relative_to(root) / "receipt-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-track-width-fixture/screen",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            error=str(exc),
        )
        raise HostedPcbFixtureFailure(str(exc)) from exc
