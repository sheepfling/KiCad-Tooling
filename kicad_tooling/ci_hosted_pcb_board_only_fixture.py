"""Exact KiCad evidence for opt-in board-only footprint review."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_pcb_fixture_support import (
    HostedPcbFixtureContext,
    capture_verified_pcb_snapshot,
)
from .hwrepo.contract_coach import ContainerNetlistRunner
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_pcb_board_only_candidates import (
    pcb_board_only_footprint_candidates,
)
from .hwrepo.evidence import digest
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    PcbConnectivitySnapshot,
    ProjectKind,
)
from .hwrepo.pcb_component_inventory import evaluate_native_component_inventory_coverage
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


def pcb_board_only_footprint_fixture_lane(
    context: HostedPcbFixtureContext,
    *,
    log: HostedLog,
) -> None:
    """Require a board-only synthetic reference to survive exact native capture."""
    fixture_root = Path(__file__).resolve().parents[1] / (
        "tests/fixtures/design_lint/component-inventory-footprint-identity"
    )
    schematic_source = fixture_root / "control.kicad_sch"
    board_source = fixture_root / "board-only-reference.kicad_pcb"
    expected_hashes = {
        "schematic": "3acf612f93c0f2f48c6b469928ab9366fc2374644966b9bf07087c8a4cd808f8",
        "board": "756ea1d3c6ef11343d91323e7f97e4baf90ec62bcd2adee022ad58c901cada30",
    }
    if digest(schematic_source) != expected_hashes["schematic"]:
        raise ValueError("Board-only footprint schematic fixture digest changed")
    if digest(board_source) != expected_hashes["board"]:
        raise ValueError("Board-only footprint PCB fixture digest changed")

    relative_project = context.scratch.relative_to(context.root) / "board-only.kicad_pro"
    project_base = context.root / relative_project
    schematic = project_base.with_suffix(".kicad_sch")
    board = project_base.with_suffix(".kicad_pcb")
    shutil.copyfile(schematic_source, schematic)
    shutil.copyfile(board_source, board)
    config = context.config.model_copy(update={"project": relative_project.as_posix()})
    runner = ContainerNetlistRunner()
    retained_netlist: NetlistContract | None = None
    retained_snapshot: PcbConnectivitySnapshot | None = None
    retained_netlist_hash: str | None = None
    retained_snapshot_path: Path | None = None

    for repeat in ("first", "repeat"):
        netlist_path = context.scratch / f"board-only.{repeat}.netlist.xml"
        command = runner.export(context.root, config, netlist_path)
        write_model(context.scratch / f"board-only.{repeat}.netlist.command.json", command)
        if command.returncode != 0 or command.error is not None:
            raise ValueError(f"Board-only fixture netlist export failed: {command.stderr}")
        observed = read_netlist(netlist_path)
        receipt = context.scratch / f"board-only.{repeat}.pcb-receipt"
        snapshot = capture_verified_pcb_snapshot(
            context,
            config,
            receipt,
            expected_board_sha256=expected_hashes["board"],
            purpose="board-only footprint PCB",
        )
        if snapshot.schema_version not in {"12", "13"}:
            raise ValueError(
                "Board-only review requires native PCB footprint snapshot schema 12 or 13"
            )
        if retained_netlist is None:
            retained_netlist = observed
            retained_snapshot = snapshot
            retained_netlist_hash = digest(netlist_path)
            retained_snapshot_path = receipt / "snapshot.json"
        elif observed != retained_netlist or snapshot != retained_snapshot:
            raise ValueError("Repeated board-only native evidence changed")

    if retained_snapshot is None:
        raise ValueError("Native board-only source evidence is unavailable")
    if retained_netlist_hash is None or retained_snapshot_path is None:
        raise ValueError("Native board-only source digests are unavailable")

    coverage = evaluate_native_component_inventory_coverage(
        retained_netlist,
        retained_snapshot,
        mode="off",
        netlist_sha256=retained_netlist_hash,
        board_path=board.relative_to(context.root).as_posix(),
        board_sha256=expected_hashes["board"],
        snapshot_path=retained_snapshot_path.relative_to(context.root).as_posix(),
        snapshot_sha256=digest(retained_snapshot_path),
        probe_sha256=retained_snapshot.probe_sha256,
        board_only_mode="review",
    )
    candidates = pcb_board_only_footprint_candidates(coverage)
    observed_references = tuple(item.subject.split(":", maxsplit=1)[0] for item in candidates)
    if coverage.status != "COMPLETE" or observed_references != ("J2",):
        raise ValueError(f"Native board-only review candidates changed: {observed_references}")

    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="native-board-only-footprint",
        project_kind=ProjectKind.PCB,
        selected_runner="container",
        source_hashes={
            schematic.relative_to(context.root).as_posix(): expected_hashes["schematic"],
            board.relative_to(context.root).as_posix(): expected_hashes["board"],
        },
        netlist_sha256=retained_netlist_hash,
        observed=retained_netlist,
    )
    report = evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.board_only_footprint",
                    mode="review",
                    reason="native synthetic fault candidate",
                ),
            )
        ),
        pcb_component_inventory_coverage=coverage,
    )
    findings = tuple(item for item in report.findings if item.rule_id == "pcb.board_only_footprint")
    if report.status != "REVIEW" or len(findings) != 1 or findings[0].mode != "review":
        raise ValueError("Native board-only candidate did not reach the configured review rule")

    log.event(
        "pcb-board-only-footprint-fixture/screen",
        "PASS",
        kicad_version=context.config.kicad_version,
        candidate_reference="J2",
        native_netlist_and_board_evidence="true",
        repeated_evidence="stable",
        schematic_sha256=expected_hashes["schematic"],
        board_sha256=expected_hashes["board"],
        snapshot_sha256=digest(retained_snapshot_path),
    )
