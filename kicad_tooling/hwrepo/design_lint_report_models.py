"""Typed design-lint report output model."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field, model_validator

from .can_peer_reference_models import CanPeerReferenceCoverageReport
from .component_peer_pin_models import ComponentPeerPinRuleCoverage
from .connector_coverage_models import ConnectorCoverageReport
from .connector_peer_pin_models import ConnectorPeerPinHeuristicCoverage
from .connector_return_distribution_models import ConnectorReturnDistributionCoverageReport
from .control_input_models import ControlInputBiasHeuristicCoverage
from .crystal_network_models import CrystalNetworkCoverageReport
from .design_lint_connectivity_snapshot_models import DesignLintConnectivitySnapshot
from .design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from .design_lint_mapped_topology_models import DesignLintMappedCheckRun
from .design_lint_pcb_required_fitted_reference_report import (
    validate_required_fitted_reference_findings,
)
from .design_lint_rule_models import DesignLintRuleCatalog
from .digital_peer_voltage_models import DigitalPeerVoltageRuleCoverage
from .external_protection_models import ExternalProtectionCoverageReport
from .i2c_address_models import I2cAddressCoverageReport
from .i2c_peer_reference_models import I2cPeerReferenceCoverageReport
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel
from .models import register_design_lint_report
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import PcbDifferentialPairRuleCoverageReport, PcbSignalPathRuleCoverageReport
from .pcb_keepout_models import (
    PcbKeepoutCoverageReport,
)
from .pcb_protection_path_models import PcbProtectionPathCoverageReport
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import PcbSwitchingLoopCoverageReport
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport
from .pcb_track_width_models import PcbTrackWidthCoverageReport
from .rc_filter_models import RcFilterCoverageReport
from .regulator_feedback_models import RegulatorFeedbackCoverageReport
from .rs485_peer_reference_models import Rs485PeerReferenceCoverageReport
from .schematic_geometry_models import SchematicGeometryCoverage
from .serial_peer_reference_models import SerialPeerReferenceCoverageReport
from .spi_peer_reference_models import SpiPeerReferenceCoverageReport
from .stm32_pin_map_models import Stm32PinMapCoverageReport
from .usb_peer_reference_models import UsbPeerReferenceCoverageReport


class DesignLintReport(StrictModel):
    """Source-bound heuristic findings; neither a pinout nor electrical approval."""

    schema_version: Literal["1", "2", "3", "4", "5"] = "5"
    lane: Literal["DESIGN_LINT"] = "DESIGN_LINT"
    status: Literal["PASS", "REVIEW", "FAIL", "BLOCKED"]
    project_id: Identifier
    review_state: Literal["HEURISTIC"] = "HEURISTIC"
    build_authorized: Literal[False] = False
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    netlist_sha256: Digest | None = None
    connectivity_snapshot: DesignLintConnectivitySnapshot | None = None
    native_summary: str | None = None
    native_status: Literal["PASS", "FAIL"] | None = None
    rule_catalog: DesignLintRuleCatalog | None = None
    project_manifest_sha256: Digest | None = None
    policy_path: RepositoryPath | None = None
    policy_sha256: Digest | None = None
    findings: tuple[DesignLintFinding, ...] = ()
    mapped_check_runs: tuple[DesignLintMappedCheckRun, ...] = ()
    digital_peer_voltage_coverage: tuple[DigitalPeerVoltageRuleCoverage, ...] = ()
    component_peer_pin_coverage: tuple[ComponentPeerPinRuleCoverage, ...] = ()
    usb_peer_reference_coverage: UsbPeerReferenceCoverageReport | None = None
    serial_peer_reference_coverage: SerialPeerReferenceCoverageReport | None = None
    i2c_peer_reference_coverage: I2cPeerReferenceCoverageReport | None = None
    spi_peer_reference_coverage: SpiPeerReferenceCoverageReport | None = None
    can_peer_reference_coverage: CanPeerReferenceCoverageReport | None = None
    rs485_peer_reference_coverage: Rs485PeerReferenceCoverageReport | None = None
    connector_peer_pin_coverage: ConnectorPeerPinHeuristicCoverage | None = None
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage = Field(
        default_factory=ControlInputBiasHeuristicCoverage
    )
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage = Field(
        default_factory=I2cPullupHeuristicCoverage
    )
    connector_coverage: ConnectorCoverageReport | None = None
    stm32_pin_map_coverage: Stm32PinMapCoverageReport = Field(
        default_factory=Stm32PinMapCoverageReport
    )
    schematic_geometry: SchematicGeometryCoverage = Field(default_factory=SchematicGeometryCoverage)
    i2c_address_coverage: I2cAddressCoverageReport = Field(default_factory=I2cAddressCoverageReport)
    external_protection_coverage: ExternalProtectionCoverageReport = Field(
        default_factory=ExternalProtectionCoverageReport
    )
    crystal_network_coverage: CrystalNetworkCoverageReport = Field(
        default_factory=CrystalNetworkCoverageReport
    )
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport = Field(
        default_factory=RegulatorFeedbackCoverageReport
    )
    rc_filter_coverage: RcFilterCoverageReport = Field(default_factory=RcFilterCoverageReport)
    connector_return_distribution: ConnectorReturnDistributionCoverageReport = Field(
        default_factory=ConnectorReturnDistributionCoverageReport
    )
    pcb_decoupling: PcbDecouplingCoverageReport = Field(default_factory=PcbDecouplingCoverageReport)
    pcb_component_inventory: PcbComponentInventoryCoverageReport = Field(
        default_factory=PcbComponentInventoryCoverageReport
    )
    pcb_protection_path: PcbProtectionPathCoverageReport = Field(
        default_factory=PcbProtectionPathCoverageReport
    )
    pcb_track_width: PcbTrackWidthCoverageReport = Field(
        default_factory=PcbTrackWidthCoverageReport
    )
    pcb_reference_plane: PcbReferencePlaneCoverageReport = Field(
        default_factory=PcbReferencePlaneCoverageReport
    )
    pcb_switching_loop: PcbSwitchingLoopCoverageReport = Field(
        default_factory=PcbSwitchingLoopCoverageReport
    )
    pcb_differential_pair_rules: PcbDifferentialPairRuleCoverageReport = Field(
        default_factory=PcbDifferentialPairRuleCoverageReport
    )
    pcb_signal_path_rules: PcbSignalPathRuleCoverageReport = Field(
        default_factory=PcbSignalPathRuleCoverageReport
    )
    pcb_keepout_coverage: PcbKeepoutCoverageReport = Field(default_factory=PcbKeepoutCoverageReport)
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport = Field(
        default_factory=PcbRfModuleAntennaCoverageReport
    )
    pcb_touch_pad_clearance_coverage: PcbTouchPadClearanceCoverageReport = Field(
        default_factory=PcbTouchPadClearanceCoverageReport
    )
    stale_ignores: tuple[DesignLintIgnore, ...] = ()
    rule_overrides: tuple[DesignLintRuleOverride, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def findings_are_catalogued(self) -> DesignLintReport:
        snapshot = self.connectivity_snapshot
        if snapshot is not None and (
            snapshot.project_id != self.project_id
            or dict(snapshot.source_hashes) != dict(self.source_hashes)
            or snapshot.netlist_sha256 != self.netlist_sha256
        ):
            raise ValueError("Connectivity snapshot must use this report's source-bound netlist")
        inventory = self.pcb_component_inventory
        if (
            self.netlist_sha256 is not None
            and inventory.netlist_sha256 is not None
            and inventory.netlist_sha256 != self.netlist_sha256
        ):
            raise ValueError("PCB component inventory must use this report's native netlist")
        if inventory.status == "COMPLETE":
            expected_findings = len(inventory.missing_placements) + len(
                inventory.footprint_mismatches
            )
            actual_findings = sum(
                finding.rule_id == "pcb.schematic_component_inventory" for finding in self.findings
            )
            if actual_findings != expected_findings:
                raise ValueError("PCB component inventory findings must match its comparison rows")
            expected_population_findings = len(inventory.population_mismatches) + int(
                inventory.variant_population.status == "BLOCKED"
            )
            actual_population_findings = sum(
                finding.rule_id == "pcb.schematic_pcb_dnp_mismatch" for finding in self.findings
            )
            if actual_population_findings != expected_population_findings:
                raise ValueError("PCB DNP findings must match their comparison rows")
            if inventory.value_comparison_status == "COMPLETE":
                expected_value_findings = len(inventory.value_mismatches)
                actual_value_findings = sum(
                    finding.rule_id == "pcb.schematic_pcb_value_mismatch"
                    for finding in self.findings
                )
                if actual_value_findings != expected_value_findings:
                    raise ValueError("PCB value findings must match their comparison rows")
        board_only = inventory.board_only_footprint_coverage
        if board_only.status in {"COMPLETE", "BLOCKED"}:
            expected_board_only_findings = (
                len(board_only.footprints) if board_only.status == "COMPLETE" else 1
            )
            actual_board_only_findings = sum(
                finding.rule_id == "pcb.board_only_footprint" for finding in self.findings
            )
            if actual_board_only_findings != expected_board_only_findings:
                raise ValueError("Board-only footprint findings must match coverage rows")
        validate_required_fitted_reference_findings(inventory, self.findings)
        if (
            self.netlist_sha256 is not None
            and self.control_input_bias_coverage.netlist_sha256 is not None
            and self.netlist_sha256 != self.control_input_bias_coverage.netlist_sha256
        ):
            raise ValueError("Control-input bias coverage must use this report's native netlist")
        if (
            self.netlist_sha256 is not None
            and self.i2c_pullup_heuristic_coverage.netlist_sha256 is not None
            and self.netlist_sha256 != self.i2c_pullup_heuristic_coverage.netlist_sha256
        ):
            raise ValueError("I2C pull-up coverage must use this report's native netlist")
        if (
            self.netlist_sha256 is not None
            and self.pcb_rf_module_antenna_coverage.netlist_sha256 is not None
            and self.netlist_sha256 != self.pcb_rf_module_antenna_coverage.netlist_sha256
        ):
            raise ValueError("RF module antenna coverage must use this report's native netlist")
        if (
            self.netlist_sha256 is not None
            and self.pcb_touch_pad_clearance_coverage.netlist_sha256 is not None
            and self.netlist_sha256 != self.pcb_touch_pad_clearance_coverage.netlist_sha256
        ):
            raise ValueError("Touch-pad clearance coverage must use this report's native netlist")
        touch_clearance = self.pcb_touch_pad_clearance_coverage
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
                finding.rule_id == "pcb.touch_pad_reference_clearance" for finding in self.findings
            )
            if actual_touch_clearance_findings != expected_touch_clearance_findings:
                raise ValueError(
                    "Touch-pad clearance findings must match source-bound coverage rows"
                )
        run_ids = [item.rule_id for item in self.mapped_check_runs]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("Mapped-check execution entries must use unique rule IDs")
        for run in self.mapped_check_runs:
            if (
                self.netlist_sha256 is not None
                and run.netlist_sha256 is not None
                and self.netlist_sha256 != run.netlist_sha256
            ):
                raise ValueError("Mapped-check execution must use this report's native netlist")
            expected_finding_count = sum(
                finding.rule_id == run.rule_id for finding in self.findings
            )
            if run.finding_count != expected_finding_count:
                raise ValueError(
                    "Mapped-check execution finding count must match the report findings"
                )
        voltage_coverage_ids = [item.rule_id for item in self.digital_peer_voltage_coverage]
        if len(voltage_coverage_ids) != len(set(voltage_coverage_ids)):
            raise ValueError("Digital-peer voltage coverage entries must use unique rule IDs")
        for item in self.digital_peer_voltage_coverage:
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("Digital-peer voltage coverage must use this report's netlist")
            expected_groups = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.candidate_group_count != expected_groups:
                raise ValueError("Digital-peer voltage candidate counts must match report findings")
        component_peer_pin_rule_ids = [item.rule_id for item in self.component_peer_pin_coverage]
        if len(component_peer_pin_rule_ids) != len(set(component_peer_pin_rule_ids)):
            raise ValueError("Component peer-pin coverage entries must use unique rule IDs")
        expected_component_peer_pin_rule_ids = {
            "component.peer_power_output_unconnected",
            "component.peer_signal_output_unconnected",
            "component.peer_signal_input_unconnected",
            "component.peer_bidirectional_pin_unconnected",
            "component.peer_power_input_assignment_divergence",
            "component.peer_power_input_named_assignment_divergence",
            "component.peer_power_input_named_all_open",
            "component.peer_power_input_open_assignment",
            "component.generic_peer_pin_assignment_outlier",
            "component.generic_peer_pin_mixed_open",
            "component.generic_peer_pin_all_open",
        }
        if component_peer_pin_rule_ids and set(component_peer_pin_rule_ids) != (
            expected_component_peer_pin_rule_ids
        ):
            raise ValueError("Component peer-pin coverage must include every supported rule")
        for item in self.component_peer_pin_coverage:
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("Component peer-pin coverage must use this report's netlist")
            expected_findings = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.finding_count != expected_findings:
                raise ValueError("Component peer-pin findings must match report findings")
        if self.usb_peer_reference_coverage is not None:
            item = self.usb_peer_reference_coverage
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("USB peer-reference coverage must use this report's netlist")
            expected_groups = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.candidate_group_count != expected_groups:
                raise ValueError("USB peer-reference candidate counts must match report findings")
        if self.serial_peer_reference_coverage is not None:
            item = self.serial_peer_reference_coverage
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("Serial peer-reference coverage must use this report's netlist")
            expected_groups = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.candidate_group_count != expected_groups:
                raise ValueError(
                    "Serial peer-reference candidate counts must match report findings"
                )
        if self.i2c_peer_reference_coverage is not None:
            item = self.i2c_peer_reference_coverage
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("I2C peer-reference coverage must use this report's netlist")
            expected_groups = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.candidate_group_count != expected_groups:
                raise ValueError("I2C peer-reference candidate counts must match report findings")
        if self.spi_peer_reference_coverage is not None:
            item = self.spi_peer_reference_coverage
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("SPI peer-reference coverage must use this report's netlist")
            expected_groups = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.candidate_group_count != expected_groups:
                raise ValueError("SPI peer-reference candidate counts must match report findings")
        if self.can_peer_reference_coverage is not None:
            item = self.can_peer_reference_coverage
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("CAN peer-reference coverage must use this report's netlist")
            expected_groups = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.candidate_group_count != expected_groups:
                raise ValueError("CAN peer-reference candidate counts must match report findings")
        if self.rs485_peer_reference_coverage is not None:
            item = self.rs485_peer_reference_coverage
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError("RS-485 peer-reference coverage must use this report's netlist")
            expected_groups = sum(finding.rule_id == item.rule_id for finding in self.findings)
            if item.candidate_group_count != expected_groups:
                raise ValueError(
                    "RS-485 peer-reference candidate counts must match report findings"
                )
        if self.connector_peer_pin_coverage is not None:
            item = self.connector_peer_pin_coverage
            if self.netlist_sha256 is not None and item.netlist_sha256 != self.netlist_sha256:
                raise ValueError(
                    "Connector peer-pin coverage must use this report's native netlist"
                )
            expected_counts = (
                (
                    "connector.repeated_pin_function",
                    item.repeated_function_finding_count,
                ),
                (
                    "connector.peer_pin_assignment_outlier",
                    item.peer_pin_outlier_finding_count,
                ),
                (
                    "connector.peer_pin_assignment_divergence",
                    item.peer_pin_divergence_finding_count,
                ),
                (
                    "connector.generic_peer_pin_all_open",
                    item.generic_peer_pin_all_open_finding_count,
                ),
                (
                    "connector.footprint_named_signal_assignment_divergence",
                    item.footprint_alias_coverage.named_signal_divergence_finding_count,
                ),
                (
                    "connector.footprint_named_passive_assignment_divergence",
                    item.footprint_alias_coverage.named_passive_divergence_finding_count,
                ),
            )
            for rule_id, expected_count in expected_counts:
                actual_count = sum(finding.rule_id == rule_id for finding in self.findings)
                if actual_count != expected_count:
                    raise ValueError(
                        f"Connector peer-pin coverage count must match {rule_id} findings"
                    )
            footprint_findings = sum(
                finding.rule_id == "connector.footprint_peer_pin_assignment_divergence"
                for finding in self.findings
            )
            if footprint_findings != item.footprint_alias_coverage.divergence_finding_count:
                raise ValueError(
                    "Connector footprint-alias peer coverage count must match findings"
                )
            named_power_input_divergence_findings = sum(
                finding.rule_id == "connector.footprint_named_power_input_assignment_divergence"
                for finding in self.findings
            )
            if (
                named_power_input_divergence_findings
                != item.footprint_alias_coverage.named_power_input_divergence_finding_count
            ):
                raise ValueError(
                    "Named power-input footprint-alias coverage count must match findings"
                )
            named_power_input_all_open_findings = sum(
                finding.rule_id == "connector.footprint_named_power_input_all_open"
                for finding in self.findings
            )
            if (
                named_power_input_all_open_findings
                != item.footprint_alias_coverage.named_power_input_all_open_finding_count
            ):
                raise ValueError(
                    "Named power-input all-open footprint-alias coverage count must match findings"
                )
            named_power_output_all_open_findings = sum(
                finding.rule_id == "connector.footprint_named_power_output_all_open"
                for finding in self.findings
            )
            if (
                named_power_output_all_open_findings
                != item.footprint_alias_coverage.named_power_output_all_open_finding_count
            ):
                raise ValueError(
                    "Named power-output all-open footprint-alias coverage count must match findings"
                )
            named_signal_all_open_findings = sum(
                finding.rule_id == "connector.footprint_named_signal_all_open"
                for finding in self.findings
            )
            if (
                named_signal_all_open_findings
                != item.footprint_alias_coverage.named_signal_all_open_finding_count
            ):
                raise ValueError(
                    "Named signal all-open footprint-alias coverage count must match findings"
                )
            named_power_output_divergence_findings = sum(
                finding.rule_id == "connector.footprint_named_power_output_assignment_divergence"
                for finding in self.findings
            )
            if (
                named_power_output_divergence_findings
                != item.footprint_alias_coverage.named_power_output_divergence_finding_count
            ):
                raise ValueError(
                    "Named power-output footprint-alias coverage count must match findings"
                )
            footprint_open_findings = sum(
                finding.rule_id
                in {
                    "connector.footprint_peer_pin_open_outlier",
                    "connector.footprint_named_power_input_open_outlier",
                    "connector.footprint_named_signal_input_open_outlier",
                    "connector.footprint_named_power_output_open_outlier",
                    "connector.footprint_named_signal_output_open_outlier",
                    "connector.footprint_named_signal_mode_dependent_open_outlier",
                    "connector.footprint_named_passive_open_outlier",
                }
                for finding in self.findings
            )
            if footprint_open_findings != item.footprint_alias_coverage.open_outlier_finding_count:
                raise ValueError(
                    "Connector footprint-alias open-peer coverage count must match findings"
                )
            footprint_all_open_findings = sum(
                finding.rule_id == "connector.footprint_peer_pin_all_open"
                for finding in self.findings
            )
            if footprint_all_open_findings != item.footprint_alias_coverage.all_open_finding_count:
                raise ValueError(
                    "Connector footprint-alias all-open coverage count must match findings"
                )
            part_id_expected_counts = (
                (
                    "connector.peer_pin_assignment_outlier",
                    item.part_id_alias_coverage.outlier_finding_count,
                ),
                (
                    "connector.peer_pin_assignment_divergence",
                    item.part_id_alias_coverage.divergence_finding_count,
                ),
            )
            for rule_id, expected_count in part_id_expected_counts:
                actual_count = sum(
                    finding.rule_id == rule_id
                    and finding.evidence.get("peer_identity_basis") == ("part_id",)
                    for finding in self.findings
                )
                if actual_count != expected_count:
                    raise ValueError(
                        f"Connector PART_ID peer coverage count must match {rule_id} findings"
                    )
        if self.rule_catalog is None:
            return self
        known = {item.rule_id for item in self.rule_catalog.rules if item.status == "active"}
        unknown = sorted({item.rule_id for item in self.findings} - known)
        if unknown:
            raise ValueError(
                f"Design-lint findings use rules absent from the active catalog: {unknown}"
            )
        return self


register_design_lint_report(DesignLintReport)
