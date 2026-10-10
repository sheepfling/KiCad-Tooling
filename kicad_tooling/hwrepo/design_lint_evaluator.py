"""Public entry point for staged, source-bound design-lint evaluation."""

from __future__ import annotations

from .design_lint_evaluation_candidates import scan_evaluation_candidates
from .design_lint_evaluation_preparation import prepare_evaluation
from .design_lint_evaluation_report import assemble_design_lint_report
from .design_lint_evaluation_report_inputs import (
    blocked_wrong_ignore_report,
    evaluation_report_input,
)
from .design_lint_evaluation_types import DesignLintEvaluationRequest
from .design_lint_finding_disposition import resolve_finding_dispositions
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext
from .i2c_address_models import I2cAddressCoverageReport
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .models import (
    ConnectorCoverageReport,
    ConnectorReturnDistributionCoverageReport,
    ContractCoachReport,
    ControlInputBiasHeuristicCoverage,
    CrystalNetworkCoverageReport,
    DesignLintPolicy,
    DesignLintReport,
    ExternalProtectionCoverageReport,
    PcbKeepoutCoverageReport,
    PcbProtectionPathCoverageReport,
    RcFilterCoverageReport,
    RegulatorFeedbackCoverageReport,
    SchematicGeometryCoverage,
    Stm32PinMapCoverageReport,
)
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageReport,
    PcbSignalPathRuleCoverageReport,
)
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
)
from .pcb_track_width_models import PcbTrackWidthCoverageReport
from .schematic_geometry import SchematicGeometryScan
from .serial_participants import SerialPeerRosterContext
from .spi_participants import SpiRosterContext
from .usb_c_ports import UsbCPortRosterContext


def evaluate(
    project_id: str,
    coach: ContractCoachReport,
    policy: DesignLintPolicy,
    connector_coverage: ConnectorCoverageReport | None = None,
    schematic_geometry: SchematicGeometryScan | None = None,
    geometry_coverage: SchematicGeometryCoverage | None = None,
    i2c_address_coverage: I2cAddressCoverageReport | None = None,
    external_protection_coverage: ExternalProtectionCoverageReport | None = None,
    crystal_network_coverage: CrystalNetworkCoverageReport | None = None,
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport | None = None,
    rc_filter_coverage: RcFilterCoverageReport | None = None,
    connector_return_distribution_coverage: ConnectorReturnDistributionCoverageReport | None = None,
    pcb_decoupling_coverage: PcbDecouplingCoverageReport | None = None,
    pcb_protection_path_coverage: PcbProtectionPathCoverageReport | None = None,
    pcb_track_width_coverage: PcbTrackWidthCoverageReport | None = None,
    pcb_switching_loop_coverage: PcbSwitchingLoopCoverageReport | None = None,
    pcb_differential_pair_coverage: PcbDifferentialPairRuleCoverageReport | None = None,
    stm32_pin_map_coverage: Stm32PinMapCoverageReport | None = None,
    spi_roster: SpiRosterContext | None = None,
    usb_c_port_roster: UsbCPortRosterContext | None = None,
    pcb_reference_plane_coverage: PcbReferencePlaneCoverageReport | None = None,
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage | None = None,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None,
    digital_peer_voltage_context: DigitalPeerVoltageLintContext | None = None,
    serial_peer_roster: SerialPeerRosterContext | None = None,
    pcb_signal_path_coverage: PcbSignalPathRuleCoverageReport | None = None,
    pcb_keepout_coverage: PcbKeepoutCoverageReport | None = None,
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport | None = None,
) -> DesignLintReport:
    """Apply project policy to findings while preserving the established call shape."""
    request = DesignLintEvaluationRequest(
        project_id=project_id,
        coach=coach,
        policy=policy,
        connector_coverage=connector_coverage,
        schematic_geometry=schematic_geometry,
        geometry_coverage=geometry_coverage,
        i2c_address_coverage=i2c_address_coverage,
        external_protection_coverage=external_protection_coverage,
        crystal_network_coverage=crystal_network_coverage,
        regulator_feedback_coverage=regulator_feedback_coverage,
        rc_filter_coverage=rc_filter_coverage,
        connector_return_distribution_coverage=connector_return_distribution_coverage,
        pcb_decoupling_coverage=pcb_decoupling_coverage,
        pcb_protection_path_coverage=pcb_protection_path_coverage,
        pcb_track_width_coverage=pcb_track_width_coverage,
        pcb_switching_loop_coverage=pcb_switching_loop_coverage,
        pcb_differential_pair_coverage=pcb_differential_pair_coverage,
        stm32_pin_map_coverage=stm32_pin_map_coverage,
        spi_roster=spi_roster,
        usb_c_port_roster=usb_c_port_roster,
        pcb_reference_plane_coverage=pcb_reference_plane_coverage,
        control_input_bias_coverage=control_input_bias_coverage,
        i2c_pullup_heuristic_coverage=i2c_pullup_heuristic_coverage,
        digital_peer_voltage_context=digital_peer_voltage_context,
        serial_peer_roster=serial_peer_roster,
        pcb_signal_path_coverage=pcb_signal_path_coverage,
        pcb_keepout_coverage=pcb_keepout_coverage,
        pcb_rf_module_antenna_coverage=pcb_rf_module_antenna_coverage,
    )
    result = prepare_evaluation(request)
    if result.report is not None:
        return result.report
    prepared = result.prepared
    if prepared is None:
        raise RuntimeError("Design-lint preparation returned neither a report nor prepared state")
    candidate_results = scan_evaluation_candidates(prepared)
    disposition = resolve_finding_dispositions(prepared, candidate_results)
    if disposition.issue is not None:
        return blocked_wrong_ignore_report(prepared, candidate_results, disposition.issue)
    return assemble_design_lint_report(
        evaluation_report_input(prepared, candidate_results, disposition)
    )
