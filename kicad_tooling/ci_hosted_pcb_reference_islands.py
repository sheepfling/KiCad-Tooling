"""Native acceptance for mapped PCB reference-zone islands without pad anchors."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .hwrepo.pcb_reference_plane_islands import unanchored_reference_zone_island_candidates
from .hwrepo.pcb_reference_plane_models import (
    PcbReferencePlaneCoverageReport,
    PcbReferencePlaneMap,
    PcbReferencePlaneRequirement,
)
from .hwrepo.pcb_reference_planes import pcb_reference_plane_entries
from .hwrepo.pcb_return_path_capture import (
    capture_native_pcb_connectivity,
    expected_probe_sha256,
    native_pcb_command_matches,
)
from .hwrepo.project_models import ProjectConfig


def _native_snapshot(
    root: Path,
    fixture_config: ProjectConfig,
    receipt: Path,
    *,
    board_sha256: str,
) -> PcbConnectivitySnapshot:
    command, snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(
            f"Native reference-island capture failed: {command.stderr or command.error}"
        )
    if not native_pcb_command_matches(command, fixture_config):
        raise ValueError("Native reference-island capture used an unpinned probe command")
    if snapshot is None:
        raise ValueError("Native reference-island capture returned no snapshot")
    if (
        snapshot.schema_version not in {"9", "10", "11", "12", "13", "14", "15", "16", "17", "18"}
        or snapshot.board_sha256 != board_sha256
        or snapshot.kicad_version != fixture_config.kicad_version
        or snapshot.image != fixture_config.image
        or snapshot.probe_sha256 != expected_probe_sha256()
        or not snapshot.zones_refilled
        or snapshot.copper_layers[0].casefold() != "f.cu"
        or snapshot.copper_layers[-1].casefold() != "b.cu"
    ):
        raise ValueError("Native reference-island evidence is not bound to source and tool")
    return snapshot


def _drc_summary(
    root: Path,
    board: Path,
    output: Path,
    image: str,
    log: HostedLog,
    *,
    case: str,
) -> tuple[str, ...]:
    relative_board = board.relative_to(root).as_posix()
    output_path = output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    log.run(
        f"pcb-reference-island-drc-{case}",
        (
            "docker",
            "run",
            "--rm",
            *user,
            "-v",
            f"{root.resolve()}:/work:ro",
            "-v",
            f"{output_path.parent}:/output:rw",
            image,
            "kicad-cli",
            "pcb",
            "drc",
            "--severity-all",
            "--format",
            "json",
            "--output",
            f"/output/{output_path.name}",
            f"/work/{relative_board}",
        ),
        cwd=root,
    )
    report = json.loads(output_path.read_text(encoding="utf-8"))
    if report.get("unconnected_items"):
        raise ValueError("Synthetic fixture unexpectedly reports unconnected DRC items")
    return tuple(sorted({str(item["type"]) for item in report.get("violations", [])}))


def pcb_reference_zone_island_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Repeat a native fault/control capture and show that DRC types do not distinguish it."""
    root = root.resolve()
    config: ProjectConfig = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError("Reference-zone island fixtures cover KiCad 10.0.0 and 10.0.5")
    source_root = tooling_checkout_root() / "tests/fixtures/design_lint/pcb-reference-zone-island"
    scratch = Path(
        tempfile.mkdtemp(prefix=f"pcb-reference-island-{project}-", dir=log.directory.resolve())
    )
    fault_board = scratch / "fault.kicad_pcb"
    control_board = scratch / "control.kicad_pcb"
    shutil.copyfile(source_root / "fault.kicad_pcb", fault_board)
    shutil.copyfile(source_root / "control.kicad_pcb", control_board)
    specification = PcbReferencePlaneMap(
        basis="Synthetic explicitly mapped adjacent reference-zone review",
        requirements=(
            PcbReferencePlaneRequirement(
                id="synthetic-data-return",
                basis="Synthetic B.Cu DATA route reviewed against adjacent F.Cu RETURN copper",
                signal_net="DATA",
                signal_layers=("B.Cu",),
                reference_net="RETURN",
                minimum_track_length_um=1_000,
                minimum_referenced_fraction=1,
                review_unanchored_islands=True,
            ),
        ),
    )
    retained: dict[str, tuple[PcbConnectivitySnapshot, tuple[str, ...]]] = {}
    for case, board in (("fault", fault_board), ("control", control_board)):
        relative_project = board.relative_to(root).with_suffix(".kicad_pro")
        fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
        board_hash = digest(board)
        drc_types = _drc_summary(
            root,
            board,
            scratch / f"{case}.drc.json",
            image,
            log,
            case=case,
        )
        samples: list[tuple[PcbConnectivitySnapshot, tuple[str, ...]]] = []
        for repeat in ("first", "repeat"):
            snapshot = _native_snapshot(
                root,
                fixture_config,
                scratch / f"{case}-receipt-{repeat}",
                board_sha256=board_hash,
            )
            entries = pcb_reference_plane_entries(specification, snapshot)
            if len(entries) != 1 or entries[0].status != "COMPLETE":
                raise ValueError(f"Native reference-island map is incomplete: {entries}")
            reference_zones = tuple(
                item
                for item in snapshot.zones
                if item.net is not None
                and item.net.casefold() == "return"
                and item.layer.casefold() == "f.cu"
            )
            if len(reference_zones) != 1 or len(reference_zones[0].filled_islands) != 1:
                raise ValueError("Synthetic RETURN zone did not produce one native filled island")
            expected = (0,) if case == "fault" else ()
            if reference_zones[0].unanchored_pad_island_indexes != expected:
                raise ValueError(
                    f"Native {case} pad-anchor evidence differed: "
                    f"{reference_zones[0].unanchored_pad_island_indexes}"
                )
            candidates = unanchored_reference_zone_island_candidates(
                PcbReferencePlaneCoverageReport(
                    status="COMPLETE",
                    mode="review",
                    map_sha256=hashlib.sha256(
                        specification.model_dump_json().encode("utf-8")
                    ).hexdigest(),
                    board_path=relative_project.with_suffix(".kicad_pcb").as_posix(),
                    board_sha256=snapshot.board_sha256,
                    snapshot_path=(scratch / f"{case}-receipt-{repeat}" / "snapshot.json")
                    .relative_to(root)
                    .as_posix(),
                    snapshot_sha256=digest(scratch / f"{case}-receipt-{repeat}/snapshot.json"),
                    probe_sha256=snapshot.probe_sha256,
                    kicad_version=snapshot.kicad_version,
                    image=snapshot.image,
                    netlist_sha256="f" * 64,
                    entries=entries,
                )
            )
            if bool(candidates) != (case == "fault"):
                raise ValueError(f"Mapped island candidate did not distinguish the {case} control")
            sample = (snapshot, drc_types)
            if samples and sample != samples[0]:
                raise ValueError(f"Repeated native {case} evidence changed")
            samples.append(sample)
        retained[case] = samples[0]
    fault_snapshot, fault_drc = retained["fault"]
    control_snapshot, control_drc = retained["control"]
    if fault_drc != control_drc or fault_snapshot.kicad_version != control_snapshot.kicad_version:
        raise ValueError("Fault/control DRC or native version differed unexpectedly")
    log.event(
        "pcb-reference-plane-fixture/unanchored-island",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        fault_fixture_sha256=digest(fault_board),
        control_fixture_sha256=digest(control_board),
        fault_unanchored_islands=str(
            len(
                next(
                    item
                    for item in fault_snapshot.zones
                    if item.net is not None
                    and item.net.casefold() == "return"
                    and item.layer.casefold() == "f.cu"
                ).unanchored_pad_island_indexes
            )
        ),
        control_unanchored_islands="none",
        drc_unconnected_items="0",
        drc_violation_types=",".join(fault_drc),
        repeatable="true",
        fault_receipt=(fault_board.parent / "fault-receipt-first").relative_to(root).as_posix(),
        control_receipt=(control_board.parent / "control-receipt-first")
        .relative_to(root)
        .as_posix(),
    )
