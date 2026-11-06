"""Typed keyword contract for the compatibility candidate adapter."""

from __future__ import annotations

from typing import TypedDict

from .bus_signal_pairs import ComplementaryPinFunctionAliasResolution
from .can_peer_reference_scan import CanPeerReferenceScan
from .component_peer_pin_scan import ComponentPeerPinAssignmentScans
from .component_role_models import ComponentRoleMap
from .connector_coverage_models import ConnectorCoverageReport
from .connector_return_distribution_models import ConnectorReturnDistributionCoverageReport
from .connector_stateful_contact_models import ConnectorStatefulContactMap
from .control_input_models import ControlInputBiasHeuristicCoverage
from .crystal_network_models import CrystalNetworkCoverageReport
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext, DigitalPeerVoltageScan
from .external_protection_models import ExternalProtectionCoverageReport
from .i2c_address_models import I2cAddressCoverageReport, I2cAddressMap
from .i2c_peer_reference_scan import I2cPeerReferenceScan
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .ic_decoupling_models import IcDecouplingMap
from .led_current_models import LedCurrentMap
from .oscillator_output_path_models import OscillatorOutputPathMap
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageReport,
    PcbDifferentialPairRuleMap,
    PcbSignalPathRuleCoverageReport,
)
from .pcb_keepout_models import PcbKeepoutCoverageReport
from .pcb_protection_path_models import PcbProtectionPathCoverageReport
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import PcbSwitchingLoopCoverageReport
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport
from .pcb_track_width_models import PcbTrackWidthCoverageReport
from .power_path_models import PowerPathMap
from .power_sequence_models import PowerSequenceMap
from .rc_filter_models import RcFilterCoverageReport
from .regulator_feedback_models import RegulatorFeedbackCoverageReport
from .rs485_peer_reference_types import Rs485PeerReferenceScan
from .schematic_geometry import SchematicGeometryScan
from .serial_participants import SerialPeerRosterContext
from .serial_peer_reference_types import SerialPeerReferenceScan
from .signal_divider_models import SignalDividerCoverageReport
from .spi_participants import SpiRosterContext
from .spi_peer_reference_scan import SpiPeerReferenceScan
from .stm32_pin_map_models import Stm32PinMapCoverageReport
from .usb_c_ports import UsbCPortRosterContext
from .usb_data_path_models import UsbDataPathMap
from .usb_peer_reference_types import UsbPeerReferenceScan


class LegacyCandidateArguments(TypedDict, total=False):
    """Keyword-only compatibility inputs grouped into the typed scanner request."""

    schematic_geometry: SchematicGeometryScan | None
    i2c_address_coverage: I2cAddressCoverageReport | None
    external_protection_coverage: ExternalProtectionCoverageReport | None
    crystal_network_coverage: CrystalNetworkCoverageReport | None
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport | None
    signal_divider_coverage: SignalDividerCoverageReport | None
    rc_filter_coverage: RcFilterCoverageReport | None
    connector_return_distribution: ConnectorReturnDistributionCoverageReport | None
    pcb_decoupling_coverage: PcbDecouplingCoverageReport | None
    pcb_protection_path_coverage: PcbProtectionPathCoverageReport | None
    pcb_track_width_coverage: PcbTrackWidthCoverageReport | None
    pcb_switching_loop_coverage: PcbSwitchingLoopCoverageReport | None
    pcb_differential_pair_coverage: PcbDifferentialPairRuleCoverageReport | None
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None
    i2c_address_map: I2cAddressMap | None
    usb_data_path_map: UsbDataPathMap | None
    stm32_pin_map_coverage: Stm32PinMapCoverageReport | None
    spi_roster: SpiRosterContext | None
    usb_c_port_roster: UsbCPortRosterContext | None
    power_path_map: PowerPathMap | None
    power_sequence_map: PowerSequenceMap | None
    pcb_reference_plane_coverage: PcbReferencePlaneCoverageReport | None
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage | None
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None
    digital_peer_voltage_context: DigitalPeerVoltageLintContext | None
    component_role_map: ComponentRoleMap | None
    serial_peer_roster: SerialPeerRosterContext | None
    reviewed_connector_references: tuple[str, ...]
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution | None
    connector_coverage: ConnectorCoverageReport | None
    digital_peer_voltage_scan: DigitalPeerVoltageScan | None
    usb_peer_reference_scan: UsbPeerReferenceScan | None
    serial_peer_reference_scan: SerialPeerReferenceScan | None
    pcb_signal_path_coverage: PcbSignalPathRuleCoverageReport | None
    pcb_keepout_coverage: PcbKeepoutCoverageReport | None
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport | None
    pcb_touch_pad_clearance_coverage: PcbTouchPadClearanceCoverageReport | None
    peer_pin_assignment_scans: ComponentPeerPinAssignmentScans | None
    pcb_component_inventory_coverage: PcbComponentInventoryCoverageReport | None
    i2c_peer_reference_scan: I2cPeerReferenceScan | None
    spi_peer_reference_scan: SpiPeerReferenceScan | None
    can_peer_reference_scan: CanPeerReferenceScan | None
    rs485_peer_reference_scan: Rs485PeerReferenceScan | None
    peer_power_output_review_enabled: bool
    connector_power_output_review_enabled: bool
    ic_decoupling_map: IcDecouplingMap | None
    oscillator_output_path_map: OscillatorOutputPathMap | None
    connector_stateful_contact_map: ConnectorStatefulContactMap | None
    led_current_map: LedCurrentMap | None
    netlist_sha256: str | None
