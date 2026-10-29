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
from .design_lint_report_catalog_validation import validate_catalogued_findings
from .design_lint_report_connector_coverage_validation import (
    validate_connector_peer_pin_coverage,
)
from .design_lint_report_evidence_validation import validate_source_bound_evidence
from .design_lint_report_pcb_evidence_validation import validate_pcb_source_consistency
from .design_lint_report_peer_coverage_validation import validate_peer_coverage
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

    schema_version: Literal["1", "2", "3", "4", "5", "6", "7"] = "7"
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
        validate_source_bound_evidence(
            project_id=self.project_id,
            source_hashes=self.source_hashes,
            netlist_sha256=self.netlist_sha256,
            connectivity_snapshot=self.connectivity_snapshot,
            findings=self.findings,
            findings_complete=self.status != "BLOCKED" or bool(self.findings),
            i2c_address_coverage=self.i2c_address_coverage,
            crystal_network_coverage=self.crystal_network_coverage,
            regulator_feedback_coverage=self.regulator_feedback_coverage,
            rc_filter_coverage=self.rc_filter_coverage,
            connector_return_distribution=self.connector_return_distribution,
            connector_interface_catalog_sha256=(
                None
                if self.connector_coverage is None
                else self.connector_coverage.interface_catalog_sha256
            ),
            pcb_component_inventory=self.pcb_component_inventory,
            control_input_bias_coverage=self.control_input_bias_coverage,
            i2c_pullup_heuristic_coverage=self.i2c_pullup_heuristic_coverage,
            pcb_rf_module_antenna_coverage=self.pcb_rf_module_antenna_coverage,
            pcb_touch_pad_clearance_coverage=self.pcb_touch_pad_clearance_coverage,
            mapped_check_runs=self.mapped_check_runs,
        )
        validate_peer_coverage(
            netlist_sha256=self.netlist_sha256,
            findings=self.findings,
            findings_complete=self.status != "BLOCKED" or bool(self.findings),
            digital_peer_voltage_coverage=self.digital_peer_voltage_coverage,
            component_peer_pin_coverage=self.component_peer_pin_coverage,
            usb_peer_reference_coverage=self.usb_peer_reference_coverage,
            serial_peer_reference_coverage=self.serial_peer_reference_coverage,
            i2c_peer_reference_coverage=self.i2c_peer_reference_coverage,
            spi_peer_reference_coverage=self.spi_peer_reference_coverage,
            can_peer_reference_coverage=self.can_peer_reference_coverage,
            rs485_peer_reference_coverage=self.rs485_peer_reference_coverage,
        )
        validate_connector_peer_pin_coverage(
            netlist_sha256=self.netlist_sha256,
            findings=self.findings,
            findings_complete=self.status != "BLOCKED" or bool(self.findings),
            connector_peer_pin_coverage=self.connector_peer_pin_coverage,
        )
        validate_pcb_source_consistency(
            (
                self.pcb_component_inventory,
                self.pcb_decoupling,
                self.pcb_differential_pair_rules,
                self.pcb_keepout_coverage,
                self.pcb_protection_path,
                self.pcb_reference_plane,
                self.pcb_rf_module_antenna_coverage,
                self.pcb_signal_path_rules,
                self.pcb_switching_loop,
                self.pcb_touch_pad_clearance_coverage,
                self.pcb_track_width,
            ),
            report_netlist_sha256=self.netlist_sha256,
            netlist_reports=(
                self.pcb_component_inventory,
                self.pcb_decoupling,
                self.pcb_keepout_coverage,
                self.pcb_protection_path,
                self.pcb_reference_plane,
                self.pcb_rf_module_antenna_coverage,
                self.pcb_switching_loop,
                self.pcb_touch_pad_clearance_coverage,
                self.pcb_track_width,
            ),
        )
        validate_catalogued_findings(
            rule_catalog=self.rule_catalog,
            findings=self.findings,
        )
        return self


register_design_lint_report(DesignLintReport)
