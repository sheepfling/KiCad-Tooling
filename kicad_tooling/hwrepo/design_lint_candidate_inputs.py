"""Required capability groups passed to the shared design-lint scanner."""

from __future__ import annotations

from dataclasses import dataclass

from .component_peer_pin_scan import ComponentPeerPinAssignmentScans
from .component_role_models import ComponentRoleMap
from .connector_coverage_models import ConnectorCoverageReport
from .connector_return_distribution_models import ConnectorReturnDistributionCoverageReport
from .connector_stateful_contact_models import ConnectorStatefulContactMap
from .control_input_models import ControlInputBiasHeuristicCoverage
from .crystal_network_models import CrystalNetworkCoverageReport
from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_rule_models import DesignLintRuleCatalog
from .design_lint_types import Candidate
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext, DigitalPeerVoltageScan
from .external_protection_models import ExternalProtectionCoverageReport
from .ic_decoupling_models import IcDecouplingMap
from .models import NetlistContract
from .oscillator_output_path_models import OscillatorOutputPathMap
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageReport,
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
from .schematic_geometry import SchematicGeometryScan
from .serial_participants import SerialPeerRosterContext
from .serial_peer_reference_types import SerialPeerReferenceScan
from .stm32_pin_map_models import Stm32PinMapCoverageReport
from .usb_c_ports import UsbCPortRosterContext
from .usb_data_path_models import UsbDataPathMap
from .usb_peer_reference_types import UsbPeerReferenceScan


@dataclass(frozen=True, slots=True)
class ConnectorCandidateInputs:
    """Connector evidence and explicit review controls for connector rules."""

    coverage: ConnectorCoverageReport | None
    return_distribution: ConnectorReturnDistributionCoverageReport | None
    stateful_contact_map: ConnectorStatefulContactMap | None
    power_output_review_enabled: bool


@dataclass(frozen=True, slots=True)
class ComponentCandidateInputs:
    """Component requirements and shared pin-assignment evidence."""

    peer_pin_assignment_scans: ComponentPeerPinAssignmentScans | None
    peer_power_output_review_enabled: bool


@dataclass(frozen=True, slots=True)
class ControlCandidateInputs:
    """Control-input coverage resolved for one candidate pass."""

    input_bias_coverage: ControlInputBiasHeuristicCoverage | None


@dataclass(frozen=True, slots=True)
class PowerCandidateInputs:
    """Authored power, role, decoupling, and sequencing requirements."""

    component_role_map: ComponentRoleMap | None
    power_path_map: PowerPathMap | None
    power_sequence_map: PowerSequenceMap | None
    oscillator_output_path_map: OscillatorOutputPathMap | None
    ic_decoupling_map: IcDecouplingMap | None


@dataclass(frozen=True, slots=True)
class PeerCandidateInputs:
    """Protocol and digital-peer scans resolved for one candidate pass."""

    digital_voltage_context: DigitalPeerVoltageLintContext | None
    digital_voltage_scan: DigitalPeerVoltageScan | None
    usb_reference_scan: UsbPeerReferenceScan | None
    serial_reference_scan: SerialPeerReferenceScan | None
    serial_roster: SerialPeerRosterContext | None
    usb_c_port_roster: UsbCPortRosterContext | None


@dataclass(frozen=True, slots=True)
class MappedCandidateInputs:
    """Source-bound schematic and mapped electrical requirement reports."""

    external_protection: ExternalProtectionCoverageReport | None
    crystal_network: CrystalNetworkCoverageReport | None
    regulator_feedback: RegulatorFeedbackCoverageReport | None
    rc_filter: RcFilterCoverageReport | None


@dataclass(frozen=True, slots=True)
class PcbCandidateInputs:
    """Native PCB measurement and authored requirement coverage."""

    component_inventory: PcbComponentInventoryCoverageReport | None
    decoupling: PcbDecouplingCoverageReport | None
    protection_path: PcbProtectionPathCoverageReport | None
    track_width: PcbTrackWidthCoverageReport | None
    reference_plane: PcbReferencePlaneCoverageReport | None
    switching_loop: PcbSwitchingLoopCoverageReport | None
    differential_pair: PcbDifferentialPairRuleCoverageReport | None
    signal_path: PcbSignalPathRuleCoverageReport | None
    keepout: PcbKeepoutCoverageReport | None
    rf_antenna: PcbRfModuleAntennaCoverageReport | None
    touch_pad_clearance: PcbTouchPadClearanceCoverageReport | None
    stm32_pin_map: Stm32PinMapCoverageReport | None


@dataclass(frozen=True, slots=True)
class DesignLintCandidateInputs:
    """All required theme groups for shared legacy and prepared scans."""

    observed: NetlistContract
    catalog: DesignLintRuleCatalog | None
    schematic_geometry: SchematicGeometryScan | None
    reviewed_connector_references: tuple[str, ...]
    connector: ConnectorCandidateInputs
    component: ComponentCandidateInputs
    control: ControlCandidateInputs
    power: PowerCandidateInputs
    bus: BusCandidateInputs
    peer: PeerCandidateInputs
    mapped: MappedCandidateInputs
    pcb: PcbCandidateInputs
    usb_data_path_map: UsbDataPathMap | None
    additional_candidates: tuple[Candidate, ...] = ()
