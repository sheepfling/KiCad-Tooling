"""Source-bound project inspection orchestration for design lint."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from ..validate import hashes
from .contract_coach import inspect_summary as inspect_contract_summary
from .contracts import read_model, repo_path
from .design_lint_connector_coverage import (
    connector_coverage_from_project,
    external_protection_coverage_from_project,
)
from .design_lint_pcb_geometry_scan import scan_pcb_geometry
from .design_lint_project_contexts import (
    control_input_bias_coverage_from_project,
    i2c_pullup_coverage_from_project,
    serial_peer_roster_context,
    spi_roster_context,
    usb_c_port_roster_context,
)
from .design_lint_project_contexts import (
    digital_peer_voltage_context as build_digital_peer_voltage_context,
)
from .design_lint_schematic_coverage import scan_schematic_geometry
from .design_lint_stm32_coverage import scan_stm32_pin_maps
from .discovery import load_config, load_registry
from .evidence import digest
from .models import (
    ControlInputBiasHeuristicCoverage,
    DesignLintPolicy,
    DesignLintReport,
    I2cPullupHeuristicCoverage,
    ProjectManifest,
)
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageReport,
    PcbDifferentialPairRuleMap,
)
from .pcb_drc_source_scan import scan_source_bound_rule_map


def inspect_design_lint_summary(
    root: Path,
    project_id: str,
    native_summary: Path,
    evaluate_report: Callable[..., DesignLintReport],
) -> DesignLintReport:
    """Read the exact native source and the current project-owned lint decisions."""
    root = root.resolve()
    coach = inspect_contract_summary(root, project_id, native_summary)
    try:
        project = next(item for item in load_registry(root).projects if item.id == project_id)
        manifest_path = repo_path(root, project.config)
        manifest_hash = digest(manifest_path)
        manifest = read_model(manifest_path, ProjectManifest)
        policy_path = repo_path(manifest_path.parent, manifest.checks)
        policy_hash = digest(policy_path)
        config = load_config(root, project.config)
        policy = config.design_lint or DesignLintPolicy()
        if coach.status != "READY_FOR_REVIEW" or coach.observed is None:
            report = evaluate_report(project_id, coach, policy)
            if digest(manifest_path) != manifest_hash or digest(policy_path) != policy_hash:
                raise ValueError("Project manifest or lint policy changed during inspection")
            return report.model_copy(
                update={
                    "project_manifest_sha256": manifest_hash,
                    "policy_path": policy_path.relative_to(root).as_posix(),
                    "policy_sha256": policy_hash,
                }
            )
        if hashes(root, config.source_roots) != coach.source_hashes:
            raise ValueError("Declared source changed while reading design-lint policy")
        spi_roster = spi_roster_context(root, config)
        serial_peer_roster = serial_peer_roster_context(root, config)
        digital_peer_voltage_context = build_digital_peer_voltage_context(root, config)
        usb_c_port_roster = usb_c_port_roster_context(root, config)
        geometry_scan, geometry_coverage = scan_schematic_geometry(root, config, coach, policy)
        (
            pcb_decoupling_coverage,
            pcb_protection_path_coverage,
            pcb_track_width_coverage,
            pcb_reference_plane_coverage,
            pcb_switching_loop_coverage,
            pcb_signal_path_coverage,
            pcb_keepout_coverage,
            pcb_rf_module_antenna_coverage,
        ) = scan_pcb_geometry(root, config, coach, policy, native_summary)
        pair_map: PcbDifferentialPairRuleMap | None = policy.pcb_differential_pair_rule_map
        pair_override = next(
            (
                item
                for item in policy.rules
                if item.rule_id == "pcb.differential_pair_rule_coverage"
            ),
            None,
        )
        pair_mode: Literal["review", "block", "off"] = (
            "review" if pair_override is None else pair_override.mode
        )
        if pair_map is None:
            pair_rule_coverage = PcbDifferentialPairRuleCoverageReport()
        elif pair_mode == "off":
            pair_rule_coverage = PcbDifferentialPairRuleCoverageReport(
                status="DISABLED",
                mode=pair_mode,
                map_sha256=hashlib.sha256(pair_map.model_dump_json().encode("utf-8")).hexdigest(),
            )
        else:
            try:
                pair_rule_coverage = scan_source_bound_rule_map(
                    root,
                    config,
                    pair_map,
                    coach.observed,
                    dict(coach.source_hashes),
                    native_summary,
                    pair_mode,
                )
            except (OSError, ValueError, TypeError) as exc:
                pair_rule_coverage = PcbDifferentialPairRuleCoverageReport(
                    status="BLOCKED",
                    mode=pair_mode,
                    map_sha256=hashlib.sha256(
                        pair_map.model_dump_json().encode("utf-8")
                    ).hexdigest(),
                    issue=f"Could not verify source-bound differential-pair DRC rule coverage: {exc}",
                )
        coverage = connector_coverage_from_project(root, config, coach.observed)
        stm32_pin_map_coverage = scan_stm32_pin_maps(
            root,
            policy,
            coach.observed,
            coach.netlist_sha256,
        )
        control_bias_coverage = (
            control_input_bias_coverage_from_project(
                root,
                config,
                coach.observed,
                coach.netlist_sha256,
            )
            if coach.netlist_sha256 is not None
            else ControlInputBiasHeuristicCoverage(
                status="BLOCKED",
                issue="Native netlist hash is unavailable for control-input bias review.",
            )
        )
        i2c_pullup_coverage = (
            i2c_pullup_coverage_from_project(
                root,
                config,
                coach.observed,
                coach.netlist_sha256,
            )
            if coach.netlist_sha256 is not None
            else I2cPullupHeuristicCoverage(
                status="BLOCKED",
                issue="Native netlist hash is unavailable for I2C pull-up review.",
            )
        )
        protection_coverage = external_protection_coverage_from_project(
            root,
            config,
            policy,
            coach.observed,
            coverage,
            coach.netlist_sha256,
        )
        report = evaluate_report(
            project_id,
            coach,
            policy,
            connector_coverage=coverage,
            schematic_geometry=geometry_scan,
            geometry_coverage=geometry_coverage,
            external_protection_coverage=protection_coverage,
            pcb_decoupling_coverage=pcb_decoupling_coverage,
            pcb_protection_path_coverage=pcb_protection_path_coverage,
            pcb_track_width_coverage=pcb_track_width_coverage,
            pcb_reference_plane_coverage=pcb_reference_plane_coverage,
            pcb_switching_loop_coverage=pcb_switching_loop_coverage,
            pcb_differential_pair_coverage=pair_rule_coverage,
            pcb_signal_path_coverage=pcb_signal_path_coverage,
            pcb_keepout_coverage=pcb_keepout_coverage,
            pcb_rf_module_antenna_coverage=pcb_rf_module_antenna_coverage,
            stm32_pin_map_coverage=stm32_pin_map_coverage,
            spi_roster=spi_roster,
            serial_peer_roster=serial_peer_roster,
            usb_c_port_roster=usb_c_port_roster,
            control_input_bias_coverage=control_bias_coverage,
            i2c_pullup_heuristic_coverage=i2c_pullup_coverage,
            digital_peer_voltage_context=digital_peer_voltage_context,
        )
        connector_catalog = report.connector_coverage
        if (
            digest(manifest_path) != manifest_hash
            or digest(policy_path) != policy_hash
            or (
                connector_catalog is not None
                and connector_catalog.interface_catalog_path is not None
                and connector_catalog.interface_catalog_sha256 is not None
                and digest(repo_path(root, connector_catalog.interface_catalog_path))
                != connector_catalog.interface_catalog_sha256
            )
            or (
                protection_coverage.electrical_contract_path is not None
                and digest(repo_path(root, protection_coverage.electrical_contract_path))
                != protection_coverage.electrical_contract_sha256
            )
            or any(
                digest(repo_path(root, source_path)) != source_sha256
                for source_path, source_sha256 in stm32_pin_map_coverage.ioc_source_hashes.items()
            )
            or (
                spi_roster.source_path is not None
                and digest(repo_path(root, spi_roster.source_path)) != spi_roster.source_sha256
            )
            or (
                serial_peer_roster.source_path is not None
                and digest(repo_path(root, serial_peer_roster.source_path))
                != serial_peer_roster.source_sha256
            )
            or (
                digital_peer_voltage_context.source_path is not None
                and digest(repo_path(root, digital_peer_voltage_context.source_path))
                != digital_peer_voltage_context.source_sha256
            )
            or (
                usb_c_port_roster.source_path is not None
                and digest(repo_path(root, usb_c_port_roster.source_path))
                != usb_c_port_roster.source_sha256
            )
            or (
                control_bias_coverage.source_path is not None
                and digest(repo_path(root, control_bias_coverage.source_path))
                != control_bias_coverage.source_sha256
            )
            or (
                i2c_pullup_coverage.source_path is not None
                and digest(repo_path(root, i2c_pullup_coverage.source_path))
                != i2c_pullup_coverage.source_sha256
            )
        ):
            raise ValueError("Project manifest or lint policy changed during inspection")
        return report.model_copy(
            update={
                "project_manifest_sha256": manifest_hash,
                "policy_path": policy_path.relative_to(root).as_posix(),
                "policy_sha256": policy_hash,
            }
        )
    except (OSError, ValueError, StopIteration) as exc:
        return DesignLintReport(
            status="BLOCKED",
            project_id=project_id,
            native_summary=coach.native_summary,
            native_status=coach.native_status,
            issues=(str(exc),),
            next_actions=("Repair the project-owned policy or source inventory, then rerun lint.",),
        )
