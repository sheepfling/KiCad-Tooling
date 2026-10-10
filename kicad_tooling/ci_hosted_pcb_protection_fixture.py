"""Native connector-entry and connected-reference-via regression fixtures."""

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
from .hwrepo.models import PcbProtectionPathMap, PcbProtectionPathRequirement
from .hwrepo.pcb_protection_path import pcb_protection_path_entries

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def protection_path_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Check mapped connector protection geometry and disconnected-via fault cases."""
    context = prepare_pcb_fixture(
        root,
        project=project,
        image=image,
        log=log,
        lane="PCB protection-path",
        scratch_prefix="pcb-protection",
    )
    root = context.root
    config = context.config
    source = context.fixture_root / "pcb-protection-entry-path.kicad_pcb"
    relative_project = context.scratch.relative_to(root) / "protection.kicad_pro"
    protection_board = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(source, protection_board)
    source_hash = digest(protection_board)
    fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
    requirement = PcbProtectionPathRequirement(
        id="synthetic-data-protection",
        connector_reference="J1",
        connector_footprint="Synthetic:Conn1",
        connector_signal_pad="J1.1",
        protection_reference="D1",
        protection_footprint="Synthetic:TVS",
        protection_signal_pad="D1.1",
        protection_reference_pad="D1.2",
        signal_net="DATA",
        reference_net="GND",
        max_entry_distance_um=650,
        minimum_reference_vias=1,
        reference_via_radius_um=2000,
    )
    protection_map = PcbProtectionPathMap(
        basis="Synthetic native connector-to-protector pad and connected-via regression",
        requirements=(requirement,),
    )
    try:
        retained_snapshot = None
        for repeat in ("first", "repeat"):
            snapshot = capture_verified_pcb_snapshot(
                context,
                fixture_config,
                context.scratch / f"protection-{repeat}",
                expected_board_sha256=source_hash,
                purpose="PCB protection-path fixture",
            )
            entries = pcb_protection_path_entries(protection_map, snapshot)
            if (
                len(entries) != 1
                or entries[0].status != "COMPLETE"
                or not entries[0].native_signal_path_connected
                or entries[0].connector_to_protection_distance_nm != 650_000
                or entries[0].connected_reference_via_count != 1
                or entries[0].reference_vias_within_radius != 1
            ):
                raise ValueError(f"Native protection-path control changed: {entries}")
            distance_fault = pcb_protection_path_entries(
                protection_map.model_copy(
                    update={
                        "requirements": (
                            requirement.model_copy(update={"max_entry_distance_um": 649}),
                        )
                    }
                ),
                snapshot,
            )
            via_count_fault = pcb_protection_path_entries(
                protection_map.model_copy(
                    update={
                        "requirements": (
                            requirement.model_copy(update={"minimum_reference_vias": 2}),
                        )
                    }
                ),
                snapshot,
            )
            if (
                distance_fault[0].status != "INCOMPLETE"
                or via_count_fault[0].status != "INCOMPLETE"
            ):
                raise ValueError("Native protection-path distance/via fault controls were missed")
            if retained_snapshot is None:
                retained_snapshot = snapshot
            elif retained_snapshot != snapshot:
                raise ValueError("Repeated native protection evidence changed for identical input")

        protection_fixture_text = protection_board.read_text(encoding="utf-8")
        reference_via = (
            '  (via (at 10.65 11) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 2)\n'
            '    (uuid "00000000-0000-0000-0000-000000000003"))\n'
        )
        if protection_fixture_text.count(reference_via) != 1:
            raise ValueError("Native protection fixture lost its unique reference-via item")
        open_via_project = relative_project.with_name("protection-nearby-open-via.kicad_pro")
        open_via_board = root / open_via_project.with_suffix(".kicad_pcb")
        open_via_board.write_text(
            protection_fixture_text.replace(
                reference_via,
                reference_via.replace("(at 10.65 11)", "(at 10.65 12.5)"),
                1,
            ),
            encoding="utf-8",
        )
        open_via_hash = digest(open_via_board)
        open_via_config = config.model_copy(update={"project": open_via_project.as_posix()})
        retained_open_via_snapshot = None
        for repeat in ("first", "repeat"):
            open_snapshot = capture_verified_pcb_snapshot(
                context,
                open_via_config,
                context.scratch / f"protection-nearby-open-via-{repeat}",
                expected_board_sha256=open_via_hash,
                purpose="nearby disconnected reference-via fixture",
            )
            entries = pcb_protection_path_entries(protection_map, open_snapshot)
            open_vias = tuple(
                item
                for item in open_snapshot.vias
                if item.net == "GND" and item.x_nm == 10_650_000 and item.y_nm == 12_500_000
            )
            reference_pad = next(
                (item for item in open_snapshot.pads if item.pad.casefold() == "d1.2"),
                None,
            )
            if (
                len(entries) != 1
                or entries[0].status != "INCOMPLETE"
                or not entries[0].native_signal_path_connected
                or entries[0].connected_reference_via_count != 0
                or entries[0].reference_vias_within_radius != 0
                or len(open_vias) != 1
                or reference_pad is None
                or reference_pad.connected_vias
                or min(
                    (x - open_vias[0].x_nm) ** 2 + (y - open_vias[0].y_nm) ** 2
                    for x, y in reference_pad.positions_nm
                )
                != 1_500_000**2
            ):
                raise ValueError(
                    "Native nearby but disconnected reference via was not rejected: "
                    f"entries={entries}, vias={open_vias}, pad={reference_pad}"
                )
            if retained_open_via_snapshot is None:
                retained_open_via_snapshot = open_snapshot
            elif retained_open_via_snapshot != open_snapshot:
                raise ValueError("Repeated nearby-open-via evidence changed for identical input")

        signal_segment = (
            '  (segment (start 10 10) (end 10.65 10) (width 0.25) (layer "F.Cu") (net 1)\n'
            '    (uuid "00000000-0000-0000-0000-000000000001"))\n'
        )
        if protection_fixture_text.count(signal_segment) != 1:
            raise ValueError("Native protection fixture lost its unique signal segment")
        disconnected_project = relative_project.with_name("protection-disconnected.kicad_pro")
        disconnected_board = root / disconnected_project.with_suffix(".kicad_pcb")
        disconnected_board.write_text(
            protection_fixture_text.replace(signal_segment, "", 1), encoding="utf-8"
        )
        disconnected_hash = digest(disconnected_board)
        disconnected_config = config.model_copy(update={"project": disconnected_project.as_posix()})
        disconnected_snapshot = capture_verified_pcb_snapshot(
            context,
            disconnected_config,
            context.scratch / "disconnected-protection-signal",
            expected_board_sha256=disconnected_hash,
            purpose="disconnected protection-signal fault fixture",
        )
        disconnected_entries = pcb_protection_path_entries(protection_map, disconnected_snapshot)
        if (
            len(disconnected_entries) != 1
            or disconnected_entries[0].status != "INCOMPLETE"
            or disconnected_entries[0].native_signal_path_connected
        ):
            raise ValueError(
                "Native disconnected connector-to-protector fault was missed: "
                f"{disconnected_entries}"
            )
        log.event(
            "pcb-protection-path-fixture/entry",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            connector_to_protector_distance_nm=650_000,
            connected_reference_vias=1,
            distance_fault_limit_um=649,
            via_count_fault_minimum=2,
            disconnected_signal_fault_sha256=disconnected_hash,
            disconnected_nearby_reference_via_fault_sha256=open_via_hash,
            nearby_reference_via_pad_distance_nm=1_500_000,
            nearby_reference_via_radius_um=2000,
            connected_vias_for_nearby_open_fault=0,
            repeatable="true",
            receipt=(context.scratch.relative_to(root) / "protection-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-protection-path-fixture/entry",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            error=str(exc),
        )
        raise HostedPcbFixtureFailure(str(exc)) from exc
