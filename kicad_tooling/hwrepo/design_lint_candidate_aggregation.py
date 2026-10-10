"""Reviewable heuristic findings from source-bound native netlist evidence."""

from __future__ import annotations

import hashlib
import json

from .bus_signal_pairs import (
    ComplementaryPinFunctionAliasResolution,
)
from .component_peer_pin_scan import (
    ComponentPeerPinAssignmentScans,
    component_peer_pin_assignment_scans,
)
from .design_lint_bus_candidates import bus_candidates
from .design_lint_catalog import rule_catalog
from .design_lint_component_candidates import component_candidates
from .design_lint_component_peer_candidates import component_peer_candidates
from .design_lint_connector_candidates import connector_candidates
from .design_lint_control_candidates import control_candidates
from .design_lint_mapped_coverage_candidates import mapped_coverage_candidates
from .design_lint_pcb_measurement_candidates import pcb_measurement_coverage_candidates
from .design_lint_pcb_requirement_candidates import pcb_requirement_coverage_candidates
from .design_lint_peer_candidates import peer_candidates
from .design_lint_power_candidates import power_candidates
from .design_lint_return_distribution_candidates import return_distribution_candidates
from .design_lint_rule_models import DesignLintRuleCatalog
from .design_lint_schematic_geometry import schematic_geometry_candidates
from .design_lint_stm32_candidates import stm32_candidates
from .design_lint_types import Candidate
from .design_lint_usb_peer_candidates import usb_data_path_map_sha256
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext, DigitalPeerVoltageScan
from .models import (
    ComponentRoleMap,
    ConnectorCoverageReport,
    ConnectorReturnDistributionCoverageReport,
    ControlInputBiasHeuristicCoverage,
    CrystalNetworkCoverageReport,
    ExternalProtectionCoverageReport,
    I2cAddressCoverageReport,
    I2cAddressMap,
    I2cPullupHeuristicCoverage,
    NetlistContract,
    PcbKeepoutCoverageReport,
    PcbProtectionPathCoverageReport,
    PowerPathMap,
    PowerSequenceMap,
    RcFilterCoverageReport,
    RegulatorFeedbackCoverageReport,
    Stm32PinMapCoverageReport,
    UsbDataPathMap,
)
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageReport,
    PcbDifferentialPairRuleMap,
    PcbSignalPathRuleCoverageReport,
)
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
)
from .pcb_track_width_models import PcbTrackWidthCoverageReport
from .schematic_geometry import (
    SchematicGeometryScan,
)
from .serial_participants import SerialPeerRosterContext
from .serial_peer_reference_types import SerialPeerReferenceScan
from .spi_participants import SpiRosterContext
from .usb_c_ports import UsbCPortRosterContext
from .usb_peer_reference_types import UsbPeerReferenceScan


def fingerprint(item: Candidate) -> str:
    """Bind an ignore to exact observed pins/nets, independent of unrelated files."""
    payload = {
        "rule_id": item.rule_id,
        "subject": item.subject,
        "evidence": {key: sorted(value) for key, value in sorted(item.evidence.items())},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def candidates(
    observed: NetlistContract,
    catalog: DesignLintRuleCatalog | None = None,
    schematic_geometry: SchematicGeometryScan | None = None,
    i2c_address_coverage: I2cAddressCoverageReport | None = None,
    external_protection_coverage: ExternalProtectionCoverageReport | None = None,
    crystal_network_coverage: CrystalNetworkCoverageReport | None = None,
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport | None = None,
    rc_filter_coverage: RcFilterCoverageReport | None = None,
    connector_return_distribution: ConnectorReturnDistributionCoverageReport | None = None,
    pcb_decoupling_coverage: PcbDecouplingCoverageReport | None = None,
    pcb_protection_path_coverage: PcbProtectionPathCoverageReport | None = None,
    pcb_track_width_coverage: PcbTrackWidthCoverageReport | None = None,
    pcb_switching_loop_coverage: PcbSwitchingLoopCoverageReport | None = None,
    pcb_differential_pair_coverage: PcbDifferentialPairRuleCoverageReport | None = None,
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None = None,
    i2c_address_map: I2cAddressMap | None = None,
    usb_data_path_map: UsbDataPathMap | None = None,
    stm32_pin_map_coverage: Stm32PinMapCoverageReport | None = None,
    spi_roster: SpiRosterContext | None = None,
    usb_c_port_roster: UsbCPortRosterContext | None = None,
    power_path_map: PowerPathMap | None = None,
    power_sequence_map: PowerSequenceMap | None = None,
    pcb_reference_plane_coverage: PcbReferencePlaneCoverageReport | None = None,
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage | None = None,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None,
    digital_peer_voltage_context: DigitalPeerVoltageLintContext | None = None,
    component_role_map: ComponentRoleMap | None = None,
    serial_peer_roster: SerialPeerRosterContext | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution | None = None,
    connector_coverage: ConnectorCoverageReport | None = None,
    digital_peer_voltage_scan: DigitalPeerVoltageScan | None = None,
    usb_peer_reference_scan: UsbPeerReferenceScan | None = None,
    serial_peer_reference_scan: SerialPeerReferenceScan | None = None,
    pcb_signal_path_coverage: PcbSignalPathRuleCoverageReport | None = None,
    pcb_keepout_coverage: PcbKeepoutCoverageReport | None = None,
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport | None = None,
    peer_pin_assignment_scans: ComponentPeerPinAssignmentScans | None = None,
) -> tuple[Candidate, ...]:
    """Aggregate thematic candidates and preserve one active-catalog lifecycle."""
    found: list[Candidate] = []
    usb_data_map_sha256 = usb_data_path_map_sha256(usb_data_path_map)
    peer_pin_scans = peer_pin_assignment_scans or component_peer_pin_assignment_scans(
        observed,
        reviewed_connector_references,
    )
    found.extend(
        connector_candidates(
            observed,
            connector_coverage=connector_coverage,
            reviewed_connector_references=reviewed_connector_references,
        )
    )
    found.extend(return_distribution_candidates(connector_return_distribution))
    control_findings, control_pin_keys = control_candidates(
        observed,
        control_input_bias_coverage=control_input_bias_coverage,
    )
    found.extend(control_findings)
    found.extend(
        component_candidates(
            observed,
            component_role_map=component_role_map,
            reviewed_connector_references=reviewed_connector_references,
        )
    )
    found.extend(
        power_candidates(
            observed,
            component_role_map=component_role_map,
            power_path_map=power_path_map,
            reviewed_connector_references=reviewed_connector_references,
        )
    )
    found.extend(
        component_peer_candidates(
            observed,
            peer_pin_scans=peer_pin_scans,
            reviewed_connector_references=reviewed_connector_references,
            control_pin_keys=control_pin_keys,
        )
    )
    found.extend(
        bus_candidates(
            observed,
            complementary_alias_resolution=complementary_alias_resolution,
            i2c_address_coverage=i2c_address_coverage,
            i2c_address_map=i2c_address_map,
            i2c_pullup_heuristic_coverage=i2c_pullup_heuristic_coverage,
            pcb_differential_pair_rule_map=pcb_differential_pair_rule_map,
        )
    )
    if schematic_geometry is not None:
        found.extend(schematic_geometry_candidates(schematic_geometry))
    found.extend(
        peer_candidates(
            observed,
            digital_peer_voltage_context=digital_peer_voltage_context,
            digital_peer_voltage_scan=digital_peer_voltage_scan,
            reviewed_connector_references=reviewed_connector_references,
            serial_peer_reference_scan=serial_peer_reference_scan,
            serial_peer_roster=serial_peer_roster,
            spi_roster=spi_roster,
            usb_c_port_roster=usb_c_port_roster,
            usb_data_path_map=usb_data_path_map,
            usb_data_map_sha256=usb_data_map_sha256,
            usb_peer_reference_scan=usb_peer_reference_scan,
        )
    )
    found.extend(
        mapped_coverage_candidates(
            observed,
            external_protection_coverage=external_protection_coverage,
            crystal_network_coverage=crystal_network_coverage,
            regulator_feedback_coverage=regulator_feedback_coverage,
            rc_filter_coverage=rc_filter_coverage,
            usb_data_path_map=usb_data_path_map,
            usb_data_map_sha256=usb_data_map_sha256,
            power_path_map=power_path_map,
            power_sequence_map=power_sequence_map,
        )
    )
    found.extend(
        pcb_measurement_coverage_candidates(
            pcb_decoupling_coverage=pcb_decoupling_coverage,
            pcb_protection_path_coverage=pcb_protection_path_coverage,
            pcb_track_width_coverage=pcb_track_width_coverage,
            pcb_reference_plane_coverage=pcb_reference_plane_coverage,
        )
    )
    found.extend(
        pcb_requirement_coverage_candidates(
            pcb_switching_loop_coverage=pcb_switching_loop_coverage,
            pcb_differential_pair_coverage=pcb_differential_pair_coverage,
            pcb_signal_path_coverage=pcb_signal_path_coverage,
            pcb_keepout_coverage=pcb_keepout_coverage,
            pcb_rf_module_antenna_coverage=pcb_rf_module_antenna_coverage,
        )
    )
    found.extend(stm32_candidates(stm32_pin_map_coverage))
    active_ids = {
        item.rule_id for item in (catalog or rule_catalog()).rules if item.status == "active"
    }
    unknown_ids = sorted({item.rule_id for item in found} - active_ids)
    if unknown_ids:
        raise ValueError(
            f"Design-lint candidates emit rules absent from the active catalog: {unknown_ids}"
        )
    return tuple(sorted(found, key=lambda item: (item.rule_id, item.subject)))
