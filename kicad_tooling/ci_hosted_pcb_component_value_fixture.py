"""Exact KiCad fault/control evidence for schematic/PCB value review."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .ci_hosted_pcb_fixture_support import (
    HostedPcbFixtureContext,
    HostedPcbFixtureFailure,
    capture_verified_pcb_snapshot,
)
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import ContainerNetlistRunner
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
    ProjectKind,
)
from .hwrepo.pcb_component_inventory import evaluate_native_component_inventory_coverage
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .validate import read_netlist


def pcb_component_value_fixture_lane(
    context: HostedPcbFixtureContext,
    *,
    log: HostedLog,
) -> None:
    """Require repeated native value-field faults and controls to remain stable."""
    fixture_root = tooling_checkout_root() / (
        "tests/fixtures/design_lint/component-inventory-footprint-identity"
    )
    schematic_source = fixture_root / "control.kicad_sch"
    board_sources = {
        "fault": fixture_root / "value-fault.kicad_pcb",
        "control": fixture_root / "control.kicad_pcb",
    }
    expected_hashes = {
        "schematic": "3acf612f93c0f2f48c6b469928ab9366fc2374644966b9bf07087c8a4cd808f8",
        "fault": "08a35eee9763c93501167098fcdf8b7484c9c539f5d0c649b58b64fb99feb1c0",
        "control": "23a19d40848ad3b6136f163ccf3ab64c53fef9185d696cde96323b66415d8913",
    }
    if digest(schematic_source) != expected_hashes["schematic"]:
        raise ValueError("Native component-value schematic fixture digest changed")
    for case, source in board_sources.items():
        if digest(source) != expected_hashes[case]:
            raise ValueError(f"Native component-value {case} PCB fixture digest changed")

    runner = ContainerNetlistRunner()
    mismatch_references: dict[str, tuple[str, ...]] = {}
    component_values: dict[str, tuple[str, str]] = {}
    source_hashes: dict[str, str] = {}
    receipts: dict[str, str] = {}
    try:
        for case, board_source in board_sources.items():
            relative_project = context.scratch.relative_to(context.root) / f"value-{case}.kicad_pro"
            project_base = context.root / relative_project
            schematic = project_base.with_suffix(".kicad_sch")
            board = project_base.with_suffix(".kicad_pcb")
            shutil.copyfile(schematic_source, schematic)
            shutil.copyfile(board_source, board)
            fixture_config = context.config.model_copy(
                update={"project": relative_project.as_posix()}
            )
            schematic_hash = digest(schematic)
            board_hash = digest(board)
            source_hashes[f"{case}.schematic"] = schematic_hash
            source_hashes[f"{case}.board"] = board_hash

            retained_netlist: NetlistContract | None = None
            retained_snapshot: PcbConnectivitySnapshot | None = None
            retained_netlist_hash: str | None = None
            retained_snapshot_path: Path | None = None
            for repeat in ("first", "repeat"):
                netlist_path = context.scratch / f"value-{case}.{repeat}.netlist.xml"
                command = runner.export(context.root, fixture_config, netlist_path)
                write_model(
                    context.scratch / f"value-{case}.{repeat}.netlist.command.json", command
                )
                if command.returncode != 0 or command.error is not None:
                    raise ValueError(
                        f"Native component-value {case} export failed: "
                        f"{command.stderr or command.error}"
                    )
                observed_netlist = read_netlist(netlist_path)
                receipt = context.scratch / f"value-{case}.{repeat}.pcb-receipt"
                observed_snapshot = capture_verified_pcb_snapshot(
                    context,
                    fixture_config,
                    receipt,
                    expected_board_sha256=board_hash,
                    purpose=f"{case} component-value PCB",
                )
                if observed_snapshot.schema_version != "14":
                    raise ValueError(
                        "Native component-value comparison requires snapshot schema 14"
                    )
                if retained_netlist is None:
                    retained_netlist = observed_netlist
                    retained_snapshot = observed_snapshot
                    retained_netlist_hash = digest(netlist_path)
                    retained_snapshot_path = receipt / "snapshot.json"
                    receipts[case] = retained_snapshot_path.relative_to(context.root).as_posix()
                elif observed_netlist != retained_netlist or observed_snapshot != retained_snapshot:
                    raise ValueError(f"Repeated native component-value {case} evidence changed")

            if (
                retained_snapshot is None
                or retained_netlist_hash is None
                or retained_snapshot_path is None
            ):
                raise ValueError(f"Native component-value {case} evidence is unavailable")
            coverage = evaluate_native_component_inventory_coverage(
                retained_netlist,
                retained_snapshot,
                mode="review",
                netlist_sha256=retained_netlist_hash,
                board_path=board.relative_to(context.root).as_posix(),
                board_sha256=board_hash,
                snapshot_path=retained_snapshot_path.relative_to(context.root).as_posix(),
                snapshot_sha256=digest(retained_snapshot_path),
                probe_sha256=retained_snapshot.probe_sha256,
                value_mode="review",
            )
            if coverage.status != "COMPLETE" or coverage.value_comparison_status != "COMPLETE":
                raise ValueError(
                    coverage.value_comparison_issue
                    or coverage.issue
                    or "Native component-value comparison is incomplete"
                )
            component = retained_netlist.components.get("U1")
            placement = next(
                (
                    item
                    for item in retained_snapshot.footprints
                    if item.reference.casefold() == "u1"
                ),
                None,
            )
            if component is None or placement is None or placement.value is None:
                raise ValueError("Native component-value fixture must contain U1 on both sources")
            component_values[case] = (component.value, placement.value)
            mismatch_references[case] = tuple(item.reference for item in coverage.value_mismatches)
            if coverage.value_mismatches and case == "control":
                raise ValueError("Native component-value control unexpectedly differs")
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"native-component-value-{case}",
                project_kind=ProjectKind.PCB,
                selected_runner="container",
                source_hashes={
                    schematic.relative_to(context.root).as_posix(): schematic_hash,
                    board.relative_to(context.root).as_posix(): board_hash,
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
            actual_findings = tuple(
                finding.subject
                for finding in report.findings
                if finding.rule_id == "pcb.schematic_pcb_value_mismatch"
            )
            expected_findings = (
                ("U1: schematic and PCB value fields differ",) if case == "fault" else ()
            )
            if actual_findings != expected_findings:
                raise ValueError(
                    f"Native component-value {case} findings changed: {actual_findings}"
                )

        if mismatch_references != {"fault": ("U1",), "control": ()}:
            raise ValueError(f"Native component-value outcome changed: {mismatch_references}")
        log.event(
            "pcb-component-value-fixture/screen",
            "PASS",
            project=context.project,
            kicad_version=context.config.kicad_version,
            fault_mismatch_references=",".join(mismatch_references["fault"]),
            control_mismatch_references=",".join(mismatch_references["control"]),
            fault_schematic_value=component_values["fault"][0],
            fault_board_value=component_values["fault"][1],
            control_schematic_value=component_values["control"][0],
            control_board_value=component_values["control"][1],
            source_hashes=json.dumps(source_hashes, sort_keys=True, separators=(",", ":")),
            receipts=json.dumps(receipts, sort_keys=True, separators=(",", ":")),
            repeated_native_evidence="stable",
        )
    except Exception as exc:
        log.event(
            "pcb-component-value-fixture/screen",
            "FAIL",
            project=context.project,
            kicad_version=context.config.kicad_version,
            error=str(exc),
        )
        raise HostedPcbFixtureFailure(str(exc)) from exc
