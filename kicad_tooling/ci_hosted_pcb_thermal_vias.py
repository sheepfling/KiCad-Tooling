"""Exact-version native fixtures for mapped thermal-pad via coverage."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .ci_hosted_support import HostedLog
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.pcb_return_path_capture import (
    capture_native_pcb_connectivity,
    expected_probe_sha256,
    native_pcb_command_matches,
)
from .hwrepo.pcb_thermal_via_models import (
    PcbThermalViaLayerRequirement,
    PcbThermalViaMap,
    PcbThermalViaRequirement,
)
from .hwrepo.pcb_thermal_vias import pcb_thermal_via_entries
from .hwrepo.project_models import ProjectConfig


def pcb_thermal_via_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Measure a synthetic pad/via fault and control twice with the pinned image."""
    root = root.resolve()
    config: ProjectConfig = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Thermal-via fixtures do not cover KiCad {config.kicad_version}")
    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(
        tempfile.mkdtemp(prefix=f"pcb-thermal-vias-{project}-", dir=log.directory.resolve())
    )
    relative_project = scratch.relative_to(root) / "thermal-via.kicad_pro"
    board = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(fixture_root / "pcb-thermal-via-pad.kicad_pcb", board)
    board_sha256 = digest(board)
    fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
    requirement = PcbThermalViaRequirement(
        id="synthetic-native-pad-vias",
        basis="Synthetic native regression threshold; not thermal guidance",
        pad="U1.1",
        footprint="Synthetic:QFN_Thermal",
        net="GND",
        maximum_center_distance_um=1_000,
        required_layer_spans=(
            PcbThermalViaLayerRequirement(
                start_layer="F.Cu",
                end_layer="B.Cu",
                minimum_vias=3,
            ),
        ),
    )
    fault_map = PcbThermalViaMap(
        basis="Synthetic native via-count fault/control",
        requirements=(requirement,),
    )
    control_map = fault_map.model_copy(
        update={
            "requirements": (
                requirement.model_copy(
                    update={
                        "required_layer_spans": (
                            PcbThermalViaLayerRequirement(
                                start_layer="F.Cu",
                                end_layer="B.Cu",
                                minimum_vias=2,
                            ),
                        )
                    }
                ),
            )
        }
    )
    retained_snapshot = None
    retained_results = None
    for repeat in ("first", "repeat"):
        receipt = scratch / f"receipt-{repeat}"
        command, snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
        if command.returncode != 0 or command.error is not None:
            raise ValueError(
                f"Native PCB thermal-via fixture failed: {command.stderr or command.error}"
            )
        if not native_pcb_command_matches(command, fixture_config):
            raise ValueError("Thermal-via fixture did not use the reviewed pinned KiCad command")
        if snapshot is None:
            raise ValueError("Native thermal-via fixture returned no PCB snapshot")
        if (
            int(snapshot.schema_version) < 7
            or snapshot.board_sha256 != board_sha256
            or snapshot.kicad_version != config.kicad_version
            or snapshot.image != config.image
            or snapshot.probe_sha256 != expected_probe_sha256()
            or not snapshot.zones_refilled
            or tuple(item.casefold() for item in snapshot.copper_layers) != ("f.cu", "b.cu")
        ):
            raise ValueError("Native via evidence is not bound to the exact board, stack, and tool")
        pad = next((item for item in snapshot.pads if item.pad.casefold() == "u1.1"), None)
        if pad is None or len(snapshot.vias) != 2 or len(pad.connected_vias) != 2:
            raise ValueError("Native fixture must expose exactly two vias connected to U1.1")
        via_by_id = {item.id: item for item in snapshot.vias}
        if any(
            via_by_id[item].net != "GND"
            or {via_by_id[item].start_layer.casefold(), via_by_id[item].end_layer.casefold()}
            != {"f.cu", "b.cu"}
            for item in pad.connected_vias
        ):
            raise ValueError("Native fixture vias do not match the expected connected layer span")
        (fault_entry,) = pcb_thermal_via_entries(fault_map, snapshot)
        (control_entry,) = pcb_thermal_via_entries(control_map, snapshot)
        if fault_entry.status != "INCOMPLETE" or control_entry.status != "COMPLETE":
            raise ValueError(
                f"Native connected-via count fault/control did not separate: "
                f"{fault_entry.status}/{control_entry.status}"
            )
        result = (fault_entry, control_entry)
        if retained_snapshot is None:
            retained_snapshot, retained_results = snapshot, result
        elif retained_snapshot != snapshot or retained_results != result:
            raise ValueError("Repeated native thermal-via evidence changed for identical inputs")
    if retained_results is None:
        raise ValueError("Native thermal-via results were not retained")
    fault_entry, control_entry = retained_results
    log.event(
        "pcb-thermal-via-fixture/pad-count",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        board_sha256=board_sha256,
        connected_vias=len(fault_entry.measurements),
        fault_minimum=3,
        control_minimum=2,
        fault_status=fault_entry.status,
        control_status=control_entry.status,
        repeatable="true",
        receipt=(scratch.relative_to(root) / "receipt-first").as_posix(),
    )
