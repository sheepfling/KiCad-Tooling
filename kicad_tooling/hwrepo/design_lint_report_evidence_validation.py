from __future__ import annotations

from collections.abc import Mapping

from .control_input_models import ControlInputBiasHeuristicCoverage
from .design_lint_connectivity_snapshot_models import DesignLintConnectivitySnapshot
from .design_lint_finding_models import DesignLintFinding
from .design_lint_mapped_topology_models import DesignLintMappedCheckRun
from .design_lint_pcb_required_fitted_reference_report import (
    validate_required_fitted_reference_findings,
)
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .model_primitives import Digest, Identifier, RepositoryPath
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport


def validate_source_bound_evidence(
    *,
    project_id: Identifier,
    source_hashes: Mapping[RepositoryPath, Digest],
    netlist_sha256: Digest | None,
    connectivity_snapshot: DesignLintConnectivitySnapshot | None,
    findings: tuple[DesignLintFinding, ...],
    pcb_component_inventory: PcbComponentInventoryCoverageReport,
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage,
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport,
    pcb_touch_pad_clearance_coverage: PcbTouchPadClearanceCoverageReport,
    mapped_check_runs: tuple[DesignLintMappedCheckRun, ...],
) -> None:
    snapshot = connectivity_snapshot
    if snapshot is not None and (
        snapshot.project_id != project_id
        or dict(snapshot.source_hashes) != dict(source_hashes)
        or snapshot.netlist_sha256 != netlist_sha256
    ):
        raise ValueError("Connectivity snapshot must use this report's source-bound netlist")
    inventory = pcb_component_inventory
    if (
        netlist_sha256 is not None
        and inventory.netlist_sha256 is not None
        and inventory.netlist_sha256 != netlist_sha256
    ):
        raise ValueError("PCB component inventory must use this report's native netlist")
    if inventory.status == "COMPLETE":
        expected_findings = len(inventory.missing_placements) + len(inventory.footprint_mismatches)
        actual_findings = sum(
            finding.rule_id == "pcb.schematic_component_inventory" for finding in findings
        )
        if actual_findings != expected_findings:
            raise ValueError("PCB component inventory findings must match its comparison rows")
        expected_population_findings = len(inventory.population_mismatches) + int(
            inventory.variant_population.status == "BLOCKED"
        )
        actual_population_findings = sum(
            finding.rule_id == "pcb.schematic_pcb_dnp_mismatch" for finding in findings
        )
        if actual_population_findings != expected_population_findings:
            raise ValueError("PCB DNP findings must match their comparison rows")
        if inventory.value_comparison_status == "COMPLETE":
            expected_value_findings = len(inventory.value_mismatches)
            actual_value_findings = sum(
                finding.rule_id == "pcb.schematic_pcb_value_mismatch" for finding in findings
            )
            if actual_value_findings != expected_value_findings:
                raise ValueError("PCB value findings must match their comparison rows")
    board_only = inventory.board_only_footprint_coverage
    if board_only.status in {"COMPLETE", "BLOCKED"}:
        expected_board_only_findings = (
            len(board_only.footprints) if board_only.status == "COMPLETE" else 1
        )
        actual_board_only_findings = sum(
            finding.rule_id == "pcb.board_only_footprint" for finding in findings
        )
        if actual_board_only_findings != expected_board_only_findings:
            raise ValueError("Board-only footprint findings must match coverage rows")
    validate_required_fitted_reference_findings(inventory, findings)
    if (
        netlist_sha256 is not None
        and control_input_bias_coverage.netlist_sha256 is not None
        and netlist_sha256 != control_input_bias_coverage.netlist_sha256
    ):
        raise ValueError("Control-input bias coverage must use this report's native netlist")
    if (
        netlist_sha256 is not None
        and i2c_pullup_heuristic_coverage.netlist_sha256 is not None
        and netlist_sha256 != i2c_pullup_heuristic_coverage.netlist_sha256
    ):
        raise ValueError("I2C pull-up coverage must use this report's native netlist")
    if (
        netlist_sha256 is not None
        and pcb_rf_module_antenna_coverage.netlist_sha256 is not None
        and netlist_sha256 != pcb_rf_module_antenna_coverage.netlist_sha256
    ):
        raise ValueError("RF module antenna coverage must use this report's native netlist")
    if (
        netlist_sha256 is not None
        and pcb_touch_pad_clearance_coverage.netlist_sha256 is not None
        and netlist_sha256 != pcb_touch_pad_clearance_coverage.netlist_sha256
    ):
        raise ValueError("Touch-pad clearance coverage must use this report's native netlist")
    touch_clearance = pcb_touch_pad_clearance_coverage
    if touch_clearance.status in {"COMPLETE", "INCOMPLETE", "BLOCKED"}:
        expected_touch_clearance_findings = (
            1
            if touch_clearance.status == "BLOCKED"
            else sum(
                entry.status == "INCOMPLETE" or entry.violates_minimum_clearance
                for entry in touch_clearance.entries
            )
        )
        actual_touch_clearance_findings = sum(
            finding.rule_id == "pcb.touch_pad_reference_clearance" for finding in findings
        )
        if actual_touch_clearance_findings != expected_touch_clearance_findings:
            raise ValueError("Touch-pad clearance findings must match source-bound coverage rows")
    run_ids = [item.rule_id for item in mapped_check_runs]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("Mapped-check execution entries must use unique rule IDs")
    for run in mapped_check_runs:
        if (
            netlist_sha256 is not None
            and run.netlist_sha256 is not None
            and netlist_sha256 != run.netlist_sha256
        ):
            raise ValueError("Mapped-check execution must use this report's native netlist")
        expected_finding_count = sum(finding.rule_id == run.rule_id for finding in findings)
        if run.finding_count != expected_finding_count:
            raise ValueError("Mapped-check execution finding count must match the report findings")
