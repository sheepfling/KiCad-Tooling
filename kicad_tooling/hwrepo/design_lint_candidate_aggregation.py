"""Reviewable heuristic findings from source-bound native netlist evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from .bus_signal_pairs import (
    ComplementaryPinFunctionAliasResolution,
)
from .can_peer_reference_scan import CanPeerReferenceScan
from .component_peer_pin_evaluation import component_peer_pin_assignment_scans
from .component_peer_pin_scan import ComponentPeerPinAssignmentScans
from .component_role_models import ComponentRoleMap
from .connector_coverage_models import ConnectorCoverageReport
from .connector_return_distribution_models import ConnectorReturnDistributionCoverageReport
from .connector_stateful_contact_models import ConnectorStatefulContactMap
from .control_input_models import ControlInputBiasHeuristicCoverage
from .crystal_network_models import CrystalNetworkCoverageReport
from .design_lint_bus_candidates import bus_candidates
from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_candidate_inputs import (
    ComponentCandidateInputs,
    ConnectorCandidateInputs,
    ControlCandidateInputs,
    DesignLintCandidateInputs,
    MappedCandidateInputs,
    PcbCandidateInputs,
    PeerCandidateInputs,
    PowerCandidateInputs,
)
from .design_lint_catalog import rule_catalog
from .design_lint_component_candidates import component_candidates
from .design_lint_component_peer_candidates import component_peer_candidates
from .design_lint_connector_candidates import connector_candidates
from .design_lint_control_candidates import control_candidates
from .design_lint_mapped_coverage_candidates import mapped_coverage_candidates
from .design_lint_pcb_board_only_candidates import pcb_board_only_footprint_candidates
from .design_lint_pcb_component_inventory_candidates import (
    pcb_component_inventory_candidates,
)
from .design_lint_pcb_measurement_candidates import pcb_measurement_coverage_candidates
from .design_lint_pcb_pad_net_candidates import pcb_pad_net_candidates
from .design_lint_pcb_required_fitted_reference_candidates import (
    pcb_required_fitted_reference_candidates,
)
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
from .external_protection_models import ExternalProtectionCoverageReport
from .i2c_address_inputs import I2cAddressCandidateInput
from .i2c_address_models import (
    I2cAddressCoverageReport,
    I2cAddressMap,
)
from .i2c_peer_reference_scan import I2cPeerReferenceScan
from .i2c_pullup_inputs import I2cPullupSnifferInput
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .ic_decoupling_models import IcDecouplingMap
from .models import NetlistContract
from .oscillator_output_path_models import OscillatorOutputPathMap
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageReport,
    PcbDifferentialPairRuleMap,
    PcbSignalPathRuleCoverageReport,
)
from .pcb_keepout_models import (
    PcbKeepoutCoverageReport,
)
from .pcb_protection_path_models import PcbProtectionPathCoverageReport
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
)
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport
from .pcb_track_width_models import PcbTrackWidthCoverageReport
from .power_path_models import PowerPathMap
from .power_sequence_models import PowerSequenceMap
from .rc_filter_models import RcFilterCoverageReport
from .regulator_feedback_models import RegulatorFeedbackCoverageReport
from .rs485_peer_reference_types import Rs485PeerReferenceScan
from .schematic_geometry import (
    SchematicGeometryScan,
)
from .serial_participants import SerialPeerRosterContext
from .serial_peer_reference_types import SerialPeerReferenceScan
from .spi_participants import SpiRosterContext
from .spi_peer_reference_scan import SpiPeerReferenceScan
from .stm32_pin_map_models import Stm32PinMapCoverageReport
from .usb_c_ports import UsbCPortRosterContext
from .usb_data_path_models import UsbDataPathMap
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


def validate_catalogued_candidates(
    items: Sequence[Candidate],
    catalog: DesignLintRuleCatalog | None = None,
) -> None:
    """Reject candidates from any theme that are absent from the active catalog."""
    active_ids = {
        item.rule_id for item in (catalog or rule_catalog()).rules if item.status == "active"
    }
    unknown_ids = sorted({item.rule_id for item in items} - active_ids)
    if unknown_ids:
        raise ValueError(
            f"Design-lint candidates emit rules absent from the active catalog: {unknown_ids}"
        )


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
    pcb_touch_pad_clearance_coverage: PcbTouchPadClearanceCoverageReport | None = None,
    peer_pin_assignment_scans: ComponentPeerPinAssignmentScans | None = None,
    pcb_component_inventory_coverage: PcbComponentInventoryCoverageReport | None = None,
    i2c_peer_reference_scan: I2cPeerReferenceScan | None = None,
    spi_peer_reference_scan: SpiPeerReferenceScan | None = None,
    can_peer_reference_scan: CanPeerReferenceScan | None = None,
    rs485_peer_reference_scan: Rs485PeerReferenceScan | None = None,
    peer_power_output_review_enabled: bool = True,
    connector_power_output_review_enabled: bool = True,
    ic_decoupling_map: IcDecouplingMap | None = None,
    oscillator_output_path_map: OscillatorOutputPathMap | None = None,
    connector_stateful_contact_map: ConnectorStatefulContactMap | None = None,
) -> tuple[Candidate, ...]:
    """Adapt legacy inputs to the shared typed candidate scanner."""
    return scan_candidates(
        DesignLintCandidateInputs(
            observed=observed,
            catalog=catalog,
            schematic_geometry=schematic_geometry,
            reviewed_connector_references=reviewed_connector_references,
            connector=ConnectorCandidateInputs(
                coverage=connector_coverage,
                return_distribution=connector_return_distribution,
                stateful_contact_map=connector_stateful_contact_map,
                power_output_review_enabled=connector_power_output_review_enabled,
            ),
            component=ComponentCandidateInputs(
                peer_pin_assignment_scans=peer_pin_assignment_scans,
                peer_power_output_review_enabled=peer_power_output_review_enabled,
            ),
            control=ControlCandidateInputs(
                input_bias_coverage=control_input_bias_coverage,
            ),
            power=PowerCandidateInputs(
                component_role_map=component_role_map,
                power_path_map=power_path_map,
                power_sequence_map=power_sequence_map,
                oscillator_output_path_map=oscillator_output_path_map,
                ic_decoupling_map=ic_decoupling_map,
            ),
            bus=BusCandidateInputs(
                observed=observed,
                i2c_address=I2cAddressCandidateInput.from_candidate_arguments(
                    observed, i2c_address_map, i2c_address_coverage
                ),
                i2c_pullup=I2cPullupSnifferInput.from_legacy_arguments(
                    observed, i2c_pullup_heuristic_coverage
                ),
                complementary_alias_resolution=complementary_alias_resolution,
                i2c_peer_reference_scan=i2c_peer_reference_scan,
                spi_roster=spi_roster,
                spi_peer_reference_scan=spi_peer_reference_scan,
                can_peer_reference_scan=can_peer_reference_scan,
                rs485_peer_reference_scan=rs485_peer_reference_scan,
                pcb_differential_pair_rule_map=pcb_differential_pair_rule_map,
                reviewed_connector_references=reviewed_connector_references,
            ),
            peer=PeerCandidateInputs(
                digital_voltage_context=digital_peer_voltage_context,
                digital_voltage_scan=digital_peer_voltage_scan,
                usb_reference_scan=usb_peer_reference_scan,
                serial_reference_scan=serial_peer_reference_scan,
                serial_roster=serial_peer_roster,
                usb_c_port_roster=usb_c_port_roster,
            ),
            mapped=MappedCandidateInputs(
                external_protection=external_protection_coverage,
                crystal_network=crystal_network_coverage,
                regulator_feedback=regulator_feedback_coverage,
                rc_filter=rc_filter_coverage,
            ),
            pcb=PcbCandidateInputs(
                component_inventory=pcb_component_inventory_coverage,
                decoupling=pcb_decoupling_coverage,
                protection_path=pcb_protection_path_coverage,
                track_width=pcb_track_width_coverage,
                reference_plane=pcb_reference_plane_coverage,
                switching_loop=pcb_switching_loop_coverage,
                differential_pair=pcb_differential_pair_coverage,
                signal_path=pcb_signal_path_coverage,
                keepout=pcb_keepout_coverage,
                rf_antenna=pcb_rf_module_antenna_coverage,
                touch_pad_clearance=pcb_touch_pad_clearance_coverage,
                stm32_pin_map=stm32_pin_map_coverage,
            ),
            usb_data_path_map=usb_data_path_map,
        )
    )


def scan_candidates(inputs: DesignLintCandidateInputs) -> tuple[Candidate, ...]:
    """Aggregate typed theme inputs and preserve one active-catalog lifecycle."""
    observed = inputs.observed
    catalog = inputs.catalog
    schematic_geometry = inputs.schematic_geometry
    reviewed_connector_references = inputs.reviewed_connector_references
    connector_coverage = inputs.connector.coverage
    connector_return_distribution = inputs.connector.return_distribution
    connector_stateful_contact_map = inputs.connector.stateful_contact_map
    connector_power_output_review_enabled = inputs.connector.power_output_review_enabled
    component_role_map = inputs.power.component_role_map
    power_path_map = inputs.power.power_path_map
    oscillator_output_path_map = inputs.power.oscillator_output_path_map
    ic_decoupling_map = inputs.power.ic_decoupling_map
    peer_pin_assignment_scans = inputs.component.peer_pin_assignment_scans
    peer_power_output_review_enabled = inputs.component.peer_power_output_review_enabled
    control_input_bias_coverage = inputs.control.input_bias_coverage
    digital_peer_voltage_context = inputs.peer.digital_voltage_context
    digital_peer_voltage_scan = inputs.peer.digital_voltage_scan
    usb_peer_reference_scan = inputs.peer.usb_reference_scan
    serial_peer_reference_scan = inputs.peer.serial_reference_scan
    serial_peer_roster = inputs.peer.serial_roster
    usb_c_port_roster = inputs.peer.usb_c_port_roster
    external_protection_coverage = inputs.mapped.external_protection
    crystal_network_coverage = inputs.mapped.crystal_network
    regulator_feedback_coverage = inputs.mapped.regulator_feedback
    rc_filter_coverage = inputs.mapped.rc_filter
    power_sequence_map = inputs.power.power_sequence_map
    pcb_component_inventory_coverage = inputs.pcb.component_inventory
    pcb_decoupling_coverage = inputs.pcb.decoupling
    pcb_protection_path_coverage = inputs.pcb.protection_path
    pcb_track_width_coverage = inputs.pcb.track_width
    pcb_reference_plane_coverage = inputs.pcb.reference_plane
    pcb_switching_loop_coverage = inputs.pcb.switching_loop
    pcb_differential_pair_coverage = inputs.pcb.differential_pair
    pcb_signal_path_coverage = inputs.pcb.signal_path
    pcb_keepout_coverage = inputs.pcb.keepout
    pcb_rf_module_antenna_coverage = inputs.pcb.rf_antenna
    pcb_touch_pad_clearance_coverage = inputs.pcb.touch_pad_clearance
    stm32_pin_map_coverage = inputs.pcb.stm32_pin_map
    usb_data_path_map = inputs.usb_data_path_map
    i2c_address_input = inputs.bus.i2c_address
    i2c_pullup_input = inputs.bus.i2c_pullup
    complementary_alias_resolution = inputs.bus.complementary_alias_resolution
    i2c_peer_reference_scan = inputs.bus.i2c_peer_reference_scan
    spi_roster = inputs.bus.spi_roster
    spi_peer_reference_scan = inputs.bus.spi_peer_reference_scan
    can_peer_reference_scan = inputs.bus.can_peer_reference_scan
    rs485_peer_reference_scan = inputs.bus.rs485_peer_reference_scan
    pcb_differential_pair_rule_map = inputs.bus.pcb_differential_pair_rule_map
    found: list[Candidate] = []
    usb_data_map_sha256 = usb_data_path_map_sha256(usb_data_path_map)
    peer_pin_scans = peer_pin_assignment_scans or component_peer_pin_assignment_scans(
        observed,
        reviewed_connector_references,
    )
    peer_unconnected_power_output_pins: frozenset[str] = (
        frozenset(
            pin.casefold()
            for group in peer_pin_scans.power_output.outliers
            for pin, nets in group.assignments.items()
            if not nets
        )
        if peer_power_output_review_enabled
        else frozenset[str]()
    )
    found.extend(
        connector_candidates(
            observed,
            connector_coverage=connector_coverage,
            reviewed_connector_references=reviewed_connector_references,
            power_output_review_enabled=connector_power_output_review_enabled,
            stateful_contact_map=connector_stateful_contact_map,
        )
    )
    found.extend(return_distribution_candidates(connector_return_distribution))
    found.extend(pcb_component_inventory_candidates(pcb_component_inventory_coverage))
    found.extend(pcb_board_only_footprint_candidates(pcb_component_inventory_coverage))
    found.extend(pcb_required_fitted_reference_candidates(pcb_component_inventory_coverage))
    found.extend(pcb_pad_net_candidates(pcb_component_inventory_coverage))
    control_findings, control_pin_keys = control_candidates(
        observed,
        control_input_bias_coverage=control_input_bias_coverage,
    )
    found.extend(control_findings)
    found.extend(
        component_candidates(
            observed,
            component_role_map=component_role_map,
            power_path_map=power_path_map,
            oscillator_output_path_map=oscillator_output_path_map,
            reviewed_connector_references=reviewed_connector_references,
        )
    )
    found.extend(
        power_candidates(
            observed,
            component_role_map=component_role_map,
            power_path_map=power_path_map,
            reviewed_connector_references=reviewed_connector_references,
            peer_unconnected_power_output_pins=peer_unconnected_power_output_pins,
            ic_decoupling_map=ic_decoupling_map,
        )
    )
    component_peer_findings = component_peer_candidates(
        observed,
        peer_pin_scans=peer_pin_scans,
        reviewed_connector_references=reviewed_connector_references,
        control_pin_keys=control_pin_keys,
    )
    found.extend(component_peer_findings)
    found.extend(
        bus_candidates(
            BusCandidateInputs(
                observed=observed,
                i2c_address=i2c_address_input,
                i2c_pullup=i2c_pullup_input,
                complementary_alias_resolution=complementary_alias_resolution,
                i2c_peer_reference_scan=i2c_peer_reference_scan,
                spi_roster=spi_roster,
                spi_peer_reference_scan=spi_peer_reference_scan,
                can_peer_reference_scan=can_peer_reference_scan,
                rs485_peer_reference_scan=rs485_peer_reference_scan,
                component_peer_findings=component_peer_findings,
                pcb_differential_pair_rule_map=pcb_differential_pair_rule_map,
                reviewed_connector_references=reviewed_connector_references,
            )
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
            pcb_touch_pad_clearance_coverage=pcb_touch_pad_clearance_coverage,
        )
    )
    found.extend(stm32_candidates(stm32_pin_map_coverage))
    found.extend(inputs.additional_candidates)
    validate_catalogued_candidates(found, catalog)
    return tuple(sorted(found, key=lambda item: (item.rule_id, item.subject)))
