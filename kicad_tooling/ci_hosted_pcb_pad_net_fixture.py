"""Exact KiCad fault/control evidence for schematic-to-PCB pad net review."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import MappingProxyType

from .ci_hosted_pcb_fixture_support import (
    HostedPcbFixtureFailure,
    capture_verified_pcb_snapshot,
    prepare_pcb_fixture,
)
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import ContainerNetlistRunner
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy, ProjectKind
from .hwrepo.pcb_component_inventory import evaluate_native_component_inventory_coverage
from .validate import read_netlist

_FIXTURE_HASHES = MappingProxyType(
    {
        "schematic": "343664d4ba1570250da0eb5b52dc23f7ba214c33e1db580c236dc0008fcaf394",
        "control": "8e83c6c49c271bc686a9d067128e65e823416bd40a1659c9238c1cf743dfb519",
        "fault": "1beeaaefba6942b2b0cc49834f0fea28f710282ba76365fc4688c64c0d4fc1e9",
    }
)


def pcb_schematic_pcb_pad_net_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Repeat native netlist and pad snapshots for an assigned and missing pad net."""
    context = prepare_pcb_fixture(
        root,
        project=project,
        image=image,
        log=log,
        lane="schematic-to-PCB pad net comparison",
        scratch_prefix="pcb-pad-net",
    )
    root = context.root
    config = context.config
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint/schematic-pcb-pad-net"
    schematic_source = fixture_root / "control.kicad_sch"
    board_sources = {case: fixture_root / f"{case}.kicad_pcb" for case in ("control", "fault")}
    if digest(schematic_source) != _FIXTURE_HASHES["schematic"]:
        raise ValueError("Native PCB pad net schematic fixture digest changed")
    for case, source in board_sources.items():
        if digest(source) != _FIXTURE_HASHES[case]:
            raise ValueError(f"Native PCB pad net {case} fixture digest changed")

    runner = ContainerNetlistRunner()
    version = runner.version(root, config)
    if (
        version.returncode != 0
        or version.error is not None
        or version.stdout.strip() != config.kicad_version
    ):
        raise ValueError("Native schematic export version differs from the selected exact KiCad")

    source_hashes: dict[str, str] = {}
    receipts: dict[str, str] = {}
    outcomes: dict[str, tuple[str, ...]] = {}
    try:
        for case, board_source in board_sources.items():
            relative_project = context.scratch.relative_to(root) / f"pad-net-{case}.kicad_pro"
            project_base = root / relative_project
            schematic = project_base.with_suffix(".kicad_sch")
            board = project_base.with_suffix(".kicad_pcb")
            shutil.copyfile(schematic_source, schematic)
            shutil.copyfile(board_source, board)
            fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
            schematic_hash = digest(schematic)
            board_hash = digest(board)
            source_hashes[f"{case}.schematic"] = schematic_hash
            source_hashes[f"{case}.board"] = board_hash

            retained_netlist = None
            retained_snapshot = None
            retained_netlist_hash: str | None = None
            retained_snapshot_path: Path | None = None
            for repeat in ("first", "repeat"):
                netlist_path = context.scratch / f"pad-net-{case}.{repeat}.netlist.xml"
                command = runner.export(root, fixture_config, netlist_path)
                write_model(
                    context.scratch / f"pad-net-{case}.{repeat}.netlist.command.json", command
                )
                if command.returncode != 0 or command.error is not None:
                    raise ValueError(
                        f"Native PCB pad net {case} schematic export failed: "
                        f"{command.stderr or command.error}"
                    )
                observed_netlist = read_netlist(netlist_path)
                receipt = context.scratch / f"pad-net-{case}.{repeat}.pcb-receipt"
                observed_snapshot = capture_verified_pcb_snapshot(
                    context,
                    fixture_config,
                    receipt,
                    expected_board_sha256=board_hash,
                    purpose=f"{case} schematic-to-PCB pad net comparison",
                )
                if observed_snapshot.schema_version not in {"12", "13", "14", "15"}:
                    raise ValueError(
                        "Native pad net comparison requires snapshot schema 12, 13, or 14"
                    )
                if retained_netlist is None:
                    retained_netlist = observed_netlist
                    retained_snapshot = observed_snapshot
                    retained_netlist_hash = digest(netlist_path)
                    retained_snapshot_path = receipt / "snapshot.json"
                    receipts[case] = retained_snapshot_path.relative_to(root).as_posix()
                elif observed_netlist != retained_netlist or observed_snapshot != retained_snapshot:
                    raise ValueError(f"Repeated native PCB pad net {case} evidence changed")

            if retained_snapshot is None or retained_netlist_hash is None:
                raise ValueError(f"Native PCB pad net {case} evidence is unavailable")
            if retained_snapshot_path is None:
                raise ValueError(f"Native PCB pad net {case} snapshot receipt is unavailable")
            coverage = evaluate_native_component_inventory_coverage(
                retained_netlist,
                retained_snapshot,
                mode="off",
                pad_net_mode="review",
                netlist_sha256=retained_netlist_hash,
                board_path=board.relative_to(root).as_posix(),
                board_sha256=board_hash,
                snapshot_path=retained_snapshot_path.relative_to(root).as_posix(),
                snapshot_sha256=digest(retained_snapshot_path),
                probe_sha256=retained_snapshot.probe_sha256,
            )
            if coverage.status != "COMPLETE" or coverage.pad_net_comparison_status != "COMPLETE":
                raise ValueError(
                    coverage.pad_net_comparison_issue
                    or coverage.issue
                    or "Native PCB pad net comparison is incomplete"
                )
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"native-pcb-pad-net-{case}",
                project_kind=ProjectKind.PCB,
                selected_runner="container",
                source_hashes={
                    schematic.relative_to(root).as_posix(): schematic_hash,
                    board.relative_to(root).as_posix(): board_hash,
                },
                netlist_sha256=retained_netlist_hash,
                observed=retained_netlist,
            )
            report = evaluate(
                coach.project_id,
                coach,
                DesignLintPolicy(),
                pcb_component_inventory_coverage=coverage,
            )
            outcomes[case] = tuple(
                finding.subject
                for finding in report.findings
                if finding.rule_id == "pcb.schematic_pcb_pad_net_mismatch"
            )

        if outcomes != {
            "control": (),
            "fault": ("U1.1: schematic and PCB net assignments differ",),
        }:
            raise ValueError(f"Native PCB pad net outcome changed: {outcomes}")
        log.event(
            "pcb-schematic-pcb-pad-net-fixture/screen",
            "PASS",
            project=context.project,
            kicad_version=config.kicad_version,
            fault_findings=";".join(outcomes["fault"]),
            control_findings=";".join(outcomes["control"]),
            source_hashes=json.dumps(source_hashes, sort_keys=True, separators=(",", ":")),
            receipts=json.dumps(receipts, sort_keys=True, separators=(",", ":")),
            repeated_native_evidence="stable",
        )
    except Exception as exc:
        log.event(
            "pcb-schematic-pcb-pad-net-fixture/screen",
            "FAIL",
            project=context.project,
            kicad_version=config.kicad_version,
            error=str(exc),
        )
        raise HostedPcbFixtureFailure(str(exc)) from exc
