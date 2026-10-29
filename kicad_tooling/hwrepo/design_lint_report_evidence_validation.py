from __future__ import annotations

from collections.abc import Mapping

from .connector_return_distribution_models import ConnectorReturnDistributionCoverageReport
from .control_input_models import ControlInputBiasHeuristicCoverage
from .crystal_network_models import CrystalNetworkCoverageReport
from .design_lint_connectivity_snapshot_models import DesignLintConnectivitySnapshot
from .design_lint_finding_models import DesignLintFinding
from .design_lint_mapped_topology_models import DesignLintMappedCheckRun
from .design_lint_pcb_required_fitted_reference_report import (
    validate_required_fitted_reference_findings,
)
from .i2c_address_models import I2cAddressCoverageReport
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .model_primitives import Digest, Identifier, RepositoryPath
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport
from .rc_filter_models import RcFilterCoverageReport
from .regulator_feedback_models import RegulatorFeedbackCoverageReport


def validate_source_bound_evidence(
    *,
    project_id: Identifier,
    source_hashes: Mapping[RepositoryPath, Digest],
    netlist_sha256: Digest | None,
    connectivity_snapshot: DesignLintConnectivitySnapshot | None,
    findings: tuple[DesignLintFinding, ...],
    findings_complete: bool,
    i2c_address_coverage: I2cAddressCoverageReport,
    crystal_network_coverage: CrystalNetworkCoverageReport,
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport,
    rc_filter_coverage: RcFilterCoverageReport,
    connector_return_distribution: ConnectorReturnDistributionCoverageReport,
    connector_interface_catalog_sha256: Digest | None,
    pcb_component_inventory: PcbComponentInventoryCoverageReport,
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage,
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport,
    pcb_touch_pad_clearance_coverage: PcbTouchPadClearanceCoverageReport,
    mapped_check_runs: tuple[DesignLintMappedCheckRun, ...],
) -> None:
    for name, coverage in (
        ("I2C address", i2c_address_coverage),
        ("Crystal network", crystal_network_coverage),
        ("Regulator feedback", regulator_feedback_coverage),
        ("RC filter", rc_filter_coverage),
        ("Connector return-distribution", connector_return_distribution),
    ):
        _validate_component_coverage_netlist_hash(
            name,
            coverage.status,
            coverage.netlist_sha256,
            netlist_sha256,
            required_statuses=frozenset({"COMPLETE", "INCOMPLETE"}),
        )
    distribution = connector_return_distribution
    if distribution.status in {"COMPLETE", "INCOMPLETE"} and (
        connector_interface_catalog_sha256 is None
        or distribution.interface_catalog_sha256 != connector_interface_catalog_sha256
    ):
        raise ValueError(
            "Connector return-distribution coverage must use this report's interface catalog"
        )
    snapshot = connectivity_snapshot
    if snapshot is not None and (
        snapshot.project_id != project_id
        or dict(snapshot.source_hashes) != dict(source_hashes)
        or snapshot.netlist_sha256 != netlist_sha256
    ):
        raise ValueError("Connectivity snapshot must use this report's source-bound netlist")
    inventory = pcb_component_inventory
    _validate_component_coverage_netlist_hash(
        "PCB component inventory",
        inventory.status,
        inventory.netlist_sha256,
        netlist_sha256,
        required_statuses=frozenset({"COMPLETE"}),
    )
    if findings_complete and inventory.status == "COMPLETE":
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
    if findings_complete and board_only.status in {"COMPLETE", "BLOCKED"}:
        expected_board_only_findings = (
            len(board_only.footprints) if board_only.status == "COMPLETE" else 1
        )
        actual_board_only_findings = sum(
            finding.rule_id == "pcb.board_only_footprint" for finding in findings
        )
        if actual_board_only_findings != expected_board_only_findings:
            raise ValueError("Board-only footprint findings must match coverage rows")
    if findings_complete:
        validate_required_fitted_reference_findings(inventory, findings)
    _validate_component_coverage_netlist_hash(
        "Control-input bias",
        control_input_bias_coverage.status,
        control_input_bias_coverage.netlist_sha256,
        netlist_sha256,
        required_statuses=frozenset({"COMPLETE", "OPEN"}),
    )
    _validate_component_coverage_netlist_hash(
        "I2C pull-up",
        i2c_pullup_heuristic_coverage.status,
        i2c_pullup_heuristic_coverage.netlist_sha256,
        netlist_sha256,
        required_statuses=frozenset({"COMPLETE", "OPEN"}),
    )
    _validate_component_coverage_netlist_hash(
        "RF module antenna",
        pcb_rf_module_antenna_coverage.status,
        pcb_rf_module_antenna_coverage.netlist_sha256,
        netlist_sha256,
        required_statuses=frozenset({"COMPLETE", "INCOMPLETE"}),
    )
    _validate_component_coverage_netlist_hash(
        "Touch-pad clearance",
        pcb_touch_pad_clearance_coverage.status,
        pcb_touch_pad_clearance_coverage.netlist_sha256,
        netlist_sha256,
        required_statuses=frozenset({"COMPLETE", "INCOMPLETE"}),
    )
    touch_clearance = pcb_touch_pad_clearance_coverage
    if findings_complete and touch_clearance.status in {"COMPLETE", "INCOMPLETE", "BLOCKED"}:
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
        _validate_component_coverage_netlist_hash(
            "Mapped-check execution",
            run.status,
            run.netlist_sha256,
            netlist_sha256,
            required_statuses=frozenset({"EVALUATED"}),
        )
        expected_finding_count = sum(finding.rule_id == run.rule_id for finding in findings)
        if findings_complete and run.finding_count != expected_finding_count:
            raise ValueError("Mapped-check execution finding count must match the report findings")


def _validate_component_coverage_netlist_hash(
    name: str,
    status: str,
    coverage_netlist_sha256: Digest | None,
    report_netlist_sha256: Digest | None,
    *,
    required_statuses: frozenset[str],
) -> None:
    if coverage_netlist_sha256 is None and status not in required_statuses:
        return
    if report_netlist_sha256 is None or coverage_netlist_sha256 != report_netlist_sha256:
        raise ValueError(f"{name} coverage must use this report's native netlist")
