"""Exact-version native fixtures for board-level fiducial-count lint."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog
from .hwrepo.design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from .hwrepo.evidence import digest
from .hwrepo.pcb_fiducial_models import (
    PcbFiducialMap,
    PcbFiducialRequirement,
)
from .hwrepo.pcb_fiducials import evaluate_pcb_fiducials
from .hwrepo.pcb_return_path_capture import (
    capture_native_pcb_connectivity,
    expected_probe_sha256,
    native_pcb_command_matches,
)
from .hwrepo.project_models import (
    ComponentIdentity,
    IgnoredChecks,
    PcbOnlyValidationContract,
    ProjectConfig,
    ProjectKind,
)


def pcb_fiducial_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Compare a one-fitted-fiducial board with fault and exact-boundary maps twice."""
    root = root.resolve()
    toolchains = {pinned_image: version for version, pinned_image in KICAD_10_NATIVE_TOOLCHAINS}
    version = toolchains.get(image)
    if version is None:
        raise ValueError(f"Fiducial fixtures do not cover image {image}")

    fixture_root = Path(__file__).resolve().parent / "hwrepo/fixtures"
    scratch = Path(
        tempfile.mkdtemp(prefix=f"pcb-fiducials-{project}-", dir=log.directory.resolve())
    )
    relative_project = scratch.relative_to(root) / "fiducials.kicad_pro"
    board_path = root / relative_project.with_suffix(".kicad_pcb")
    shutil.copyfile(fixture_root / "pcb-fiducials.kicad_pcb", board_path)
    board_sha256 = digest(board_path)
    fixture_config = ProjectConfig(
        schema_version="1",
        kind=ProjectKind.PCB_ONLY,
        assurance_profile="training",
        not_for_manufacture=True,
        project_id="synthetic-pcb-fiducials",
        component_identity=ComponentIdentity(required=False, part_ids=()),
        toolchain_id=f"kicad-{version}",
        kicad_version=version,
        image=image,
        project=relative_project.as_posix(),
        source_roots=(scratch.relative_to(root).as_posix(),),
        required_inputs=(board_path.relative_to(root).as_posix(),),
        validation=PcbOnlyValidationContract(
            kind=ProjectKind.PCB_ONLY,
            expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
        ),
    )

    requirement = PcbFiducialRequirement(
        id="synthetic-board-fiducials",
        basis="Synthetic native fault/control threshold; not assembly guidance",
        minimum_count=2,
        accepted_footprints=("Synthetic:Fiducial_1mm_Mask2mm",),
        side="front",
    )
    fault_map = PcbFiducialMap(requirements=(requirement,))
    control_map = fault_map.model_copy(
        update={"requirements": (requirement.model_copy(update={"minimum_count": 1}),)}
    )

    retained_snapshot = None
    retained_entries = None
    for repeat in ("first", "repeat"):
        receipt = scratch / f"receipt-{repeat}"
        command, native_snapshot = capture_native_pcb_connectivity(root, fixture_config, receipt)
        if command.returncode != 0 or command.error is not None:
            raise ValueError(
                f"Native PCB fiducial fixture failed: {command.stderr or command.error}"
            )
        if not native_pcb_command_matches(command, fixture_config):
            raise ValueError("Fiducial fixture did not use the reviewed pinned KiCad command")
        if native_snapshot is None:
            raise ValueError("Native fiducial fixture returned no PCB snapshot")
        if (
            int(native_snapshot.schema_version) < 12
            or native_snapshot.board_sha256 != board_sha256
            or native_snapshot.kicad_version != version
            or native_snapshot.image != image
            or native_snapshot.probe_sha256 != expected_probe_sha256()
            or not native_snapshot.zones_refilled
        ):
            raise ValueError("Native fiducial evidence is not bound to the exact board and tool")

        output = receipt
        evidence = PcbGeometrySourceEvidence(
            board_path=board_path.relative_to(root).as_posix(),
            board_sha256=board_sha256,
            snapshot_relative_path=(output / "snapshot.json").relative_to(root).as_posix(),
            snapshot_path=output / "snapshot.json",
            snapshot_sha256=digest(output / "snapshot.json"),
            probe_sha256=expected_probe_sha256(),
            snapshot=native_snapshot,
            command=command,
            command_path=output / "native.command.json",
            command_sha256=digest(output / "native.command.json"),
        )
        fault = evaluate_pcb_fiducials(fault_map, "review", evidence, "a" * 64)
        control = evaluate_pcb_fiducials(control_map, "review", evidence, "a" * 64)
        if (
            fault.status != "INCOMPLETE"
            or control.status != "COMPLETE"
            or fault.entries[0].observed_count != 1
            or tuple(item.reference for item in fault.entries[0].observations) != ("FID1",)
        ):
            raise ValueError(
                "Native fitted-footprint count did not separate the exact fault and control maps"
            )
        current = (native_snapshot, fault.entries, control.entries)
        if retained_snapshot is None:
            retained_snapshot, retained_entries = current[0], current[1:]
        elif retained_snapshot != current[0] or retained_entries != current[1:]:
            raise ValueError("Repeated native fiducial evidence changed for identical inputs")

    log.event(
        "pcb-fiducial-fixture/board-count",
        "PASS",
        project=project,
        kicad_version=version,
        board_sha256=board_sha256,
        fitted_exact_matches=1,
        fault_minimum=2,
        control_minimum=1,
        fault_status="INCOMPLETE",
        control_status="COMPLETE",
        dnp_excluded="true",
        unrelated_footprint_excluded="true",
        repeatable="true",
        receipt=(scratch.relative_to(root) / "receipt-first").as_posix(),
    )
