"""Exact KiCad fault/control evidence for schematic-to-PCB inventory review."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_pcb_fixture_support import (
    HostedPcbFixtureFailure,
    capture_verified_pcb_snapshot,
    prepare_pcb_fixture,
)
from .hwrepo.contract_coach import ContainerNetlistRunner
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy
from .hwrepo.pcb_component_inventory import evaluate_native_component_inventory_coverage
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def pcb_component_inventory_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Compare repeated native schematic and PCB inventories for fault/control sources."""
    context = prepare_pcb_fixture(
        root,
        project=project,
        image=image,
        log=log,
        lane="PCB component inventory",
        scratch_prefix="pcb-component-inventory",
    )
    root = context.root
    config = context.config
    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    cases = {
        "fault": fixture_root / "component-peer-power-native/control.kicad_sch",
        "control": fixture_root / "usb-peer-reference-native/control.kicad_sch",
    }
    board_source = context.fixture_root / "pcb-decoupling-placement.kicad_pcb"
    expected_fixture_sha256 = {
        "fault": "0198205216be6cd5be0c03ac14b7c2b9de52258aacd564159e16532fadb10446",
        "control": "0fe232d691405e8ac95ef894a2ece81a3d11ccd9b200f59ff6fcb685d591bd98",
        "board": "adbec8134e1bce77a91642ac610e70c2ff23d6dca9dc7ac9fa97853e0251a445",
    }
    for case, schematic_source in cases.items():
        if digest(schematic_source) != expected_fixture_sha256[case]:
            raise ValueError(f"Native {case} schematic fixture digest changed")
    if digest(board_source) != expected_fixture_sha256["board"]:
        raise ValueError("Native PCB component inventory board fixture digest changed")
    runner = ContainerNetlistRunner()
    version = runner.version(root, config)
    if (
        version.returncode != 0
        or version.error is not None
        or version.stdout.strip() != config.kicad_version
    ):
        raise ValueError("Native schematic export version differs from the selected exact KiCad")

    try:
        results: dict[str, DesignLintReport] = {}
        case_receipts: dict[str, str] = {}
        schematic_hashes: dict[str, str] = {}
        expected_missing = {"fault": ("U2",), "control": ()}
        for case, schematic_source in cases.items():
            relative_project = context.scratch.relative_to(root) / f"{case}.kicad_pro"
            project_base = root / relative_project
            schematic = project_base.with_suffix(".kicad_sch")
            board = project_base.with_suffix(".kicad_pcb")
            shutil.copyfile(schematic_source, schematic)
            shutil.copyfile(board_source, board)
            fixture_config = config.model_copy(update={"project": relative_project.as_posix()})
            schematic_hash = digest(schematic)
            board_hash = digest(board)
            schematic_hashes[case] = schematic_hash

            retained_netlist = None
            retained_snapshot = None
            retained_netlist_hash: str | None = None
            retained_snapshot_path: Path | None = None
            retained_receipt: Path | None = None
            for repeat in ("first", "repeat"):
                netlist_path = context.scratch / f"{case}.{repeat}.netlist.xml"
                netlist_command = runner.export(root, fixture_config, netlist_path)
                write_model(context.scratch / f"{case}.{repeat}.netlist.command.json", netlist_command)
                if netlist_command.returncode != 0 or netlist_command.error is not None:
                    raise ValueError(
                        f"Native {case} schematic export failed: "
                        f"{netlist_command.stderr or netlist_command.error}"
                    )
                observed = read_netlist(netlist_path)
                receipt = context.scratch / f"{case}.{repeat}.pcb-receipt"
                snapshot = capture_verified_pcb_snapshot(
                    context,
                    fixture_config,
                    receipt,
                    expected_board_sha256=board_hash,
                    purpose=f"{case} component inventory PCB",
                )
                if snapshot.schema_version != "12":
                    raise ValueError("Native footprint inventory requires PCB snapshot schema 12")
                if retained_netlist is None:
                    retained_netlist = observed
                    retained_snapshot = snapshot
                    retained_netlist_hash = digest(netlist_path)
                    retained_snapshot_path = receipt / "snapshot.json"
                    retained_receipt = receipt
                elif observed != retained_netlist or snapshot != retained_snapshot:
                    raise ValueError(f"Repeated native {case} component inventory evidence changed")

            if (
                retained_netlist is None
                or retained_snapshot is None
                or retained_netlist_hash is None
                or retained_snapshot_path is None
                or retained_receipt is None
            ):
                raise ValueError(f"Native {case} component inventory evidence is unavailable")
            inventory = evaluate_native_component_inventory_coverage(
                retained_netlist,
                retained_snapshot,
                mode="review",
                netlist_sha256=retained_netlist_hash,
                board_path=board.relative_to(root).as_posix(),
                board_sha256=board_hash,
                snapshot_path=retained_snapshot_path.relative_to(root).as_posix(),
                snapshot_sha256=digest(retained_snapshot_path),
                probe_sha256=retained_snapshot.probe_sha256,
            )
            if inventory.status != "COMPLETE":
                raise ValueError(inventory.issue or "Native PCB component inventory is incomplete")
            missing_references = tuple(item.reference for item in inventory.missing_placements)
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"native-component-inventory-{case}",
                project_kind="pcb",
                selected_runner="container",
                source_hashes={
                    schematic.relative_to(root).as_posix(): schematic_hash,
                    board.relative_to(root).as_posix(): board_hash,
                },
                netlist_sha256=retained_netlist_hash,
                observed=retained_netlist,
            )
            if missing_references != expected_missing[case]:
                raise ValueError(
                    f"Native {case} missing-placement references changed: {missing_references}"
                )
            case_receipts[case] = retained_receipt.relative_to(root).as_posix()
            results[case] = evaluate(
                coach.project_id,
                coach,
                DesignLintPolicy(),
                pcb_component_inventory_coverage=inventory,
            )

        for case, expected in expected_missing.items():
            report = results[case]
            findings = tuple(
                item
                for item in report.findings
                if item.rule_id == "pcb.schematic_component_inventory"
            )
            observed = tuple(item.subject.split(":", maxsplit=1)[0] for item in findings)
            if observed != expected:
                raise ValueError(f"Native {case} design-lint candidates changed: {observed}")

        log.event(
            "pcb-component-inventory-fixture/screen",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            fault_missing_references=",".join(expected_missing["fault"]),
            control_missing_references=",".join(expected_missing["control"]),
            native_netlist_and_board_evidence="true",
            repeated_evidence="stable",
            fault_schematic_sha256=schematic_hashes["fault"],
            control_schematic_sha256=schematic_hashes["control"],
            board_sha256=digest(board_source),
            fault_receipt=case_receipts["fault"],
            control_receipt=case_receipts["control"],
        )
    except Exception as exc:
        log.event(
            "pcb-component-inventory-fixture/screen",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            error=str(exc),
        )
        raise HostedPcbFixtureFailure(str(exc)) from exc
