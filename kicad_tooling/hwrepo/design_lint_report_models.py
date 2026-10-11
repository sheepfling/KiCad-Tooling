"""Typed design-lint report output model."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field, model_validator

from .component_peer_pin_models import ComponentPeerPinRuleCoverage
from .connector_peer_pin_models import ConnectorPeerPinHeuristicCoverage
from .control_input_models import ControlInputBiasHeuristicCoverage
from .design_lint_rule_models import DesignLintRuleCatalog
from .digital_peer_voltage_models import DigitalPeerVoltageRuleCoverage
from .external_protection_models import ExternalProtectionCoverageReport
from .i2c_address_models import I2cAddressCoverageReport
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel
from .models import (
    ConnectorCoverageReport,
    ConnectorReturnDistributionCoverageReport,
    CrystalNetworkCoverageReport,
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintMappedCheckRun,
    DesignLintRuleOverride,
    PcbKeepoutCoverageReport,
    PcbProtectionPathCoverageReport,
    RcFilterCoverageReport,
    RegulatorFeedbackCoverageReport,
    SchematicGeometryCoverage,
    Stm32PinMapCoverageReport,
    _register_design_lint_report,
)
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import PcbDifferentialPairRuleCoverageReport, PcbSignalPathRuleCoverageReport
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import PcbSwitchingLoopCoverageReport
from .pcb_track_width_models import PcbTrackWidthCoverageReport
from .serial_peer_reference_models import SerialPeerReferenceCoverageReport
from .usb_peer_reference_models import UsbPeerReferenceCoverageReport


class DesignLintReport(StrictModel):
    """Source-bound heuristic findings; neither a pinout nor electrical approval."""

    schema_version: Literal["1", "2"] = "2"
    lane: Literal["DESIGN_LINT"] = "DESIGN_LINT"
    status: Literal["PASS", "REVIEW", "FAIL", "BLOCKED"]
    project_id: Identifier
    review_state: Literal["HEURISTIC"] = "HEURISTIC"
    build_authorized: Literal[False] = False
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    netlist_sha256: Digest | None = None
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
    stale_ignores: tuple[DesignLintIgnore, ...] = ()
    rule_overrides: tuple[DesignLintRuleOverride, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def findings_are_catalogued(self) -> DesignLintReport:
        inventory = self.pcb_component_inventory
        if (
            self.netlist_sha256 is not None
            and inventory.netlist_sha256 is not None
            and inventory.netlist_sha256 != self.netlist_sha256
        ):
            raise ValueError("PCB component inventory must use this report's native netlist")
        if inventory.status == "COMPLETE":
            expected_findings = len(inventory.missing_placements)
            actual_findings = sum(
                finding.rule_id == "pcb.schematic_component_inventory" for finding in self.findings
            )
            if actual_findings != expected_findings:
                raise ValueError(
                    "PCB component inventory findings must match its missing placements"
                )
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
            )
            for rule_id, expected_count in expected_counts:
                actual_count = sum(finding.rule_id == rule_id for finding in self.findings)
                if actual_count != expected_count:
                    raise ValueError(
                        f"Connector peer-pin coverage count must match {rule_id} findings"
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


_register_design_lint_report(DesignLintReport)
