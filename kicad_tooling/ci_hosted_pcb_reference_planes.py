"""Hosted native fixtures for PCB reference-plane lint themes."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.models import ProjectConfig

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def pcb_reference_plane_via_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify native via antipad contours and mapped reference-plane context."""
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.pcb_reference_plane_models import (
        PcbReferencePlaneMap,
        PcbReferencePlaneRequirement,
    )
    from .hwrepo.pcb_reference_planes import pcb_reference_plane_entries
    from .hwrepo.pcb_return_path_capture import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
    )

    root = root.resolve()
    config: ProjectConfig = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Reference-plane via fixtures do not cover KiCad {config.kicad_version}")
    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(
        tempfile.mkdtemp(prefix=f"pcb-reference-via-{project}-", dir=log.directory.resolve())
    )
    relative_project = scratch.relative_to(root) / "via-antipad.kicad_pro"
    board = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(fixture_root / "pcb-reference-via-antipad.kicad_pcb", board)
    source_hash = digest(board)
    fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
    fault_requirement: PcbReferencePlaneRequirement = PcbReferencePlaneRequirement(
        id="synthetic-data-via-antipad",
        basis="Synthetic native via clearance; 0.75 is only a fixture threshold",
        signal_net="DATA",
        signal_layers=("F.Cu",),
        reference_net="GND",
        minimum_track_length_um=1_000,
        minimum_referenced_fraction=0.75,
    )
    fault_map: PcbReferencePlaneMap = PcbReferencePlaneMap(
        basis="Synthetic native via-antipad fault control",
        requirements=(fault_requirement,),
    )
    control_map: PcbReferencePlaneMap = fault_map.model_copy(
        update={
            "requirements": (
                fault_requirement.model_copy(update={"minimum_referenced_fraction": 0.5}),
            )
        }
    )
    try:
        retained_snapshot = None
        retained_measurement: tuple[str, int, int, bool, tuple[str, ...]] | None = None
        for repeat in ("first", "repeat"):
            receipt = scratch / f"receipt-{repeat}"
            command, snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
            if command.returncode != 0 or command.error is not None:
                raise ValueError(
                    f"Native PCB reference-via fixture command failed: {command.stderr or command.error}"
                )
            if not native_pcb_command_matches(command, fixture_config):
                raise ValueError(
                    "Native reference-via fixture did not use the pinned read-only probe command"
                )
            if snapshot is None:
                raise ValueError("Native PCB reference-via fixture returned no snapshot")
            if (
                snapshot.schema_version not in {"10", "11", "12"}
                or snapshot.board_sha256 != source_hash
                or snapshot.kicad_version != config.kicad_version
                or snapshot.image != config.image
                or snapshot.probe_sha256 != expected_probe_sha256()
                or not snapshot.zones_refilled
                or snapshot.copper_layers[0].casefold() != "f.cu"
                or snapshot.copper_layers[-1].casefold() != "b.cu"
            ):
                raise ValueError(
                    "Native reference-via evidence is not bound to its source, tool, and copper stack"
                )
            data_tracks = tuple(
                track
                for track in snapshot.tracks
                if track.net is not None
                and track.net.casefold() == "data"
                and track.layer.casefold() == "f.cu"
            )
            data_vias = tuple(
                via for via in snapshot.vias if via.net is not None and via.net.casefold() == "data"
            )
            if len(data_tracks) != 1 or len(data_vias) != 1:
                raise ValueError(
                    "Native reference-via fixture must expose exactly one DATA segment and via"
                )
            track = data_tracks[0]
            via = data_vias[0]
            if (
                via.x_nm != 10_000_000
                or via.y_nm != 13_000_000
                or via.start_layer.casefold() != "f.cu"
                or via.end_layer.casefold() != "b.cu"
                or (via.x_nm, via.y_nm) not in {track.start_nm, track.end_nm}
                or via.id not in {*track.start_vias, *track.end_vias}
            ):
                raise ValueError(
                    "Native DATA track endpoint does not match the synthetic through-via"
                )
            reference_zones = tuple(
                zone
                for zone in snapshot.zones
                if zone.layer.casefold() == "in1.cu"
                and zone.net is not None
                and zone.net.casefold() == "gnd"
            )
            if len(reference_zones) != 1 or not any(
                island.holes_nm for island in reference_zones[0].filled_islands
            ):
                raise ValueError("Native GND reference zone did not retain a filled clearance hole")
            measured = pcb_reference_plane_entries(fault_map, snapshot)
            if (
                len(measured) != 1
                or measured[0].status != "COMPLETE"
                or len(measured[0].tracks) != 1
            ):
                raise ValueError(f"Native reference-via coverage is incomplete: {measured}")
            measurement = measured[0].tracks[0]
            if (
                measurement.track_uuid.casefold() != track.uuid.casefold()
                or not measurement.below_minimum
                or measurement.endpoint_via_ids != (via.id,)
                or measurement.endpoint_via_ids_with_center_in_reference_holes != (via.id,)
            ):
                raise ValueError(
                    "Native via center was not annotated as an uncovered reference-hole candidate"
                )
            control = pcb_reference_plane_entries(control_map, snapshot)
            if len(control) != 1 or control[0].tracks[0].below_minimum:
                raise ValueError("Native via-hole measurement did not pass its 0.5 control")
            measurement_value = (
                measurement.track_uuid,
                measurement.covered_fraction_numerator,
                measurement.covered_fraction_denominator,
                measurement.below_minimum,
                measurement.endpoint_via_ids_with_center_in_reference_holes,
            )
            if retained_snapshot is None:
                retained_snapshot = snapshot
                retained_measurement = measurement_value
            elif retained_snapshot != snapshot or retained_measurement != measurement_value:
                raise ValueError(
                    "Repeated native via-hole geometry changed for identical source and tool inputs"
                )
        if retained_measurement is None:
            raise ValueError("Native reference-via measurement was not retained")
        log.event(
            "pcb-reference-plane-fixture/via-antipad",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            covered_fraction=(f"{retained_measurement[1]}/{retained_measurement[2]}"),
            fault_threshold=0.75,
            control_threshold=0.5,
            endpoint_via_hole_candidate=retained_measurement[4][0],
            intervals_remain_uncovered="true",
            repeatable="true",
            receipt=(scratch.relative_to(root) / "receipt-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-reference-plane-fixture/via-antipad",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=source_hash,
            error=str(exc),
        )
        raise


def pcb_reference_plane_narrow_void_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Ensure exact native centerline geometry catches a void between coarse samples."""
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
    from .hwrepo.pcb_reference_plane_models import (
        PcbReferencePlaneMap,
        PcbReferencePlaneRequirement,
    )
    from .hwrepo.pcb_reference_planes import pcb_reference_plane_entries
    from .hwrepo.pcb_return_path_capture import (
        capture_native_pcb_connectivity,
        expected_probe_sha256,
        native_pcb_command_matches,
    )

    root = root.resolve()
    config: ProjectConfig = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Reference-plane narrow-void fixtures do not cover KiCad {config.kicad_version}"
        )
    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"pcb-reference-narrow-void-{project}-", dir=log.directory.resolve()
        )
    )
    requirement = PcbReferencePlaneRequirement(
        id="synthetic-data-narrow-reference-void",
        basis="Synthetic 0.2 mm mid-route void; 0.65 is only a fixture threshold",
        signal_net="DATA",
        signal_layers=("F.Cu",),
        reference_net="GND",
        minimum_track_length_um=1_000,
        minimum_referenced_fraction=0.65,
    )
    reference_map = PcbReferencePlaneMap(
        basis="Synthetic native narrow-void fault/control",
        requirements=(requirement,),
    )
    retained: dict[
        str, tuple[PcbConnectivitySnapshot, tuple[str, int, int, bool, tuple[str, ...]]]
    ] = {}
    source_hashes: dict[str, str] = {}
    try:
        for case in ("control", "fault"):
            relative_project = scratch.relative_to(root) / f"narrow-void-{case}.kicad_pro"
            board = root / relative_project.with_suffix(".kicad_pcb")
            shutil.copyfile(fixture_root / f"pcb-reference-narrow-void-{case}.kicad_pcb", board)
            source_hash = digest(board)
            source_hashes[case] = source_hash
            fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
            retained_snapshot: PcbConnectivitySnapshot | None = None
            retained_measurement: tuple[str, int, int, bool, tuple[str, ...]] | None = None
            for repeat in ("first", "repeat"):
                receipt = scratch / f"{case}-receipt-{repeat}"
                command, snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
                if command.returncode != 0 or command.error is not None:
                    raise ValueError(
                        f"Native reference-plane {case} command failed: "
                        f"{command.stderr or command.error}"
                    )
                if not native_pcb_command_matches(command, fixture_config):
                    raise ValueError(
                        f"Native reference-plane {case} did not use the pinned read-only probe"
                    )
                if snapshot is None:
                    raise ValueError(f"Native reference-plane {case} returned no snapshot")
                if (
                    snapshot.schema_version not in {"10", "11", "12"}
                    or snapshot.board_sha256 != source_hash
                    or snapshot.kicad_version != config.kicad_version
                    or snapshot.image != config.image
                    or snapshot.probe_sha256 != expected_probe_sha256()
                    or not snapshot.zones_refilled
                    or snapshot.copper_layers != ("F.Cu", "B.Cu")
                ):
                    raise ValueError(
                        f"Native reference-plane {case} evidence is not bound to source, tool, and two-layer stack"
                    )
                data_tracks = tuple(
                    track
                    for track in snapshot.tracks
                    if track.net is not None
                    and track.net.casefold() == "data"
                    and track.layer.casefold() == "f.cu"
                )
                data_vias = tuple(
                    via
                    for via in snapshot.vias
                    if via.net is not None and via.net.casefold() == "data"
                )
                if len(data_tracks) != 1 or len(data_vias) != 1:
                    raise ValueError(
                        f"Native reference-plane {case} must expose one DATA segment and via"
                    )
                track = data_tracks[0]
                via = data_vias[0]
                if (
                    (track.start_nm, track.end_nm)
                    != ((10_000_000, 13_000_000), (12_000_000, 13_000_000))
                    or via.x_nm != 10_000_000
                    or via.y_nm != 13_000_000
                    or (via.id not in {*track.start_vias, *track.end_vias})
                ):
                    raise ValueError(
                        f"Native reference-plane {case} lost its exact synthetic route"
                    )
                reference_zones = tuple(
                    zone
                    for zone in snapshot.zones
                    if zone.layer.casefold() == "b.cu"
                    and zone.net is not None
                    and zone.net.casefold() == "gnd"
                )
                if len(reference_zones) != 1 or not any(
                    island.holes_nm for island in reference_zones[0].filled_islands
                ):
                    raise ValueError(
                        f"Native reference-plane {case} did not retain the endpoint via clearance"
                    )
                entries = pcb_reference_plane_entries(reference_map, snapshot)
                if (
                    len(entries) != 1
                    or entries[0].status != "COMPLETE"
                    or len(entries[0].tracks) != 1
                ):
                    raise ValueError(
                        f"Native reference-plane {case} coverage is incomplete: {entries}"
                    )
                measurement = entries[0].tracks[0]
                expected_below = case == "fault"
                if (
                    measurement.track_uuid.casefold() != track.uuid.casefold()
                    or measurement.below_minimum != expected_below
                    or measurement.endpoint_via_ids != (via.id,)
                    or measurement.endpoint_via_ids_with_center_in_reference_holes != (via.id,)
                ):
                    raise ValueError(
                        f"Native reference-plane {case} did not match its threshold control"
                    )
                measurement_value = (
                    measurement.track_uuid,
                    measurement.covered_fraction_numerator,
                    measurement.covered_fraction_denominator,
                    measurement.below_minimum,
                    measurement.endpoint_via_ids_with_center_in_reference_holes,
                )
                if retained_snapshot is None:
                    retained_snapshot = snapshot
                    retained_measurement = measurement_value
                elif retained_snapshot != snapshot or retained_measurement != measurement_value:
                    raise ValueError(
                        f"Repeated native reference-plane {case} geometry changed for identical inputs"
                    )
            if retained_measurement is None:
                raise ValueError(f"Native reference-plane {case} evidence was not retained")
            retained[case] = (retained_snapshot, retained_measurement)

        control_snapshot, control_measurement = retained["control"]
        fault_snapshot, fault_measurement = retained["fault"]
        if control_snapshot.kicad_version != fault_snapshot.kicad_version:
            raise ValueError("Native reference-plane fault/control versions differ")
        log.event(
            "pcb-reference-plane-fixture/narrow-void",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            control_fixture_sha256=source_hashes["control"],
            fault_fixture_sha256=source_hashes["fault"],
            control_coverage=(f"{control_measurement[1]}/{control_measurement[2]}"),
            fault_coverage=(f"{fault_measurement[1]}/{fault_measurement[2]}"),
            minimum_fraction=requirement.minimum_referenced_fraction,
            control_below_threshold="false",
            fault_below_threshold="true",
            endpoint_via_hole_context="retained",
            repeatable="true",
            control_receipt=(scratch.relative_to(root) / "control-receipt-first").as_posix(),
            fault_receipt=(scratch.relative_to(root) / "fault-receipt-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-reference-plane-fixture/narrow-void",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            control_fixture_sha256=source_hashes.get("control", ""),
            fault_fixture_sha256=source_hashes.get("fault", ""),
            error=str(exc),
        )
        raise
