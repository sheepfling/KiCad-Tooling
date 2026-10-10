"""Source-bound schematic geometry capture and rule coverage."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from .contract_coach import ContractCoachReport
from .contracts import repo_path
from .discovery import ProjectConfig
from .models import (
    DesignLintPolicy,
    SchematicGeometryCoverage,
    SchematicGeometryRuleCoverageStatus,
    SchematicGeometryRuleId,
    SchematicGeometrySourceBinding,
)
from .schematic_geometry import (
    MAX_SHEET_OCCURRENCES,
    SchematicGeometryScan,
    resolve_schematic_sheet_path,
    scan_schematic_geometry_tree,
    schematic_sheet_references,
)

SCHEMATIC_GEOMETRY_RULE_IDS: tuple[SchematicGeometryRuleId, ...] = (
    "schematic.wire_end_on_pin_line",
    "schematic.pin_tip_on_wire_interior",
    "schematic.wire_endpoint_near_pin_tip",
    "schematic.label_near_wire_endpoint",
    "schematic.unmarked_wire_crossing",
    "schematic.unmarked_t_junction",
    "schematic.coincident_text_anchors",
    "schematic.free_text_overlap",
    "schematic.free_text_over_wire",
    "schematic.free_text_over_symbol_body",
    "schematic.wire_through_symbol_body",
)


def schematic_geometry_coverage(
    scan: SchematicGeometryScan,
    netlist_sha256: str | None,
    rule_modes: Mapping[SchematicGeometryRuleId, Literal["review", "block", "off"]],
) -> SchematicGeometryCoverage:
    """Report completeness only for the schematic geometry rules the project enabled."""
    counts = {
        "schematic.wire_end_on_pin_line": len(scan.findings),
        "schematic.pin_tip_on_wire_interior": len(scan.pin_tip_on_wire_interiors),
        "schematic.wire_endpoint_near_pin_tip": len(scan.wire_endpoints_near_pin_tips),
        "schematic.label_near_wire_endpoint": len(scan.labels_near_wire_endpoints),
        "schematic.unmarked_wire_crossing": len(scan.unmarked_wire_crossings),
        "schematic.unmarked_t_junction": len(scan.unmarked_t_junctions),
        "schematic.coincident_text_anchors": len(scan.coincident_text_anchors),
        "schematic.free_text_overlap": len(scan.free_text_overlaps),
        "schematic.free_text_over_wire": len(scan.free_text_wire_overlaps),
        "schematic.free_text_over_symbol_body": len(scan.free_text_symbol_body_overlaps),
        "schematic.wire_through_symbol_body": len(scan.wires_through_symbol_bodies),
    }
    rule_coverage: dict[SchematicGeometryRuleId, SchematicGeometryRuleCoverageStatus] = {}
    active_issues: dict[SchematicGeometryRuleId, tuple[str, ...]] = {}
    for rule_id in SCHEMATIC_GEOMETRY_RULE_IDS:
        mode = rule_modes[rule_id]
        if mode == "off":
            rule_coverage[rule_id] = "DISABLED"
            continue
        issues = scan.unsupported_by_rule.get(rule_id, ())
        if not scan.unsupported_by_rule and scan.status in {"PARTIAL", "UNSUPPORTED"}:
            issues = scan.unsupported
        if scan.status == "UNSUPPORTED":
            rule_coverage[rule_id] = "UNSUPPORTED"
            active_issues[rule_id] = issues or scan.unsupported
        elif issues:
            rule_coverage[rule_id] = "PARTIAL"
            active_issues[rule_id] = issues
        else:
            rule_coverage[rule_id] = "COMPLETE"

    active_rules: tuple[SchematicGeometryRuleId, ...] = tuple(
        rule_id for rule_id in SCHEMATIC_GEOMETRY_RULE_IDS if rule_modes[rule_id] != "off"
    )
    active_statuses = tuple(rule_coverage[rule_id] for rule_id in active_rules)
    status: Literal["COMPLETE", "PARTIAL", "UNSUPPORTED", "DISABLED"] = (
        "DISABLED"
        if not active_rules
        else "UNSUPPORTED"
        if "UNSUPPORTED" in active_statuses
        else "PARTIAL"
        if "PARTIAL" in active_statuses
        else "COMPLETE"
    )
    mode: Literal["review", "block", "off"] = (
        "off"
        if not active_rules
        else "block"
        if any(rule_modes[rule_id] == "block" for rule_id in active_rules)
        else "review"
    )
    return SchematicGeometryCoverage(
        status=status,
        mode=mode,
        rule_modes=rule_modes,
        rule_coverage=rule_coverage,
        unsupported_by_rule=active_issues,
        source_path=scan.source_path,
        source_sha256=scan.source_sha256,
        source_tree_sha256=scan.source_tree_sha256,
        source_bindings=tuple(
            SchematicGeometrySourceBinding(
                source_path=item.source_path,
                source_sha256=item.source_sha256,
                sheet_instance_path=item.sheet_instance_path,
                sheet_path=item.sheet_path,
            )
            for item in scan.source_bindings
        ),
        netlist_sha256=netlist_sha256,
        kicad_version=scan.kicad_version,
        schematic_version=scan.schematic_version,
        finding_count=sum(counts.values()),
        unsupported=tuple(sorted({issue for issues in active_issues.values() for issue in issues})),
    )


def scan_schematic_geometry(
    root: Path,
    config: ProjectConfig,
    coach: ContractCoachReport,
    policy: DesignLintPolicy,
) -> tuple[SchematicGeometryScan | None, SchematicGeometryCoverage]:
    """Run geometry only for explicit project opt-in and bind it to native evidence."""
    geometry_rule_ids = SCHEMATIC_GEOMETRY_RULE_IDS
    overrides = {item.rule_id: item for item in policy.rules if item.rule_id in geometry_rule_ids}
    if not overrides:
        return None, SchematicGeometryCoverage()
    rule_modes: dict[SchematicGeometryRuleId, Literal["review", "block", "off"]] = {
        rule_id: overrides[rule_id].mode if rule_id in overrides else "off"
        for rule_id in geometry_rule_ids
    }
    active_modes = tuple(mode for mode in rule_modes.values() if mode != "off")
    if not active_modes:
        return None, SchematicGeometryCoverage(
            status="DISABLED",
            mode="off",
            rule_modes=rule_modes,
            rule_coverage={rule_id: "DISABLED" for rule_id in geometry_rule_ids},
        )
    mode: Literal["review", "block"] = "block" if "block" in active_modes else "review"

    relative_path: str | None = None
    expected_source_hash: str | None = None
    try:
        schematic_relative = Path(config.project).with_suffix(".kicad_sch").as_posix()
        if coach.netlist_sha256 is None or coach.observed is None:
            raise ValueError("Source-bound native netlist evidence is unavailable")
        source_path = repo_path(root, schematic_relative)
        relative_path = source_path.relative_to(root).as_posix()
        project_directory = source_path.parent.relative_to(root).as_posix()
        expected_source_hash = coach.source_hashes.get(relative_path)
        if expected_source_hash is None:
            raise ValueError(
                "Primary schematic is absent from the source-bound native summary hashes"
            )

        source_files: dict[str, bytes] = {}
        pending = [relative_path]
        while pending:
            current_path = pending.pop()
            if current_path in source_files:
                continue
            if len(source_files) >= MAX_SHEET_OCCURRENCES:
                raise ValueError(
                    f"Schematic source tree exceeds {MAX_SHEET_OCCURRENCES} unique files"
                )
            current_file = repo_path(root, current_path)
            expected_hash = coach.source_hashes.get(current_path)
            if expected_hash is None:
                raise ValueError(
                    "Referenced hierarchical schematic is absent from the "
                    f"source-bound native summary hashes: {current_path}"
                )
            source = current_file.read_bytes()
            actual_hash = hashlib.sha256(source).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(
                    f"Schematic differs from the source-bound native summary: {current_path}"
                )
            source_files[current_path] = source
            for sheet in schematic_sheet_references(source):
                child_path = resolve_schematic_sheet_path(
                    current_path,
                    project_directory,
                    sheet.file,
                )
                repo_path(root, child_path)
                if child_path not in source_files:
                    pending.append(child_path)

        unconnected_pins = frozenset(
            pin for pins in coach.observed.unconnected_nets.values() for pin in pins
        )
        scan = scan_schematic_geometry_tree(
            source_files,
            root_path=relative_path,
            project_directory=project_directory,
            project_name=source_path.stem,
            kicad_version=config.kicad_version,
            unconnected_pins=unconnected_pins,
        )
        if any(
            binding.source_path not in source_files
            or hashlib.sha256(source_files[binding.source_path]).hexdigest()
            != binding.source_sha256
            for binding in scan.source_bindings
        ):
            raise ValueError("Geometry scan returned an unbound hierarchical source instance")
        if scan.source_sha256 != expected_source_hash:
            raise ValueError("Geometry scan source hash differs from native source evidence")
        coverage = schematic_geometry_coverage(scan, coach.netlist_sha256, rule_modes)
        return scan, coverage
    except (OSError, ValueError, TypeError) as exc:
        return None, SchematicGeometryCoverage(
            status="BLOCKED",
            mode=mode,
            rule_modes=rule_modes,
            source_path=relative_path,
            source_sha256=expected_source_hash,
            netlist_sha256=coach.netlist_sha256,
            kicad_version=config.kicad_version,
            issue=f"Could not bind schematic geometry to native evidence: {exc}",
        )
