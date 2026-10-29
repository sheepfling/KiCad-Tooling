"""Exact KiCad fixtures for schematic/PCB DNP consistency review."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .ci_hosted_pcb_fixture_support import (
    HostedPcbFixtureContext,
    capture_verified_pcb_snapshot,
)
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import ContainerNetlistRunner
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract, ProjectKind
from .hwrepo.pcb_component_inventory import evaluate_native_component_inventory_coverage
from .hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .hwrepo.pcb_required_fitted_reference_models import (
    PcbRequiredFittedReference,
    PcbRequiredFittedReferenceMap,
)
from .validate import read_netlist


def pcb_population_mismatch_fixture_lane(
    context: HostedPcbFixtureContext,
    *,
    log: HostedLog,
) -> None:
    """Check both DNP mismatch directions and matched controls with repeated native evidence."""
    fixture_root = tooling_checkout_root() / (
        "tests/fixtures/design_lint/component-inventory-footprint-identity"
    )
    schematic_control = fixture_root / "control.kicad_sch"
    schematic_dnp = fixture_root / "population-schematic-dnp.kicad_sch"
    board_control = fixture_root / "control.kicad_pcb"
    board_dnp = fixture_root / "population-board-dnp.kicad_pcb"
    expected_hashes = {
        schematic_control: "3acf612f93c0f2f48c6b469928ab9366fc2374644966b9bf07087c8a4cd808f8",
        schematic_dnp: "7f185318b3941f10901f8e27bc29b13030ca771e4ff7d3418c09e18a6428c269",
        board_control: "23a19d40848ad3b6136f163ccf3ab64c53fef9185d696cde96323b66415d8913",
        board_dnp: "cabf0b68f4ceadffa21ec590c7a2a67c5a54c9930a1e57bae688a813417b8ca4",
    }
    for source, expected in expected_hashes.items():
        if digest(source) != expected:
            raise ValueError(f"Native PCB population fixture changed: {source.name}")

    cases = {
        "board-only-dnp": (schematic_control, board_dnp, ("U1",), (False, True)),
        "schematic-only-dnp": (schematic_dnp, board_control, ("U1",), (True, False)),
        "both-fitted": (schematic_control, board_control, (), (False, False)),
        "both-dnp": (schematic_dnp, board_dnp, (), (True, True)),
    }
    runner = ContainerNetlistRunner()
    observed_outcomes: dict[str, tuple[str, ...]] = {}
    required_outcomes: dict[str, tuple[str, ...]] = {}
    required_violations: dict[str, tuple[str, ...]] = {}
    source_hashes: dict[str, str] = {}
    repeats_stable = True

    for case, (schematic_source, board_source, expected_refs, expected_state) in cases.items():
        relative_project = (
            context.scratch.relative_to(context.root) / f"population-{case}.kicad_pro"
        )
        project_base = context.root / relative_project
        schematic = project_base.with_suffix(".kicad_sch")
        board = project_base.with_suffix(".kicad_pcb")
        shutil.copyfile(schematic_source, schematic)
        shutil.copyfile(board_source, board)
        fixture_config = context.config.model_copy(update={"project": relative_project.as_posix()})
        schematic_hash = digest(schematic)
        board_hash = digest(board)
        source_hashes[f"{case}.schematic"] = schematic_hash
        source_hashes[f"{case}.board"] = board_hash
        retained_netlist: NetlistContract | None = None
        retained_snapshot: PcbConnectivitySnapshot | None = None
        retained_netlist_hash: str | None = None
        retained_snapshot_path: Path | None = None

        for repeat in ("first", "repeat"):
            netlist_path = context.scratch / f"population-{case}.{repeat}.netlist.xml"
            command = runner.export(context.root, fixture_config, netlist_path)
            write_model(
                context.scratch / f"population-{case}.{repeat}.netlist.command.json", command
            )
            if command.returncode != 0 or command.error is not None:
                raise ValueError(
                    f"Native {case} schematic export failed: {command.stderr or command.error}"
                )
            observed_netlist = read_netlist(netlist_path)
            receipt = context.scratch / f"population-{case}.{repeat}.pcb-receipt"
            observed_snapshot = capture_verified_pcb_snapshot(
                context,
                fixture_config,
                receipt,
                expected_board_sha256=board_hash,
                purpose=f"{case} population comparison PCB",
            )
            if observed_snapshot.schema_version != "15":
                raise ValueError("Native population acceptance requires PCB snapshot schema 15")
            if retained_netlist is None:
                retained_netlist = observed_netlist
                retained_snapshot = observed_snapshot
                retained_netlist_hash = digest(netlist_path)
                retained_snapshot_path = receipt / "snapshot.json"
            elif observed_netlist != retained_netlist or observed_snapshot != retained_snapshot:
                repeats_stable = False
                raise ValueError(f"Repeated native {case} population evidence changed")

        if retained_snapshot is None or retained_snapshot_path is None:
            raise ValueError(f"Native {case} population evidence is unavailable")
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
            value_mode="off",
        )
        if coverage.status != "COMPLETE":
            raise ValueError(coverage.issue or f"Native {case} comparison is incomplete")
        mismatch_refs = tuple(item.reference for item in coverage.population_mismatches)
        observed_outcomes[case] = mismatch_refs
        observed_state = (
            "u1" in {reference.casefold() for reference in retained_netlist.dnp_components},
            retained_snapshot.footprints[0].dnp,
        )
        if mismatch_refs != expected_refs or observed_state != expected_state:
            raise ValueError(
                f"Native {case} population result changed: refs={mismatch_refs}, state={observed_state}"
            )
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=f"native-pcb-population-{case}",
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
        finding_refs = tuple(
            item.subject.split(":", maxsplit=1)[0]
            for item in report.findings
            if item.rule_id == "pcb.schematic_pcb_dnp_mismatch"
        )
        expected_status = "REVIEW" if expected_refs else "PASS"
        if finding_refs != expected_refs or report.status != expected_status:
            raise ValueError(
                f"Native {case} design-lint result changed: refs={finding_refs}, status={report.status}"
            )

        required_map = PcbRequiredFittedReferenceMap(
            basis="synthetic native fixture requires U1 in the base assembly",
            requirements=(
                PcbRequiredFittedReference(
                    reference="U1",
                    footprint="Synthetic:Probe_Module",
                    basis="U1 must be fitted for this native fixture",
                ),
            ),
        )
        required_coverage = evaluate_native_component_inventory_coverage(
            retained_netlist,
            retained_snapshot,
            mode="off",
            netlist_sha256=retained_netlist_hash,
            board_path=board.relative_to(context.root).as_posix(),
            board_sha256=board_hash,
            snapshot_path=retained_snapshot_path.relative_to(context.root).as_posix(),
            snapshot_sha256=digest(retained_snapshot_path),
            probe_sha256=retained_snapshot.probe_sha256,
            required_fitted_reference_map=required_map,
            required_fitted_reference_mode="block",
        )
        required_report = evaluate(
            coach.project_id,
            coach,
            DesignLintPolicy(pcb_required_fitted_reference_map=required_map),
            pcb_component_inventory_coverage=required_coverage,
        )
        required_findings = tuple(
            item
            for item in required_report.findings
            if item.rule_id == "pcb.required_fitted_reference"
        )
        required_outcomes[case] = tuple(
            item.subject.split(":", maxsplit=1)[0] for item in required_findings
        )
        if required_findings:
            required_violations[case] = required_findings[0].evidence["violations"]
        else:
            required_violations[case] = ()

    expected_required_outcomes = {
        "board-only-dnp": ("U1",),
        "schematic-only-dnp": ("U1",),
        "both-fitted": (),
        "both-dnp": ("U1",),
    }
    if required_outcomes != expected_required_outcomes:
        raise ValueError(f"Native required fitted-reference results changed: {required_outcomes}")
    if required_violations["both-dnp"] != (
        "schematic_component_dnp",
        "board_footprint_dnp",
    ):
        raise ValueError("Native required fitted-reference check did not catch the both-DNP fault")
    if required_violations["both-fitted"]:
        raise ValueError("Native required fitted-reference control produced a finding")

    log.event(
        "pcb-component-population-fixture/screen",
        "PASS",
        project=context.project,
        kicad_version=context.config.kicad_version,
        board_only_dnp=",".join(observed_outcomes["board-only-dnp"]),
        schematic_only_dnp=",".join(observed_outcomes["schematic-only-dnp"]),
        both_fitted=",".join(observed_outcomes["both-fitted"]),
        both_dnp=",".join(observed_outcomes["both-dnp"]),
        native_evidence_repeated=str(repeats_stable).lower(),
        source_hashes=json.dumps(source_hashes, sort_keys=True),
    )
    log.event(
        "pcb-required-fitted-reference-fixture/screen",
        "PASS",
        project=context.project,
        kicad_version=context.config.kicad_version,
        both_dnp_violations=",".join(required_violations["both-dnp"]),
        both_fitted_violations=",".join(required_violations["both-fitted"]),
        consistency_rule_both_dnp_mismatches=",".join(observed_outcomes["both-dnp"]),
        native_evidence_repeated=str(repeats_stable).lower(),
        source_hashes=json.dumps(source_hashes, sort_keys=True),
    )
