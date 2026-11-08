"""Exact-version native fixtures for alternate PCB reference-net coverage."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .ci_hosted_support import HostedLog
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .hwrepo.pcb_reference_plane_models import (
    PcbReferencePlaneMap,
    PcbReferencePlaneRequirement,
)
from .hwrepo.pcb_reference_plane_transitions import (
    PcbAlternateReferenceRunMeasurement,
    alternate_reference_plane_run_measurements,
)
from .hwrepo.pcb_reference_planes import pcb_reference_plane_entries
from .hwrepo.pcb_return_path_capture import (
    capture_native_pcb_connectivity,
    expected_probe_sha256,
    native_pcb_command_matches,
)
from .hwrepo.project_models import ProjectConfig


def pcb_alternate_reference_plane_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify native alternate-zone coverage and an authored threshold control."""
    root = root.resolve()
    config: ProjectConfig = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Alternate reference-plane fixtures do not cover KiCad {config.kicad_version}"
        )
    fixture = (
        Path(__file__).resolve().parent / "hwrepo/fixtures/pcb-reference-alternate-net.kicad_pcb"
    )
    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"pcb-reference-alternate-net-{project}-",
            dir=log.directory.resolve(),
        )
    )
    relative_project = scratch.relative_to(root) / "alternate-net.kicad_pro"
    board = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(fixture, board)
    board_sha256 = digest(board)
    fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
    base_requirement = PcbReferencePlaneRequirement(
        id="synthetic-alternate-net",
        basis="Synthetic alternate-net geometry and threshold control",
        signal_net="DATA",
        signal_layers=("F.Cu",),
        reference_net="GND",
        minimum_track_length_um=1_000,
        minimum_referenced_fraction=0,
    )
    fault_map = PcbReferencePlaneMap(
        basis="Synthetic low alternate-net threshold fault case",
        requirements=(
            base_requirement.model_copy(update={"minimum_alternate_reference_length_um": 500}),
        ),
    )
    control_map = PcbReferencePlaneMap(
        basis="Synthetic above-measured-coverage threshold control",
        requirements=(
            base_requirement.model_copy(update={"minimum_alternate_reference_length_um": 3_000}),
        ),
    )

    try:
        retained: dict[
            str, tuple[PcbConnectivitySnapshot, PcbAlternateReferenceRunMeasurement]
        ] = {}
        for case, specification in (("fault", fault_map), ("control", control_map)):
            samples: list[tuple[PcbConnectivitySnapshot, PcbAlternateReferenceRunMeasurement]] = []
            for repeat in ("first", "repeat"):
                receipt = scratch / f"{case}-receipt-{repeat}"
                command, snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
                if command.returncode != 0 or command.error is not None:
                    raise ValueError(
                        f"Native alternate reference-plane {case} capture failed: "
                        f"{command.stderr or command.error}"
                    )
                if not native_pcb_command_matches(command, fixture_config):
                    raise ValueError(
                        "Native alternate reference-plane capture used an unpinned probe"
                    )
                if snapshot is None:
                    raise ValueError(
                        f"Native alternate reference-plane {case} returned no snapshot"
                    )
                if (
                    snapshot.board_sha256 != board_sha256
                    or snapshot.kicad_version != config.kicad_version
                    or snapshot.image != config.image
                    or snapshot.probe_sha256 != expected_probe_sha256()
                    or not snapshot.zones_refilled
                    or snapshot.copper_layers != ("F.Cu", "B.Cu")
                ):
                    raise ValueError("Native alternate-plane evidence is not source/tool bound")
                named_zones = {
                    (zone.net.casefold(), zone.layer.casefold()): zone
                    for zone in snapshot.zones
                    if zone.net is not None
                }
                if not {("gnd", "b.cu"), ("vcc", "b.cu")} <= set(named_zones):
                    raise ValueError(
                        "Native refill did not retain both synthetic adjacent-net zones"
                    )
                entries = pcb_reference_plane_entries(specification, snapshot)
                if len(entries) != 1 or entries[0].status != "COMPLETE":
                    raise ValueError(f"Native alternate-plane map is incomplete: {entries}")
                if len(entries[0].tracks) != 1:
                    raise ValueError(
                        "Native alternate-plane fixture must expose one mapped DATA track"
                    )
                measurements = alternate_reference_plane_run_measurements(entries[0])
                vcc_runs = tuple(
                    item for item in measurements if item.alternate_net.casefold() == "vcc"
                )
                if len(vcc_runs) != 1 or not vcc_runs[0].track_coverage_nm:
                    raise ValueError("Native DATA route did not produce VCC centerline coverage")
                measured = vcc_runs[0]
                if measured.meets_threshold != (case == "fault"):
                    raise ValueError(
                        f"Native alternate-plane {case} threshold result was unexpected: {measured}"
                    )
                sample = (snapshot, measured)
                if samples and sample != samples[0]:
                    raise ValueError(
                        "Repeated alternate reference-plane capture changed its evidence"
                    )
                samples.append(sample)
            if len(samples) != 2:
                raise ValueError("Native alternate reference-plane evidence was not retained")
            retained[case] = samples[0]

        fault_snapshot, fault_measurement = retained["fault"]
        control_snapshot, control_measurement = retained["control"]
        if fault_snapshot.kicad_version != control_snapshot.kicad_version:
            raise ValueError("Native alternate reference-plane fault/control versions differ")
        log.event(
            "pcb-reference-plane-fixture/alternate-net",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=board_sha256,
            alternate_net="VCC",
            adjacent_layer=fault_measurement.reference_layer,
            fault_threshold_um=fault_measurement.minimum_length_um,
            control_threshold_um=control_measurement.minimum_length_um,
            observed_coverage_nm=str(fault_measurement.total_coverage_nm),
            fault_review="true",
            control_review="false",
            repeatable="true",
            fault_receipt=(scratch.relative_to(root) / "fault-receipt-first").as_posix(),
            control_receipt=(scratch.relative_to(root) / "control-receipt-first").as_posix(),
        )
    except Exception as exc:
        log.event(
            "pcb-reference-plane-fixture/alternate-net",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            fixture_sha256=board_sha256,
            error=str(exc),
        )
        raise
