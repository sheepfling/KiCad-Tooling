"""Coordinate source-bound PCB DRC rule and signal-path coverage scans."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from .evidence import digest
from .models import CommandEvidence, NetlistContract, ProjectConfig
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageEntry,
    PcbDifferentialPairRuleCoverageReport,
    PcbDifferentialPairRuleMap,
    PcbSignalPathRuleCoverageReport,
    PcbSignalPathRuleMap,
)
from .pcb_drc_rule_coverage import compare_native_rules, compare_native_signal_path_rules
from .pcb_drc_source_evidence import (
    source_bound_drc_evidence,
    source_inventory_sha256,
    verify_source_bound_drc_unchanged,
)


def scan_source_bound_rule_map(
    root: Path,
    config: ProjectConfig,
    requirements: PcbDifferentialPairRuleMap,
    observed: NetlistContract,
    source_hashes: dict[str, str],
    native_summary: Path,
    mode: Literal["review", "block", "off"],
) -> PcbDifferentialPairRuleCoverageReport:
    """Read exact KiCad DRC inputs and bind coverage to the native receipt."""
    root = root.resolve()
    requirement_hash = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    if mode == "off":
        return PcbDifferentialPairRuleCoverageReport(
            status="DISABLED", mode="off", map_sha256=requirement_hash
        )
    evidence = source_bound_drc_evidence(root, config, source_hashes, native_summary)
    entries = compare_native_rules(requirements, evidence.rules_source, evidence.ignored_checks)
    net_names = set(observed.nets)
    checked: list[PcbDifferentialPairRuleCoverageEntry] = []
    for entry in entries:
        missing = tuple(
            net for net in (entry.positive_net, entry.negative_net) if net not in net_names
        )
        if missing:
            issues = (
                *entry.issues,
                f"Mapped pair net(s) absent from the source-bound netlist: {', '.join(missing)}.",
            )
            entry = entry.model_copy(update={"status": "INCOMPLETE", "issues": issues})
        checked.append(entry)
    entries = tuple(checked)
    verify_source_bound_drc_unchanged(root, config, source_hashes, evidence)
    return PcbDifferentialPairRuleCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode=mode,
        map_sha256=requirement_hash,
        source_inventory_sha256=source_inventory_sha256(source_hashes),
        project_path=evidence.project_path,
        project_sha256=evidence.project_sha256,
        rules_path=evidence.rules_path,
        rules_sha256=evidence.rules_sha256,
        board_path=evidence.board_path,
        board_sha256=evidence.board_sha256,
        native_summary_path=evidence.native_summary_path,
        native_summary_sha256=digest(evidence.summary_file),
        native_drc_path=evidence.native_drc_path,
        native_drc_sha256=evidence.native_drc_sha256,
        kicad_version=config.kicad_version,
        image=config.image,
        entries=entries,
    )


def scan_source_bound_signal_path_map(
    root: Path,
    config: ProjectConfig,
    requirements: PcbSignalPathRuleMap,
    observed: NetlistContract,
    source_hashes: dict[str, str],
    native_summary: Path,
    snapshot: PcbConnectivitySnapshot,
    snapshot_path: Path,
    snapshot_sha256: str,
    pcb_command: CommandEvidence,
    pcb_command_path: Path,
    pcb_command_sha256: str,
    mode: Literal["review", "block", "off"],
) -> PcbSignalPathRuleCoverageReport:
    """Bind mapped pad paths to both source-bound DRC and exact native copper evidence."""
    root = root.resolve()
    requirement_hash = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    if mode == "off":
        return PcbSignalPathRuleCoverageReport(
            status="DISABLED", mode="off", map_sha256=requirement_hash
        )
    evidence = source_bound_drc_evidence(root, config, source_hashes, native_summary)
    try:
        snapshot_relative = snapshot_path.resolve().relative_to(root).as_posix()
        command_relative = pcb_command_path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(
            "Native PCB snapshot or command is outside the current repository"
        ) from exc
    board_hash = evidence.board_sha256
    if (
        digest(evidence.board_file) != board_hash
        or digest(snapshot_path) != snapshot_sha256
        or digest(pcb_command_path) != pcb_command_sha256
        or snapshot.board_sha256 != board_hash
        or snapshot.kicad_version != config.kicad_version
        or snapshot.zones_refilled is not True
        or pcb_command.error is not None
        or pcb_command.returncode != 0
    ):
        raise ValueError("Native PCB snapshot or command differs from source-bound evidence")
    entries = compare_native_signal_path_rules(
        requirements,
        evidence.rules_source,
        evidence.ignored_checks,
        observed,
        snapshot,
    )
    verify_source_bound_drc_unchanged(root, config, source_hashes, evidence)
    return PcbSignalPathRuleCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode=mode,
        map_sha256=requirement_hash,
        source_inventory_sha256=source_inventory_sha256(source_hashes),
        project_path=evidence.project_path,
        project_sha256=evidence.project_sha256,
        rules_path=evidence.rules_path,
        rules_sha256=evidence.rules_sha256,
        board_path=evidence.board_path,
        board_sha256=evidence.board_sha256,
        native_summary_path=evidence.native_summary_path,
        native_summary_sha256=digest(evidence.summary_file),
        native_drc_path=evidence.native_drc_path,
        native_drc_sha256=evidence.native_drc_sha256,
        pcb_snapshot_path=snapshot_relative,
        pcb_snapshot_sha256=snapshot_sha256,
        pcb_command_path=command_relative,
        pcb_command_sha256=pcb_command_sha256,
        pcb_probe_sha256=snapshot.probe_sha256,
        kicad_version=snapshot.kicad_version,
        image=snapshot.image,
        entries=entries,
    )
