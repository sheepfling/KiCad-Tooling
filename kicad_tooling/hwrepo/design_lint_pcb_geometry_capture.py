"""Source binding for native PCB geometry snapshots used by design lint."""

from __future__ import annotations

from pathlib import Path

from ..validate import hashes
from .contract_coach import pinned_image
from .contracts import repo_path
from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from .discovery import ProjectConfig
from .evidence import digest
from .models import ContractCoachReport
from .pcb_geometry_receipts import verify_pcb_geometry_receipts, write_pcb_geometry_snapshot
from .pcb_return_path_capture import (
    capture_native_pcb_connectivity,
    expected_probe_sha256,
    native_pcb_command_matches,
)
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceRequestSet
from .project_models import ProjectKind


def capture_pcb_geometry_source(
    root: Path,
    config: ProjectConfig,
    coach: ContractCoachReport,
    output: Path,
    *,
    touch_pad_clearance_requests: PcbTouchPadClearanceRequestSet | None = None,
) -> PcbGeometrySourceEvidence:
    """Capture exact native board geometry and bind it to the authored source/toolchain."""
    if config.kind is not ProjectKind.PCB:
        raise ValueError("PCB geometry requirements need an authoritative PCB project")
    if coach.netlist_sha256 is None:
        raise ValueError("Source-bound native netlist hash is unavailable")
    board_relative = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    board_path = repo_path(root, board_relative)
    board_hash = digest(board_path)
    if coach.source_hashes.get(board_relative) != board_hash:
        raise ValueError("Authoritative PCB is absent from, or differs from, native source hashes")
    command, snapshot = capture_native_pcb_connectivity(
        root,
        config,
        output,
        touch_pad_clearance_requests=touch_pad_clearance_requests,
    )
    if snapshot is None:
        raise ValueError(
            "Native PCB geometry probe failed; inspect a native.command.json receipt under "
            "build/design-lint/pcb-geometry-*"
        )
    if (
        snapshot.schema_version not in {"10", "11", "12", "13", "14", "15"}
        or snapshot.board_sha256 != board_hash
        or snapshot.kicad_version != config.kicad_version
        or snapshot.image != pinned_image(config.image)
        or snapshot.probe_sha256 != expected_probe_sha256()
        or not snapshot.zones_refilled
        or not native_pcb_command_matches(
            command,
            config,
            touch_pad_clearance_probes=touch_pad_clearance_requests is not None,
        )
    ):
        raise ValueError(
            "Native PCB geometry evidence does not match the reviewed source/toolchain"
        )
    snapshot_path = output / "snapshot.json"
    write_pcb_geometry_snapshot(snapshot_path, snapshot)
    if digest(board_path) != board_hash or hashes(root, config.source_roots) != coach.source_hashes:
        raise ValueError("Project sources changed during native PCB geometry capture")
    command_path = output / "native.command.json"
    evidence = PcbGeometrySourceEvidence(
        board_path=board_relative,
        board_sha256=board_hash,
        snapshot_relative_path=snapshot_path.relative_to(root).as_posix(),
        snapshot_path=snapshot_path,
        snapshot_sha256=digest(snapshot_path),
        probe_sha256=expected_probe_sha256(),
        snapshot=snapshot,
        command=command,
        command_path=command_path,
        command_sha256=digest(command_path),
    )
    verify_pcb_geometry_receipts(
        evidence.snapshot,
        evidence.snapshot_path,
        evidence.snapshot_sha256,
        evidence.command,
        evidence.command_path,
        evidence.command_sha256,
    )
    return evidence
