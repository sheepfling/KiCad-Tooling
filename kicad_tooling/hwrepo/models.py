"""Typed, strict records for repository inputs, policy outputs and generated views."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

from . import analysis_state_models as _analysis_state_models
from . import can_termination_models as _can_termination_models
from . import component_peer_pin_models as _component_peer_pin_models
from . import component_rating_models as _component_rating_models
from . import component_role_models as _component_role_models
from . import connector_contact_rating_models as _connector_contact_rating_models
from . import connector_coverage_models as _connector_coverage_models
from . import connector_peer_pin_models as _connector_peer_pin_models
from . import connector_return_distribution_models as _connector_return_distribution_models
from . import control_input_models as _control_input_models
from . import crystal_network_models as _crystal_network_models
from . import design_lint_finding_models as _design_lint_finding_models
from . import design_lint_mapped_topology_models as _design_lint_mapped_topology_models
from . import design_lint_policy_models as _design_lint_policy_models
from . import design_lint_rule_models as _design_lint_rule_models
from . import design_lint_rule_types as _design_lint_rule_types
from . import digital_peer_voltage_models as _digital_peer_voltage_models
from . import electrical_analysis_contract_models as _electrical_analysis_contract_models
from . import electrical_simulation_models as _electrical_simulation_models
from . import external_protection_models as _external_protection_models
from . import grounding_models as _grounding_models
from . import i2c_address_models as _i2c_address_models
from . import i2c_pullup_models as _i2c_pullup_models
from . import mosfet_stress_models as _mosfet_stress_models
from . import pcb_connectivity_observations as _pcb_connectivity_observations
from . import pcb_connectivity_snapshot as _pcb_connectivity_snapshot
from . import pcb_decoupling_models as _pcb_decoupling_models
from . import pcb_drc_models as _pcb_drc_models
from . import pcb_keepout_models as _pcb_keepout_models
from . import pcb_protection_path_models as _pcb_protection_path_models
from . import pcb_reference_plane_models as _pcb_reference_plane_models
from . import pcb_return_path_models as _pcb_return_path_models
from . import pcb_rf_antenna_models as _pcb_rf_antenna_models
from . import pcb_switching_loop_models as _pcb_switching_loop_models
from . import pcb_test_access_models as _pcb_test_access_models
from . import pcb_track_width_models as _pcb_track_width_models
from . import pin_connectivity_models as _pin_connectivity_models
from . import power_connectivity_models as _power_connectivity_models
from . import power_path_models as _power_path_models
from . import power_rail_models as _power_rail_models
from . import power_sequence_models as _power_sequence_models
from . import rc_filter_models as _rc_filter_models
from . import reference_bond_models as _reference_bond_models
from . import regulator_feedback_models as _regulator_feedback_models
from . import return_net_models as _return_net_models
from . import rs485_models as _rs485_models
from . import schematic_geometry_models as _schematic_geometry_models
from . import serial_logic_models as _serial_logic_models
from . import serial_peer_models as _serial_peer_models
from . import serial_peer_reference_models as _serial_peer_reference_models
from . import signal_pair_models as _signal_pair_models
from . import spi_models as _spi_models
from . import stm32_pin_map_models as _stm32_pin_map_models
from . import usb_c_models as _usb_c_models
from . import usb_data_path_models as _usb_data_path_models
from . import usb_peer_reference_models as _usb_peer_reference_models
from . import usb_reference_pin_models as _usb_reference_pin_models
from .model_primitives import (
    Digest,
    ElectricalPositive,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    FiniteMeasure,
    GitCommit,
    Identifier,
    NativePcbUuid,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    NetName,
    NonEmptyText,
    NonNegativeCount,
    NonNegativeMeasure,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    PositiveCount,
    PositiveMeasure,
    Reference,
    RepositoryPath,
    Stm32PortPin,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    Stm32SymbolPin,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    StrictModel,
    TemplateVersion,
)
from .netlist_contract_inputs import NetlistRawValue, normalize_native_unconnected_nets

CrystalLoadCapRequirement = _crystal_network_models.CrystalLoadCapRequirement
CrystalNetworkRequirement = _crystal_network_models.CrystalNetworkRequirement
CrystalNetworkMap = _crystal_network_models.CrystalNetworkMap
CrystalNetworkCoverageEntry = _crystal_network_models.CrystalNetworkCoverageEntry
CrystalNetworkCoverageReport = _crystal_network_models.CrystalNetworkCoverageReport

AnalysisPending = _analysis_state_models.AnalysisPending
AnalysisNotApplicable = _analysis_state_models.AnalysisNotApplicable
ConnectorInterfaceReview = _connector_coverage_models.ConnectorInterfaceReview
ConnectorInventoryReview = _connector_coverage_models.ConnectorInventoryReview
ElectricalAnalysisContract = _electrical_analysis_contract_models.ElectricalAnalysisContract
SpiceExpression = _electrical_simulation_models.SpiceExpression
PowerLoad = _electrical_simulation_models.PowerLoad
PowerRail = _electrical_simulation_models.PowerRail
SimulationMeasure = _electrical_simulation_models.SimulationMeasure
SimulationModel = _electrical_simulation_models.SimulationModel
TransientAnalysis = _electrical_simulation_models.TransientAnalysis
FrequencyAnalysis = _electrical_simulation_models.FrequencyAnalysis
PowerAnalysis = _electrical_simulation_models.PowerAnalysis
HighFrequencyAnalysis = _electrical_simulation_models.HighFrequencyAnalysis
UsbCcResistorAttachment = _usb_c_models.UsbCcResistorAttachment
UsbCcControllerAttachment = _usb_c_models.UsbCcControllerAttachment
UsbCcAttachment = _usb_c_models.UsbCcAttachment
UsbCcLineRequirement = _usb_c_models.UsbCcLineRequirement
UsbCControllerRequirement = _usb_c_models.UsbCControllerRequirement
UsbCNetPinAssignment = _usb_c_models.UsbCNetPinAssignment
UsbCVbusPathElement = _usb_c_models.UsbCVbusPathElement
UsbCVbusPathRequirement = _usb_c_models.UsbCVbusPathRequirement
UsbCProtectionComponentRequirement = _usb_c_models.UsbCProtectionComponentRequirement
UsbCProtectionAnalysis = _usb_c_models.UsbCProtectionAnalysis
UsbCVbusCapacitorRequirement = _usb_c_models.UsbCVbusCapacitorRequirement
UsbCVbusCapacitanceRequirement = _usb_c_models.UsbCVbusCapacitanceRequirement
UsbCPortRequirement = _usb_c_models.UsbCPortRequirement
UsbCAnalysis = _usb_c_models.UsbCAnalysis
Stm32PinRequirement = _stm32_pin_map_models.Stm32PinRequirement
Stm32PinExclusion = _stm32_pin_map_models.Stm32PinExclusion
Stm32CubeMxPinMap = _stm32_pin_map_models.Stm32CubeMxPinMap
Stm32PinMapMismatch = _stm32_pin_map_models.Stm32PinMapMismatch
Stm32UnmappedDevice = _stm32_pin_map_models.Stm32UnmappedDevice
Stm32PinMapCoverageReport = _stm32_pin_map_models.Stm32PinMapCoverageReport
RegulatorDividerResistorRequirement = _regulator_feedback_models.RegulatorDividerResistorRequirement
RegulatorFeedbackRequirement = _regulator_feedback_models.RegulatorFeedbackRequirement
RegulatorFeedbackMap = _regulator_feedback_models.RegulatorFeedbackMap
RcFilterRequirement = _rc_filter_models.RcFilterRequirement
RcFilterMap = _rc_filter_models.RcFilterMap
RcFilterCoverageEntry = _rc_filter_models.RcFilterCoverageEntry
RcFilterCoverageReport = _rc_filter_models.RcFilterCoverageReport
RegulatorFeedbackCoverageEntry = _regulator_feedback_models.RegulatorFeedbackCoverageEntry
RegulatorFeedbackCoverageReport = _regulator_feedback_models.RegulatorFeedbackCoverageReport
ComplementaryPinFunctionAlias = _signal_pair_models.ComplementaryPinFunctionAlias
ComplementaryPinFunctionAliasMap = _signal_pair_models.ComplementaryPinFunctionAliasMap
DesignLintPolicy = _design_lint_policy_models.DesignLintPolicy
DesignLintMappedCheckRun = _design_lint_mapped_topology_models.DesignLintMappedCheckRun
ComponentVoltageRatingRequirement = _component_rating_models.ComponentVoltageRatingRequirement
ComponentVoltageRatingAnalysis = _component_rating_models.ComponentVoltageRatingAnalysis
ComponentPowerRatingRequirement = _component_rating_models.ComponentPowerRatingRequirement
ComponentPowerRatingAnalysis = _component_rating_models.ComponentPowerRatingAnalysis
ComponentRolePin = _component_role_models.ComponentRolePin
ComponentRoleBinding = _component_role_models.ComponentRoleBinding
ComponentRoleMap = _component_role_models.ComponentRoleMap
ConnectorContactCurrentRequirement = (
    _connector_contact_rating_models.ConnectorContactCurrentRequirement
)
ConnectorContactRatingRequirement = (
    _connector_contact_rating_models.ConnectorContactRatingRequirement
)
ConnectorContactRatingAnalysis = _connector_contact_rating_models.ConnectorContactRatingAnalysis
ConnectorReturnDistributionRequirement = (
    _connector_return_distribution_models.ConnectorReturnDistributionRequirement
)
ConnectorReturnDistributionMap = (
    _connector_return_distribution_models.ConnectorReturnDistributionMap
)
ConnectorReturnDistributionEntry = (
    _connector_return_distribution_models.ConnectorReturnDistributionEntry
)
ConnectorReturnDistributionCoverageReport = (
    _connector_return_distribution_models.ConnectorReturnDistributionCoverageReport
)
MosfetVoltageInterval = _mosfet_stress_models.MosfetVoltageInterval
MosfetOperatingState = _mosfet_stress_models.MosfetOperatingState
MosfetStressRequirement = _mosfet_stress_models.MosfetStressRequirement
MosfetStressAnalysis = _mosfet_stress_models.MosfetStressAnalysis
ControlInputBiasHeuristicEntry = _control_input_models.ControlInputBiasHeuristicEntry
ControlInputBiasHeuristicCoverage = _control_input_models.ControlInputBiasHeuristicCoverage
ControlElectricalType = _control_input_models.ControlElectricalType
ControlPinRequirement = _control_input_models.ControlPinRequirement
ControlBiasArrayChannelRequirement = _control_input_models.ControlBiasArrayChannelRequirement
ControlBiasResistorArrayRequirement = _control_input_models.ControlBiasResistorArrayRequirement
ControlBiasResistorRequirement = _control_input_models.ControlBiasResistorRequirement
ControlLocalBiasRequirement = _control_input_models.ControlLocalBiasRequirement
ControlInternalBiasRequirement = _control_input_models.ControlInternalBiasRequirement
ControlExternalBiasRequirement = _control_input_models.ControlExternalBiasRequirement
ControlNoBiasRequirement = _control_input_models.ControlNoBiasRequirement
ControlBiasRequirement = _control_input_models.ControlBiasRequirement
ControlSignalRequirement = _control_input_models.ControlSignalRequirement
ControlInputsAnalysis = _control_input_models.ControlInputsAnalysis
ExternalProtectionChannelRequirement = (
    _external_protection_models.ExternalProtectionChannelRequirement
)
ExternalProtectionInterfaceRequirement = (
    _external_protection_models.ExternalProtectionInterfaceRequirement
)
ExternalProtectionDeviceRequirement = (
    _external_protection_models.ExternalProtectionDeviceRequirement
)
ExternalProtectionMap = _external_protection_models.ExternalProtectionMap
ExternalProtectionCoverageEntry = _external_protection_models.ExternalProtectionCoverageEntry
ExternalProtectionCoverageReport = _external_protection_models.ExternalProtectionCoverageReport
ComponentPeerPinRuleCoverage = _component_peer_pin_models.ComponentPeerPinRuleCoverage
ConnectorPinRole = _connector_peer_pin_models.ConnectorPinRole
SimilarConnectorPinGroup = _connector_peer_pin_models.SimilarConnectorPinGroup
ConnectorPartIdPeerPinCoverage = _connector_peer_pin_models.ConnectorPartIdPeerPinCoverage
ConnectorPeerPinHeuristicCoverage = _connector_peer_pin_models.ConnectorPeerPinHeuristicCoverage
DigitalPeerVoltageRuleCoverage = _digital_peer_voltage_models.DigitalPeerVoltageRuleCoverage
SerialPeerReferenceCoverageReport = _serial_peer_reference_models.SerialPeerReferenceCoverageReport
SerialPeerReferenceLinkCoverageEntry = (
    _serial_peer_reference_models.SerialPeerReferenceLinkCoverageEntry
)
UsbPeerDataLineCoverage = _usb_peer_reference_models.UsbPeerDataLineCoverage
UsbPeerDataPathCoverage = _usb_peer_reference_models.UsbPeerDataPathCoverage
UsbPeerDataSeriesResistorCoverage = _usb_peer_reference_models.UsbPeerDataSeriesResistorCoverage
UsbPeerDataShuntBranchCoverage = _usb_peer_reference_models.UsbPeerDataShuntBranchCoverage
UsbPeerEndpointGroupCoverage = _usb_peer_reference_models.UsbPeerEndpointGroupCoverage
UsbPeerReferenceCoverageReport = _usb_peer_reference_models.UsbPeerReferenceCoverageReport
UsbPeerReferencePathCoverageEntry = _usb_peer_reference_models.UsbPeerReferencePathCoverageEntry
UsbPeerReferencePinCoverage = _usb_peer_reference_models.UsbPeerReferencePinCoverage
UsbDataSeriesResistorRequirement = _usb_data_path_models.UsbDataSeriesResistorRequirement
UsbDataPathLineRequirement = _usb_data_path_models.UsbDataPathLineRequirement
UsbReferencePinRequirement = _usb_reference_pin_models.UsbReferencePinRequirement
UsbDataInterfaceRequirement = _usb_data_path_models.UsbDataInterfaceRequirement
UsbDataPathMap = _usb_data_path_models.UsbDataPathMap
PcbReturnEndpointRequirement = _pcb_return_path_models.PcbReturnEndpointRequirement
PcbReturnBondRequirement = _pcb_return_path_models.PcbReturnBondRequirement
PcbReturnDomainRequirement = _pcb_return_path_models.PcbReturnDomainRequirement
PcbReturnPathsAnalysis = _pcb_return_path_models.PcbReturnPathsAnalysis
GroundDomain = _grounding_models.GroundDomain
GroundingAnalysis = _grounding_models.GroundingAnalysis
PinRelationshipRule = _pin_connectivity_models.PinRelationshipRule
PinConnectivityAnalysis = _pin_connectivity_models.PinConnectivityAnalysis
PowerPathEndpointRequirement = _power_path_models.PowerPathEndpointRequirement
PowerPathElementRequirement = _power_path_models.PowerPathElementRequirement
PowerPathRequirement = _power_path_models.PowerPathRequirement
PowerPathMap = _power_path_models.PowerPathMap
PowerPinEndpointRequirement = _power_connectivity_models.PowerPinEndpointRequirement
PowerSourceGroupRequirement = _power_connectivity_models.PowerSourceGroupRequirement
PowerLoadConnectivityRequirement = _power_connectivity_models.PowerLoadConnectivityRequirement
PowerConnectivityRailRequirement = _power_connectivity_models.PowerConnectivityRailRequirement
PowerConnectivityAnalysis = _power_connectivity_models.PowerConnectivityAnalysis
PowerSequenceEndpointRequirement = _power_sequence_models.PowerSequenceEndpointRequirement
PowerSequenceStageRequirement = _power_sequence_models.PowerSequenceStageRequirement
PowerSequenceDependencyRequirement = _power_sequence_models.PowerSequenceDependencyRequirement
PowerSequenceMap = _power_sequence_models.PowerSequenceMap
PcbAccessProbeObservation = _pcb_connectivity_observations.PcbAccessProbeObservation
PcbFootprintPlacementObservation = _pcb_connectivity_observations.PcbFootprintPlacementObservation
PcbNetTieObservation = _pcb_connectivity_observations.PcbNetTieObservation
PcbPadConnectivityObservation = _pcb_connectivity_observations.PcbPadConnectivityObservation
PcbRuleAreaObservation = _pcb_connectivity_observations.PcbRuleAreaObservation
PcbRuleAreaPolygonObservation = _pcb_connectivity_observations.PcbRuleAreaPolygonObservation
PcbTrackObservation = _pcb_connectivity_observations.PcbTrackObservation
PcbTrackUuid = _pcb_connectivity_observations.PcbTrackUuid
PcbViaObservation = _pcb_connectivity_observations.PcbViaObservation
PcbZoneFilledIslandObservation = _pcb_connectivity_observations.PcbZoneFilledIslandObservation
PcbZoneIdentity = _pcb_connectivity_observations.PcbZoneIdentity
PcbZoneIslandIdentity = _pcb_connectivity_observations.PcbZoneIslandIdentity
PcbZoneObservation = _pcb_connectivity_observations.PcbZoneObservation
PcbConnectivitySnapshot = _pcb_connectivity_snapshot.PcbConnectivitySnapshot
TestAccessProbeEnvelope = _pcb_test_access_models.TestAccessProbeEnvelope
PcbAccessProbeRequest = _pcb_test_access_models.PcbAccessProbeRequest
PcbAccessProbeRequestSet = _pcb_test_access_models.PcbAccessProbeRequestSet
TestAccessEndpointRequirement = _pcb_test_access_models.TestAccessEndpointRequirement
RequiredTestAccess = _pcb_test_access_models.RequiredTestAccess
ExcludedTestAccess = _pcb_test_access_models.ExcludedTestAccess
TestAccessDecision = _pcb_test_access_models.TestAccessDecision
PcbAccessAnalysis = _pcb_test_access_models.PcbAccessAnalysis
TestAccessAnalysis = _pcb_test_access_models.TestAccessAnalysis
PcbDrcMinMaxRequirement = _pcb_drc_models.PcbDrcMinMaxRequirement
PcbDrcMaximumRequirement = _pcb_drc_models.PcbDrcMaximumRequirement
PcbDrcPadSelectorPattern = _pcb_drc_models.PcbDrcPadSelectorPattern
PcbSignalPathRequirement = _pcb_drc_models.PcbSignalPathRequirement
PcbSignalPathBundleRequirement = _pcb_drc_models.PcbSignalPathBundleRequirement
PcbSignalPathRuleMap = _pcb_drc_models.PcbSignalPathRuleMap
PcbDifferentialPairRuleRequirement = _pcb_drc_models.PcbDifferentialPairRuleRequirement
PcbDifferentialPairRuleMap = _pcb_drc_models.PcbDifferentialPairRuleMap
PcbDrcConstraintName = _pcb_drc_models.PcbDrcConstraintName
PcbDrcConstraintCoverageStatus = _pcb_drc_models.PcbDrcConstraintCoverageStatus
PcbDrcConstraintCoverage = _pcb_drc_models.PcbDrcConstraintCoverage
PcbDifferentialPairRuleCoverageEntry = _pcb_drc_models.PcbDifferentialPairRuleCoverageEntry
PcbDifferentialPairRuleCoverageReport = _pcb_drc_models.PcbDifferentialPairRuleCoverageReport
PcbSignalPathRuleCoverageEntry = _pcb_drc_models.PcbSignalPathRuleCoverageEntry
PcbSignalPathRuleCoverageReport = _pcb_drc_models.PcbSignalPathRuleCoverageReport
PcbKeepoutRequirement = _pcb_keepout_models.PcbKeepoutRequirement
PcbKeepoutMap = _pcb_keepout_models.PcbKeepoutMap
PcbKeepoutCoverageEntry = _pcb_keepout_models.PcbKeepoutCoverageEntry
PcbKeepoutCoverageReport = _pcb_keepout_models.PcbKeepoutCoverageReport
PcbDecouplingCapacitor = _pcb_decoupling_models.PcbDecouplingCapacitor
PcbDecouplingRequirement = _pcb_decoupling_models.PcbDecouplingRequirement
PcbDecouplingMap = _pcb_decoupling_models.PcbDecouplingMap
PcbDecouplingCandidateObservation = _pcb_decoupling_models.PcbDecouplingCandidateObservation
PcbDecouplingCoverageEntry = _pcb_decoupling_models.PcbDecouplingCoverageEntry
PcbDecouplingCoverageReport = _pcb_decoupling_models.PcbDecouplingCoverageReport
PcbProtectionPathRequirement = _pcb_protection_path_models.PcbProtectionPathRequirement
PcbProtectionPathMap = _pcb_protection_path_models.PcbProtectionPathMap
PcbProtectionPathEntry = _pcb_protection_path_models.PcbProtectionPathEntry
PcbProtectionPathCoverageReport = _pcb_protection_path_models.PcbProtectionPathCoverageReport
PcbTrackWidthRequirement = _pcb_track_width_models.PcbTrackWidthRequirement
PcbTrackWidthMap = _pcb_track_width_models.PcbTrackWidthMap
PcbTrackWidthMeasurement = _pcb_track_width_models.PcbTrackWidthMeasurement
PcbTrackWidthCoverageEntry = _pcb_track_width_models.PcbTrackWidthCoverageEntry
PcbTrackWidthCoverageReport = _pcb_track_width_models.PcbTrackWidthCoverageReport
PcbReferencePlaneRequirement = _pcb_reference_plane_models.PcbReferencePlaneRequirement
PcbReferencePlaneMap = _pcb_reference_plane_models.PcbReferencePlaneMap
PcbReferencePlaneTrackMeasurement = _pcb_reference_plane_models.PcbReferencePlaneTrackMeasurement
PcbReferencePlaneCoverageEntry = _pcb_reference_plane_models.PcbReferencePlaneCoverageEntry
PcbReferencePlaneCoverageReport = _pcb_reference_plane_models.PcbReferencePlaneCoverageReport
PcbSwitchingLoopPad = _pcb_switching_loop_models.PcbSwitchingLoopPad
PcbSwitchingLoopEdge = _pcb_switching_loop_models.PcbSwitchingLoopEdge
PcbSwitchingLoopRequirement = _pcb_switching_loop_models.PcbSwitchingLoopRequirement
PcbSwitchingLoopMap = _pcb_switching_loop_models.PcbSwitchingLoopMap
PcbSwitchingLoopRouteEdgeCoverage = _pcb_switching_loop_models.PcbSwitchingLoopRouteEdgeCoverage
PcbSwitchingLoopCoverageEntry = _pcb_switching_loop_models.PcbSwitchingLoopCoverageEntry
PcbSwitchingLoopCoverageReport = _pcb_switching_loop_models.PcbSwitchingLoopCoverageReport
PcbRfAntennaKeepout = _pcb_rf_antenna_models.PcbRfAntennaKeepout
PcbRfAntennaPolygon = _pcb_rf_antenna_models.PcbRfAntennaPolygon
PcbRfModuleAntennaCoverageEntry = _pcb_rf_antenna_models.PcbRfModuleAntennaCoverageEntry
PcbRfModuleAntennaCoverageReport = _pcb_rf_antenna_models.PcbRfModuleAntennaCoverageReport
PcbRfModuleAntennaMap = _pcb_rf_antenna_models.PcbRfModuleAntennaMap
PcbRfModuleAntennaRequirement = _pcb_rf_antenna_models.PcbRfModuleAntennaRequirement
DesignLintRuleCatalog = _design_lint_rule_models.DesignLintRuleCatalog
DesignLintRuleCatalogDocument = _design_lint_rule_models.DesignLintRuleCatalogDocument
DesignLintRuleMetadata = _design_lint_rule_models.DesignLintRuleMetadata
DesignLintRuleOverride = _design_lint_finding_models.DesignLintRuleOverride
DesignLintIgnore = _design_lint_finding_models.DesignLintIgnore
DesignLintFinding = _design_lint_finding_models.DesignLintFinding
DesignLintRuleId = _design_lint_rule_types.DesignLintRuleId
DesignLintTheme = _design_lint_rule_types.DesignLintTheme
CanTerminationResistorRequirement = _can_termination_models.CanTerminationResistorRequirement
CanTerminationMidpointCapacitorRequirement = (
    _can_termination_models.CanTerminationMidpointCapacitorRequirement
)
CanTerminationEndpointRequirement = _can_termination_models.CanTerminationEndpointRequirement
CanTerminationBusRequirement = _can_termination_models.CanTerminationBusRequirement
CanTerminationAnalysis = _can_termination_models.CanTerminationAnalysis
SpiPinNetRequirement = _spi_models.SpiPinNetRequirement
SpiPinUnconnectedRequirement = _spi_models.SpiPinUnconnectedRequirement
SpiMisoConnectedRequirement = _spi_models.SpiMisoConnectedRequirement
SpiPinNotPresent = _spi_models.SpiPinNotPresent
SpiMisoRequirement = _spi_models.SpiMisoRequirement
SpiControllerRequirement = _spi_models.SpiControllerRequirement
SpiDeviceRequirement = _spi_models.SpiDeviceRequirement
SpiBridgePathRequirement = _spi_models.SpiBridgePathRequirement
SpiBridgeRequirement = _spi_models.SpiBridgeRequirement
SpiBusRequirement = _spi_models.SpiBusRequirement
SpiAnalysis = _spi_models.SpiAnalysis
SerialPinNetRequirement = _serial_logic_models.SerialPinNetRequirement
SerialLogicOutputLimits = _serial_logic_models.SerialLogicOutputLimits
SerialLogicInputLimits = _serial_logic_models.SerialLogicInputLimits
SerialLogicLimits = _serial_logic_models.SerialLogicLimits
SerialLabelFixtureExpectedNets = _serial_logic_models.SerialLabelFixtureExpectedNets
SerialEndpointRequirement = _serial_peer_models.SerialEndpointRequirement
SerialBridgePathRequirement = _serial_peer_models.SerialBridgePathRequirement
SerialBridgeRequirement = _serial_peer_models.SerialBridgeRequirement
SerialDirectPeerRequirement = _serial_peer_models.SerialDirectPeerRequirement
SerialShiftedPeerRequirement = _serial_peer_models.SerialShiftedPeerRequirement
SerialExternalPeerRequirement = _serial_peer_models.SerialExternalPeerRequirement
SerialPeerRequirement = _serial_peer_models.SerialPeerRequirement
SerialPeerLinkRequirement = _serial_peer_models.SerialPeerLinkRequirement
SerialPeerAnalysis = _serial_peer_models.SerialPeerAnalysis
Rs485EndpointPinRequirement = _rs485_models.Rs485EndpointPinRequirement
Rs485EndpointRequirement = _rs485_models.Rs485EndpointRequirement
Rs485TerminationResistorRequirement = _rs485_models.Rs485TerminationResistorRequirement
Rs485DnpResistorRequirement = _rs485_models.Rs485DnpResistorRequirement
Rs485TerminationEndpointRequirement = _rs485_models.Rs485TerminationEndpointRequirement
Rs485BiasResistorRequirement = _rs485_models.Rs485BiasResistorRequirement
Rs485LocalBiasRequirement = _rs485_models.Rs485LocalBiasRequirement
Rs485RemoteBiasRequirement = _rs485_models.Rs485RemoteBiasRequirement
Rs485InternalFailSafeRequirement = _rs485_models.Rs485InternalFailSafeRequirement
Rs485NoBiasRequirement = _rs485_models.Rs485NoBiasRequirement
Rs485BiasRequirement = _rs485_models.Rs485BiasRequirement
Rs485SignalPairRequirement = _rs485_models.Rs485SignalPairRequirement
Rs485BusRequirement = _rs485_models.Rs485BusRequirement
Rs485Analysis = _rs485_models.Rs485Analysis
ReferenceBondRequirement = _reference_bond_models.ReferenceBondRequirement
DigitalLogicOutputLimits = _digital_peer_voltage_models.DigitalLogicOutputLimits
DigitalLogicInputLimits = _digital_peer_voltage_models.DigitalLogicInputLimits
DigitalPeerPinRequirement = _digital_peer_voltage_models.DigitalPeerPinRequirement
DigitalPeerVoltageLink = _digital_peer_voltage_models.DigitalPeerVoltageLink
DigitalPeerVoltageAnalysis = _digital_peer_voltage_models.DigitalPeerVoltageAnalysis
I2cAddressBitRequirement = _i2c_address_models.I2cAddressBitRequirement
I2cResponderAddressRequirement = _i2c_address_models.I2cResponderAddressRequirement
I2cAddressSegmentRequirement = _i2c_address_models.I2cAddressSegmentRequirement
I2cAddressMap = _i2c_address_models.I2cAddressMap
I2cAddressBitEvidence = _i2c_address_models.I2cAddressBitEvidence
I2cResponderAddressCoverageEntry = _i2c_address_models.I2cResponderAddressCoverageEntry
I2cAddressCoverageReport = _i2c_address_models.I2cAddressCoverageReport
I2cPullupArrayChannelRequirement = _i2c_pullup_models.I2cPullupArrayChannelRequirement
I2cPullupArrayRequirement = _i2c_pullup_models.I2cPullupArrayRequirement
I2cPullupInputVoltageLimit = _i2c_pullup_models.I2cPullupInputVoltageLimit
I2cPullupVoltageCompatibilityRequirement = (
    _i2c_pullup_models.I2cPullupVoltageCompatibilityRequirement
)
I2cPullupElectricalWindow = _i2c_pullup_models.I2cPullupElectricalWindow
I2cPullupLineRequirement = _i2c_pullup_models.I2cPullupLineRequirement
I2cPullupSeriesResistorRequirement = _i2c_pullup_models.I2cPullupSeriesResistorRequirement
I2cPullupSeriesPathRequirement = _i2c_pullup_models.I2cPullupSeriesPathRequirement
I2cPullupBusRequirement = _i2c_pullup_models.I2cPullupBusRequirement
I2cPullupAnalysis = _i2c_pullup_models.I2cPullupAnalysis
I2cPullupHeuristicEntry = _i2c_pullup_models.I2cPullupHeuristicEntry
I2cPullupHeuristicCoverage = _i2c_pullup_models.I2cPullupHeuristicCoverage


class SchematicTextMetricsResource(StrictModel):
    """Pinned KiCad standard-stroke glyph metrics used by schematic review lint."""

    schema_version: Literal["4"]
    kicad_version: Literal["10.0.6"]
    native_image: Literal[
        "kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec"
    ]
    reference_size_mm: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    stroke_width_mm: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    single_glyph_svg_end_spacing_mm: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    line_end_spacing_mm: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    multiline_line_spacing_mm: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    vertical_ink_envelope_ratio: tuple[
        Annotated[float, Field(allow_inf_nan=False)],
        Annotated[float, Field(allow_inf_nan=False)],
    ]
    metrics_method: NonEmptyText
    advances_mm: Mapping[
        Annotated[str, StringConstraints(min_length=1, max_length=1)],
        Annotated[float, Field(gt=0, allow_inf_nan=False)],
    ]

    @model_validator(mode="after")
    def complete_calibrated_glyph_metrics(self) -> SchematicTextMetricsResource:
        expected_characters = {
            " ",
            *(chr(code) for code in range(33, 127)),
            "°",
            "±",
            "µ",
            "×",
            "Ω",
            "—",
        }
        if set(self.advances_mm) != expected_characters:
            raise ValueError("Schematic text metrics must cover the calibrated glyph set exactly")
        top, bottom = self.vertical_ink_envelope_ratio
        if top >= bottom:
            raise ValueError("Schematic text metric vertical envelope is reversed")
        return self


class Assurance(str, Enum):
    UNKNOWN = "unknown"
    ASSUMED = "assumed"
    INFERRED = "inferred"
    OBSERVED = "observed"
    MANUFACTURER_DOCUMENTED = "manufacturer_documented"
    VERIFIED = "verified"
    NOT_APPLICABLE = "not_applicable"


class PartStatus(str, Enum):
    TRAINING = "not_for_manufacture"
    APPROVED = "approved"


class PartCadBinding(StrictModel):
    """Reviewed symbol, value, package and source model for one catalog part."""

    symbol_id: NonEmptyText
    value: NonEmptyText
    footprint: Annotated[str, StringConstraints(pattern=r"^[^:\r\n]+:[^:\r\n]+$")]
    model: RepositoryPath
    digikey_sku: Annotated[str, StringConstraints(min_length=1)] | None = None

    @model_validator(mode="after")
    def exact_sku(self) -> PartCadBinding:
        if self.digikey_sku is not None and (
            self.digikey_sku != self.digikey_sku.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in self.digikey_sku)
        ):
            raise ValueError("DigiKey SKU must be exact text without padding or control characters")
        return self


class PartRecord(StrictModel):
    id: Identifier
    revision: Identifier
    description: NonEmptyText
    part_class: NonEmptyText
    unit: Literal["each"]
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    datasheet_url: NonEmptyText
    lifecycle: NonEmptyText
    status: PartStatus
    approved_alternates: tuple[Identifier, ...] = ()
    cad: PartCadBinding | None = None


class PartsCatalog(StrictModel):
    schema_version: NonEmptyText
    parts: tuple[PartRecord, ...]


class InterfacePin(StrictModel):
    number: NonEmptyText
    signal: NonEmptyText
    role: ConnectorPinRole | None = None
    direction: NonEmptyText
    voltage_domain: NonEmptyText
    mating: NonEmptyText
    orientation: NonEmptyText
    mechanical_clearance: NonEmptyText


class InterfaceRecord(StrictModel):
    id: Identifier
    revision: NonEmptyText
    pins: tuple[InterfacePin, ...]

    @model_validator(mode="after")
    def unique_pin_numbers(self) -> InterfaceRecord:
        if len({pin.number for pin in self.pins}) != len(self.pins):
            raise ValueError("Interface pin numbers must be unique")
        return self


class InterfacesCatalog(StrictModel):
    schema_version: NonEmptyText
    interfaces: tuple[InterfaceRecord, ...]


class LibraryRecord(StrictModel):
    id: Identifier
    version: NonEmptyText
    path: RepositoryPath
    owner: NonEmptyText
    status: NonEmptyText
    provenance_path: RepositoryPath
    provenance_sha256: Digest
    licensing_path: RepositoryPath
    licensing_sha256: Digest


class LibrariesCatalog(StrictModel):
    schema_version: NonEmptyText
    libraries: tuple[LibraryRecord, ...]


class LibrarySbom(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    libraries: tuple[LibraryRecord, ...]


class ToolchainRecord(StrictModel):
    id: Identifier
    kicad_version: NonEmptyText
    cli_profile: Literal["kicad-10"] | None = None
    image: NonEmptyText
    desktop_edit_policy: NonEmptyText
    installer_source: NonEmptyText
    migration_policy: NonEmptyText


class ToolchainsCatalog(StrictModel):
    schema_version: NonEmptyText
    toolchains: tuple[ToolchainRecord, ...]


class ComponentIdentity(StrictModel):
    required: bool
    part_ids: tuple[Identifier, ...]


class ProjectKind(str, Enum):
    """The engineering deliverable represented by one native KiCad project."""

    PCB = "pcb"
    PCB_ONLY = "pcb_only"
    SCHEMATIC = "schematic"
    SYSTEM_WIRING = "system_wiring"
    HARNESS_INTERFACE = "harness_interface"

    @property
    def domain_name(self) -> str:
        """Return the human-facing directory name for this design kind."""
        return {
            ProjectKind.PCB: "pcb",
            ProjectKind.PCB_ONLY: "pcb-only",
            ProjectKind.SCHEMATIC: "schematic",
            ProjectKind.SYSTEM_WIRING: "system-wiring",
            ProjectKind.HARNESS_INTERFACE: "harness-interface",
        }[self]

    @property
    def design_root(self) -> str:
        """Return the canonical root for adopted-repository project sources."""
        return "projects"

    @property
    def example_root(self) -> str:
        """Return the fixture root used by this template's reference projects."""
        return f"examples/{self.design_root}"

    @property
    def accepted_roots(self) -> tuple[str, str]:
        """Return canonical and template-fixture roots accepted by repository policy."""
        return (self.design_root, self.example_root)


class ProjectRecord(StrictModel):
    id: Identifier
    kind: ProjectKind
    status: Literal["training_fixture", "engineering", "release_candidate"]
    assurance_profile: Literal["training", "development", "production"]
    config: RepositoryPath
    project: RepositoryPath
    component_identity: ComponentIdentity
    tags: tuple[Identifier, ...] = ()
    interfaces: tuple[Identifier, ...] = ()
    library_ids: tuple[Identifier, ...] = ()
    mechanical_handoff: RepositoryPath | None = None
    governance_record: RepositoryPath | None = None


class CatalogPaths(StrictModel):
    parts: RepositoryPath
    interfaces: RepositoryPath
    libraries: RepositoryPath
    toolchains: RepositoryPath
    release_policies: RepositoryPath


class ProjectRegistry(StrictModel):
    schema_version: NonEmptyText
    catalogs: CatalogPaths
    projects: tuple[ProjectRecord, ...]


class ComponentContract(StrictModel):
    value: NonEmptyText
    footprint: str
    part_id: Identifier | None = None


class IgnoredChecks(StrictModel):
    erc: tuple[Identifier, ...]
    drc: tuple[Identifier, ...]


class PcbValidationContract(StrictModel):
    """Native checks and independent electrical contract for a board deliverable."""

    kind: Literal[ProjectKind.PCB]
    components: Mapping[Identifier, ComponentContract]
    nets: Mapping[NetName, tuple[Reference, ...]]
    expected_ignored_checks: IgnoredChecks


class PcbOnlyValidationContract(StrictModel):
    """Native board-layout checks where no authoritative schematic is available."""

    kind: Literal[ProjectKind.PCB_ONLY]
    expected_ignored_checks: IgnoredChecks


class SchematicValidationContract(StrictModel):
    """Native checks for a schematic-only deliverable with no manufactured PCB."""

    kind: Literal[ProjectKind.SCHEMATIC]
    components: Mapping[Identifier, ComponentContract] = Field(default_factory=dict)
    nets: Mapping[NetName, tuple[Reference, ...]] = Field(default_factory=dict)
    expected_ignored_checks: IgnoredChecks


class ProductTraceabilityValidationContract(StrictModel):
    """Shared typed authority for KiCad product, wiring, and harness review views."""

    product_id: Identifier
    connection_ids: tuple[Identifier, ...]
    terminal_ids: tuple[Identifier, ...]
    harness_ids: tuple[Identifier, ...]
    expected_ignored_checks: IgnoredChecks

    def require_complete_unique_coverage(self, *extra: tuple[str, tuple[str, ...]]) -> None:
        for label, values in (
            ("connection_ids", self.connection_ids),
            ("terminal_ids", self.terminal_ids),
            ("harness_ids", self.harness_ids),
            *extra,
        ):
            if not values:
                raise ValueError(f"{label} must not be empty for a product traceability view")
            if len(set(values)) != len(values):
                raise ValueError(f"{label} must not contain duplicates")


class SystemWiringValidationContract(ProductTraceabilityValidationContract):
    """Trace a whole-system KiCad view to every typed product relationship."""

    kind: Literal[ProjectKind.SYSTEM_WIRING]
    mechanical_handoff_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def complete_unique_coverage(self) -> SystemWiringValidationContract:
        self.require_complete_unique_coverage(
            ("mechanical_handoff_ids", self.mechanical_handoff_ids)
        )
        return self


class HarnessInterfaceValidationContract(ProductTraceabilityValidationContract):
    """Trace a harness-interface sheet to only its owned electrical conductors."""

    kind: Literal[ProjectKind.HARNESS_INTERFACE]

    @model_validator(mode="after")
    def complete_unique_coverage(self) -> HarnessInterfaceValidationContract:
        self.require_complete_unique_coverage()
        return self


ProjectValidationContract = Annotated[
    PcbValidationContract
    | PcbOnlyValidationContract
    | SchematicValidationContract
    | SystemWiringValidationContract
    | HarnessInterfaceValidationContract,
    Field(discriminator="kind"),
]


SchematicGeometryRuleId = _schematic_geometry_models.SchematicGeometryRuleId
SchematicGeometryRuleCoverageStatus = _schematic_geometry_models.SchematicGeometryRuleCoverageStatus
SchematicGeometrySourceBinding = _schematic_geometry_models.SchematicGeometrySourceBinding
SchematicGeometryCoverage = _schematic_geometry_models.SchematicGeometryCoverage


class ProjectConfig(StrictModel):
    schema_version: NonEmptyText
    kind: ProjectKind
    assurance_profile: Literal["training", "development", "production"]
    not_for_manufacture: bool
    project_id: Identifier
    component_identity: ComponentIdentity
    toolchain_id: Identifier
    kicad_version: NonEmptyText
    cli_profile: Literal["kicad-10"] | None = None
    image: NonEmptyText
    project: RepositoryPath
    source_roots: tuple[RepositoryPath, ...]
    required_inputs: tuple[RepositoryPath, ...]
    validation: ProjectValidationContract
    electrical: RepositoryPath | None = None
    design_lint: DesignLintPolicy | None = None
    interfaces: tuple[Identifier, ...] = ()
    connector_reviews: tuple[ConnectorInterfaceReview, ...] = ()
    connector_inventory_review: ConnectorInventoryReview | None = None

    @model_validator(mode="after")
    def matching_project_kind(self) -> ProjectConfig:
        if self.kind is not self.validation.kind:
            raise ValueError("project kind must match validation contract kind")
        if (
            self.design_lint is not None
            and (
                self.design_lint.pcb_decoupling_map is not None
                or self.design_lint.pcb_protection_path_map is not None
                or self.design_lint.pcb_track_width_map is not None
                or self.design_lint.pcb_reference_plane_map is not None
                or self.design_lint.pcb_switching_loop_map is not None
                or self.design_lint.pcb_differential_pair_rule_map is not None
                or self.design_lint.pcb_signal_path_rule_map is not None
                or self.design_lint.pcb_mechanical_edge_clearance_map is not None
                or self.design_lint.pcb_keepout_map is not None
                or self.design_lint.pcb_rf_module_antenna_map is not None
                or self.design_lint.pcb_touch_pad_clearance_map is not None
            )
            and self.kind is not ProjectKind.PCB
        ):
            raise ValueError("PCB geometry maps require an authoritative PCB project")
        return self


class ProjectDiscovery(StrictModel):
    """Repository-wide dependencies and roots; project records live with boards."""

    schema_version: Literal["1"] = "1"
    catalogs: CatalogPaths
    project_roots: Annotated[tuple[RepositoryPath, ...], Field(min_length=1)]
    project_depth: Annotated[int, Field(ge=1, le=8)] = 1

    @model_validator(mode="after")
    def unique_project_roots(self) -> ProjectDiscovery:
        if len({name.casefold() for name in self.project_roots}) != len(self.project_roots):
            raise ValueError("Discovery roots must be unique")
        return self


class ReleaseExportSettings(StrictModel):
    """Manufacturer-facing settings reviewed with each board's source."""

    gerber_layers: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    coordinate_origin: Literal["absolute", "plot"] = "absolute"
    position_units: Literal["mm", "in"] = "mm"
    assembly_variant: NonEmptyText | None = None
    supplier_formats: tuple[Literal["odb", "ipc2581", "ipcd356"], ...] = ()

    @model_validator(mode="after")
    def unique_supplier_formats(self) -> ReleaseExportSettings:
        if len(set(self.supplier_formats)) != len(self.supplier_formats):
            raise ValueError("supplier_formats must not contain duplicates")
        return self


class ProjectManifest(StrictModel):
    """Authored project-local inputs. Shared paths are explicitly repository-relative."""

    schema_version: Literal["1"] = "1"
    id: Identifier
    kind: ProjectKind
    status: Literal["training_fixture", "engineering", "release_candidate"]
    assurance_profile: Literal["training", "development", "production"]
    toolchain_id: Identifier
    project: RepositoryPath
    source_roots: tuple[RepositoryPath, ...]
    required_inputs: tuple[RepositoryPath, ...]
    checks: RepositoryPath = "tests/contract.json"
    shared_source_roots: tuple[RepositoryPath, ...] = ()
    shared_inputs: tuple[RepositoryPath, ...] = ()
    component_identity: ComponentIdentity
    tags: tuple[Identifier, ...] = ()
    interfaces: tuple[Identifier, ...] = ()
    connector_reviews: tuple[ConnectorInterfaceReview, ...] = ()
    connector_inventory_review: ConnectorInventoryReview | None = None
    library_ids: tuple[Identifier, ...] = ()
    mechanical_handoff: RepositoryPath | None = None
    governance_record: RepositoryPath | None = None
    release_exports: ReleaseExportSettings | None = None

    @model_validator(mode="after")
    def unique_connector_reviews(self) -> ProjectManifest:
        references = [item.reference.casefold() for item in self.connector_reviews]
        if len(set(references)) != len(references):
            raise ValueError("Connector review references must be unique")
        if len(set(self.interfaces)) != len(self.interfaces):
            raise ValueError("Project interface IDs must be unique")
        interface_ids = {
            item.interface_id for item in self.connector_reviews if item.interface_id is not None
        }
        if not interface_ids <= set(self.interfaces):
            raise ValueError("Connector reviews must reference declared project interfaces")
        return self


class ProjectTestContract(StrictModel):
    schema_version: Literal["1"] = "1"
    validation: ProjectValidationContract
    electrical: RepositoryPath | None = None
    design_lint: DesignLintPolicy | None = None

    @model_validator(mode="after")
    def lint_requires_netlist(self) -> ProjectTestContract:
        if self.design_lint is not None and self.validation.kind not in {
            ProjectKind.PCB,
            ProjectKind.SCHEMATIC,
        }:
            raise ValueError("design_lint requires a pcb or schematic netlist")
        if (
            self.design_lint is not None
            and (
                self.design_lint.pcb_decoupling_map is not None
                or self.design_lint.pcb_protection_path_map is not None
                or self.design_lint.pcb_track_width_map is not None
                or self.design_lint.pcb_reference_plane_map is not None
                or self.design_lint.pcb_switching_loop_map is not None
                or self.design_lint.pcb_differential_pair_rule_map is not None
                or self.design_lint.pcb_signal_path_rule_map is not None
                or self.design_lint.pcb_mechanical_edge_clearance_map is not None
                or self.design_lint.pcb_keepout_map is not None
                or self.design_lint.pcb_rf_module_antenna_map is not None
                or self.design_lint.pcb_touch_pad_clearance_map is not None
            )
            and self.validation.kind is not ProjectKind.PCB
        ):
            raise ValueError("PCB geometry maps require an authoritative PCB project")
        return self


class ProjectScaffoldReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    directory: str
    issues: tuple[str, ...] = ()
    next_step: str = "Create the native KiCad design, then complete the test contract and run kicad_tooling.verify."


class ProjectImportReport(StrictModel):
    """Import receipt; copying source is separate from accepting its engineering checks."""

    status: Literal["PASS", "FAIL"]
    directory: str
    source_project: str
    dry_run: bool
    copied_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    excluded: Mapping[RepositoryPath, str] = Field(default_factory=dict)
    issues: tuple[str, ...] = ()
    review_required: Literal[True] = True
    next_step: str = "Review dependencies, populate independent test expectations, then run kicad_tooling.verify. Import does not approve the design."


class KiCadForeignImportSummary(StrictModel):
    """Narrow projection of KiCad's retained, version-specific JSON import report."""

    source_format: NonEmptyText
    mapped_layers: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


class ImportInventoryCandidate(StrictModel):
    """One suggested island and its unchanged-source import preview."""

    source_project: NonEmptyText
    suggested_project_id: Identifier
    kind: ProjectKind | None
    preview: ProjectImportReport
    next_command: NonEmptyText


class ImportInventoryReport(StrictModel):
    """Read-only bulk intake plan; candidates still require individual review."""

    schema_version: Literal["1"] = "1"
    lane: Literal["IMPORT_INVENTORY"] = "IMPORT_INVENTORY"
    source_directory: NonEmptyText
    status: Literal["PASS", "NEEDS_WORK"]
    copied: Literal[False] = False
    candidates: tuple[ImportInventoryCandidate, ...] = ()
    skipped_local_state: tuple[NonEmptyText, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    next_step: NonEmptyText = (
        "Review each candidate and its exclusions; run one import-project command per accepted design. "
        "An import preview is not electrical validation."
    )


class ProductIndexEntry(StrictModel):
    id: Identifier
    path: RepositoryPath
    project_ids: tuple[Identifier, ...]


class ProductIndex(StrictModel):
    schema_version: Literal["1"]
    products: tuple[ProductIndexEntry, ...]

    @model_validator(mode="after")
    def unique_product_ids(self) -> ProductIndex:
        ids = [product.id.casefold() for product in self.products]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate product IDs in catalog/products.json")
        return self


class AssemblyKind(str, Enum):
    PURCHASED = "purchased"
    BUILT = "built"
    PHANTOM = "phantom"


class AssemblyMember(StrictModel):
    ref: Identifier
    item: Reference
    quantity: PositiveCount


class Assembly(StrictModel):
    id: Identifier
    revision: Identifier
    kind: AssemblyKind
    members: tuple[AssemblyMember, ...]
    purchase_part: Reference | None = None
    project_id: Identifier | None = None


class TerminalKind(str, Enum):
    ELECTRICAL = "electrical"
    MECHANICAL = "mechanical"
    LOGICAL = "logical"


class Terminal(StrictModel):
    id: Identifier
    instance: Reference
    pin: Identifier
    kind: TerminalKind
    exclusive: bool
    interface_id: Identifier | None = None
    interface_pin: NonEmptyText | None = None


class ConnectionKind(str, Enum):
    ELECTRICAL = "electrical"
    FUNCTIONAL = "functional"
    MECHANICAL = "mechanical"
    PROTOCOL = "protocol"


class Connection(StrictModel):
    id: Identifier
    kind: ConnectionKind
    from_terminal: Annotated[Identifier, Field(alias="from")]
    to_terminal: Annotated[Identifier, Field(alias="to")]
    variants: tuple[Identifier, ...]
    assurance: Assurance
    evidence: tuple[Identifier, ...]
    harness: Identifier | None = None


class Variant(StrictModel):
    id: Identifier
    revision: Identifier
    exclude: tuple[Reference, ...]
    board_variants: Mapping[Identifier, NonEmptyText] = Field(default_factory=dict)


class EvidenceKind(str, Enum):
    DESIGN_NOTE = "design_note"
    OBSERVATION = "observation"
    DATASHEET = "datasheet"
    TEST_REPORT = "test_report"


class Evidence(StrictModel):
    id: Identifier
    kind: EvidenceKind
    path: RepositoryPath
    sha256: Digest
    claims: tuple[Identifier, ...]


class Harness(StrictModel):
    id: Identifier
    revision: Identifier
    instance: Reference
    length_mm: PositiveMeasure
    conductor_area_mm2: PositiveMeasure
    assurance: Assurance
    evidence: tuple[Identifier, ...]


class MechanicalHandoff(StrictModel):
    id: Identifier
    instances: tuple[Reference, ...]
    units: Literal["mm"]
    datum: NonEmptyText
    drawing: RepositoryPath
    assurance: Assurance
    evidence: tuple[Identifier, ...]
    open_items: tuple[NonEmptyText, ...]


class ProductRecord(StrictModel):
    schema_version: Literal["1"]
    id: Identifier
    revision: Identifier
    maturity: Literal["training", "engineering_review", "prototype", "pilot", "production"]
    root_assembly: Identifier
    assemblies: tuple[Assembly, ...]
    terminals: tuple[Terminal, ...]
    connections: tuple[Connection, ...]
    variants: tuple[Variant, ...]
    evidence: tuple[Evidence, ...]
    harnesses: tuple[Harness, ...]
    mechanical: tuple[MechanicalHandoff, ...]
    blocking_issues: tuple[NonEmptyText, ...]


class PolicyIssue(StrictModel):
    code: NonEmptyText
    location: NonEmptyText
    message: NonEmptyText


class ProductPolicyReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["PRODUCT_POLICY"] = "PRODUCT_POLICY"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    products: tuple[Identifier, ...]
    open_items: Mapping[Identifier, tuple[NonEmptyText, ...]]
    issues: tuple[PolicyIssue, ...]


class Occurrence(StrictModel):
    item: Reference
    quantity: PositiveCount


class BomRow(StrictModel):
    part_id: Identifier
    revision: Identifier
    quantity: PositiveCount
    unit: Literal["each"]
    instances: NonEmptyText
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    disposition: Literal["NOT FOR MANUFACTURE"]


class HarnessScheduleRow(StrictModel):
    """One non-procurement harness schedule row for a selected product variant."""

    harness_id: Identifier
    revision: Identifier
    instance: Reference
    length_mm: PositiveMeasure
    conductor_area_mm2: PositiveMeasure
    electrical_connection_ids: tuple[Identifier, ...]
    endpoint_terminal_ids: tuple[Identifier, ...]
    assurance: Assurance
    evidence: tuple[Identifier, ...]
    disposition: Literal["NOT FOR MANUFACTURE"]


class HarnessSchedule(StrictModel):
    schema_version: Literal["1"] = "1"
    product: Identifier
    revision: Identifier
    variant: Identifier
    variant_revision: Identifier
    build_authorized: Literal[False] = False
    rows: tuple[HarnessScheduleRow, ...]


class ElectricalConnectionView(StrictModel):
    id: Identifier
    from_terminal: Annotated[Terminal, Field(alias="from")]
    to_terminal: Annotated[Terminal, Field(alias="to")]
    harness: Identifier | None = None
    assurance: Assurance
    evidence: tuple[Identifier, ...]


class ElectricalView(StrictModel):
    schema_version: Literal["1"] = "1"
    product: Identifier
    revision: Identifier
    variant: Identifier
    variant_revision: Identifier
    build_authorized: Literal[False] = False
    connections: tuple[ElectricalConnectionView, ...]


class SystemConnectionView(StrictModel):
    id: Identifier
    kind: ConnectionKind
    from_terminal: Annotated[Terminal, Field(alias="from")]
    to_terminal: Annotated[Terminal, Field(alias="to")]
    harness: Identifier | None = None
    assurance: Assurance
    evidence: tuple[Identifier, ...]


class SystemView(StrictModel):
    schema_version: Literal["1"] = "1"
    product: Identifier
    revision: Identifier
    variant: Identifier
    variant_revision: Identifier
    build_authorized: Literal[False] = False
    connections: tuple[SystemConnectionView, ...]


class SnapshotManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    kind: Literal["engineering_review_snapshot"] = "engineering_review_snapshot"
    build_authorized: Literal[False] = False
    commit: NonEmptyText
    working_tree_clean: bool
    git_status: str
    python_version: NonEmptyText
    policy_version: NonEmptyText
    products: tuple[Identifier, ...]
    checks: Mapping[Identifier, NonEmptyText]
    sources_sha256: Mapping[RepositoryPath, Digest]
    artifacts_sha256: Mapping[RepositoryPath, Digest]


class NetlistIdentityReport(StrictModel):
    status: Literal["PASS", "NOT_APPLICABLE"]
    assemblies: tuple[Identifier, ...] = ()
    components: int = 0
    reason: NonEmptyText | None = None


class SnapshotVerification(StrictModel):
    status: Literal["PASS"]
    artifacts: PositiveCount
    build_authorized: Literal[False] = False
    scope: Literal["artifact_integrity_only_not_authenticity_or_source_reconstruction"]


class ReleaseClass(str, Enum):
    ENGINEERING_REVIEW = "engineering_review"
    PROTOTYPE = "prototype"
    PILOT = "pilot"
    PRODUCTION = "production"


class ReleaseAssurancePolicy(StrictModel):
    release_class: ReleaseClass
    minimum_assurance: Assurance


class ReleasePoliciesCatalog(StrictModel):
    schema_version: Literal["1"] = "1"
    policies: tuple[ReleaseAssurancePolicy, ...]


class ReleaseStatus(str, Enum):
    CANDIDATE = "candidate"
    APPROVED = "approved"


class DeviationStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    CLOSED = "closed"


class ReleaseVariant(StrictModel):
    product: Identifier
    product_revision: Identifier
    variant: Identifier
    variant_revision: Identifier


class ReleaseLibrary(StrictModel):
    id: Identifier
    version: NonEmptyText
    provenance_sha256: Digest
    licensing_sha256: Digest


class ReleaseInterface(StrictModel):
    id: Identifier
    revision: NonEmptyText


class ReleaseArtifactKind(str, Enum):
    REVIEW_RECORD = "review_record"
    BOM = "bom"
    SCHEMATIC_EXPORT = "schematic_export"
    PCB_EXPORT = "pcb_export"
    HARNESS_EXPORT = "harness_export"
    VALIDATION_REPORT = "validation_report"
    FABRICATION_PACKAGE = "fabrication_package"
    ASSEMBLY_PACKAGE = "assembly_package"


class ReleaseArtifact(StrictModel):
    id: Identifier
    kind: ReleaseArtifactKind
    path: RepositoryPath
    sha256: Digest
    intended_use: NonEmptyText


class ReleaseDeviation(StrictModel):
    id: Identifier
    scope: tuple[Identifier, ...]
    owner: NonEmptyText
    reason: NonEmptyText
    status: DeviationStatus
    expires: date
    evidence: tuple[Identifier, ...]


class ReleaseApproval(StrictModel):
    electrical_reviewer: NonEmptyText
    mechanical_reviewer: NonEmptyText | None = None
    integrator: NonEmptyText
    release_authority: NonEmptyText | None = None
    approved_at: date
    evidence: tuple[Identifier, ...]


class SourceState(StrictModel):
    """Observed Git identity and source bytes, never a caller-supplied assertion."""

    commit: GitCommit | None = None
    clean: bool = False
    files_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)


class EvidenceFile(StrictModel):
    path: RepositoryPath
    sha256: Digest


class ReleaseEvidence(StrictModel):
    portable: EvidenceFile
    native: Mapping[Identifier, EvidenceFile]
    exports: Mapping[Identifier, EvidenceFile] = Field(default_factory=dict)
    electrical: Mapping[Identifier, EvidenceFile] = Field(default_factory=dict)


class ReleaseManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    release_id: Identifier
    release_class: ReleaseClass
    status: ReleaseStatus
    source_commit: GitCommit
    source_tag: NonEmptyText | None = None
    toolchain_id: Identifier
    projects: tuple[Identifier, ...] = ()
    variants: tuple[ReleaseVariant, ...] = ()
    libraries: tuple[ReleaseLibrary, ...]
    interfaces: tuple[ReleaseInterface, ...]
    checks: Mapping[Identifier, Literal["PASS", "NOT_APPLICABLE"]] = Field(default_factory=dict)
    evidence: ReleaseEvidence | None = None
    artifacts: tuple[ReleaseArtifact, ...]
    deviations: tuple[ReleaseDeviation, ...] = ()
    approval: ReleaseApproval | None = None


class ReleaseReadinessReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["RELEASE_READINESS"] = "RELEASE_READINESS"
    build_authorized: Literal[False] = False
    release_id: Identifier
    release_class: ReleaseClass
    status: Literal["PASS", "FAIL"]
    issues: tuple[PolicyIssue, ...]


class RepositoryPolicyReport(StrictModel):
    lane: Literal["REPOSITORY_POLICY"] = "REPOSITORY_POLICY"
    status: Literal["PASS", "FAIL"]
    issues: tuple[NonEmptyText, ...]


class GenerationReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    issues: tuple[NonEmptyText, ...]


class GovernanceRecord(StrictModel):
    schema_version: Literal["1"] = "1"
    branch: NonEmptyText
    required_status_checks: tuple[NonEmptyText, ...]
    authors: tuple[NonEmptyText, ...]
    reviewers: tuple[NonEmptyText, ...]
    integrators: tuple[NonEmptyText, ...]
    release_authorities: tuple[NonEmptyText, ...]
    branch_protection_evidence: tuple[NonEmptyText, ...]
    branch_protection_verified_at: NonEmptyText


class TeamPolicy(StrictModel):
    """Reviewed team choices, kept separately from project-specific assignments."""

    schema_version: Literal["1"] = "1"
    minimum_actors: Annotated[int, Field(ge=1)] = 2
    independent_review: bool = True
    required_status_checks: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)] = (
        "Template acceptance",
    )
    rationale: NonEmptyText


class HostedGovernanceCheck(StrictModel):
    """One observed hosted control, with uncertainty preserved."""

    id: Identifier
    status: Literal["PASS", "NEEDS_SETUP", "UNKNOWN"]
    expected: NonEmptyText
    observed: NonEmptyText
    source: NonEmptyText | None = None
    next_action: NonEmptyText | None = None


class HostedGovernanceReport(StrictModel):
    """Read-only API observations, never team or hardware approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["HOSTED_GOVERNANCE_AUDIT"] = "HOSTED_GOVERNANCE_AUDIT"
    build_authorized: Literal[False] = False
    repository: NonEmptyText | None = None
    default_branch: NonEmptyText | None = None
    required_status_checks: tuple[NonEmptyText, ...] = ()
    hosted_controls_status: Literal["PASS", "NEEDS_SETUP", "UNKNOWN"]
    status: Literal["PASS", "NEEDS_SETUP", "UNKNOWN"]
    checks: tuple[HostedGovernanceCheck, ...]
    next_actions: tuple[NonEmptyText, ...] = ()


class GovernanceLintReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["STATIC_GOVERNANCE_LINT"] = "STATIC_GOVERNANCE_LINT"
    projects: tuple[Identifier, ...]
    issues: tuple[NonEmptyText, ...]
    status: Literal["PASS", "FAIL"]


class ToolchainAssessment(StrictModel):
    toolchain_id: Identifier
    expected_version: NonEmptyText
    observed_version: NonEmptyText | None
    desktop_editing_allowed: bool
    status: Literal["PASS", "FAIL"]
    next_action: NonEmptyText


class MatrixEntry(StrictModel):
    project: Identifier
    image: NonEmptyText
    kicad_version: NonEmptyText
    fault_probes: bool = False
    electrical: bool = False


class CiMatrix(StrictModel):
    include: tuple[MatrixEntry, ...]


class ImpactPlan(StrictModel):
    """Fail-closed scope for a changed-path development check."""

    schema_version: Literal["1"] = "1"
    scope: Literal["docs", "focused", "full"]
    projects: tuple[Identifier, ...]
    changed_paths: tuple[str, ...]
    reasons: tuple[NonEmptyText, ...]
    docs_changed: bool = False


class CommandEvidence(StrictModel):
    argv: tuple[NonEmptyText, ...]
    started_utc: NonEmptyText
    returncode: int
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class ReleaseExportReport(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    source: SourceState
    toolchain_id: Identifier
    settings: ReleaseExportSettings
    assembly_variant: NonEmptyText | None = None
    commands: Mapping[Identifier, CommandEvidence]
    artifacts_sha256: Mapping[RepositoryPath, Digest]
    status: Literal["PASS", "FAIL"]
    issues: tuple[NonEmptyText, ...] = ()


class ReleasePackageIndex(StrictModel):
    schema_version: Literal["1"] = "1"
    source_commit: GitCommit
    manifest: RepositoryPath
    files_sha256: Mapping[RepositoryPath, Digest]


class ReleasePackageReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    source_commit: GitCommit
    package: str
    package_sha256: Digest
    manifest: RepositoryPath
    build_authorized: Literal[False] = False


class DocumentationException(StrictModel):
    """A reviewed, path-scoped and time-bounded documentation-policy waiver."""

    id: Identifier
    code: Identifier
    path: RepositoryPath
    reason: NonEmptyText
    expires: date


class DocumentationPolicy(StrictModel):
    """Repository-owned Markdown graph roots and narrow policy exceptions."""

    schema_version: Literal["1"] = "1"
    roots: tuple[RepositoryPath, ...]
    documentation_namespaces: tuple[RepositoryPath, ...] = ()
    exceptions: tuple[DocumentationException, ...] = ()


class DocumentationIssue(StrictModel):
    code: Identifier
    path: RepositoryPath
    line: PositiveCount
    message: NonEmptyText


class DocumentationPolicyReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["MARKDOWN_REPOSITORY_POLICY"] = "MARKDOWN_REPOSITORY_POLICY"
    roots: tuple[RepositoryPath, ...]
    documents: NonNegativeCount
    issues: tuple[DocumentationIssue, ...]
    status: Literal["PASS", "FAIL"]


class TemplateContract(StrictModel):
    """Versioned, portable inventory for a repository template implementation."""

    schema_version: Literal["1"] = "1"
    template_version: TemplateVersion
    required_paths: tuple[RepositoryPath, ...]
    adoption_guide: RepositoryPath
    upgrades_catalog: RepositoryPath


class TemplateUpgrade(StrictModel):
    id: Identifier
    from_version: TemplateVersion
    to_version: TemplateVersion
    breaking: bool
    steps: tuple[NonEmptyText, ...]


class TemplateUpgradesCatalog(StrictModel):
    schema_version: Literal["1"] = "1"
    upgrades: tuple[TemplateUpgrade, ...]


class TemplateAdoptionRecord(StrictModel):
    schema_version: Literal["1"] = "1"
    template_version: TemplateVersion
    project_id: Identifier
    status: Literal["needs_adoption", "initialized"] = "needs_adoption"


class TemplateInitReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    project_id: str
    changed: tuple[RepositoryPath, ...] = ()
    removed: tuple[RepositoryPath, ...] = ()
    issues: tuple[PolicyIssue, ...] = ()


class TemplateAdoptReport(StrictModel):
    """One-command fork initialization and portable acceptance result."""

    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_ADOPTION"] = "TEMPLATE_ADOPTION"
    build_authorized: Literal[False] = False
    project_id: Identifier
    preflight: Literal["PASS", "FAIL"]
    initialization: Literal["PASS", "FAIL", "NOT_RUN"]
    portable: Literal["PASS", "FAIL", "NOT_RUN"]
    status: Literal["PASS", "FAIL"]
    changed: tuple[RepositoryPath, ...] = ()
    removed: tuple[RepositoryPath, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()


class EnvironmentCheck(StrictModel):
    id: Identifier
    required: bool
    status: Literal["PASS", "FAIL", "OPTIONAL"]
    expected: NonEmptyText
    observed: NonEmptyText | None = None
    next_action: NonEmptyText


class TemplateDoctorReport(StrictModel):
    """Local prerequisites and native-runner readiness without changing the repository."""

    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_DOCTOR"] = "TEMPLATE_DOCTOR"
    build_authorized: Literal[False] = False
    native_requested: bool
    electrical_requested: bool = False
    checks: tuple[EnvironmentCheck, ...]
    status: Literal["PASS", "FAIL"]
    next_actions: tuple[NonEmptyText, ...] = ()


class InventoryProject(StrictModel):
    """Declared island and whether its authored inputs are present for a check."""

    id: Identifier
    kind: ProjectKind
    status: Literal["training_fixture", "engineering", "release_candidate"]
    assurance_profile: Literal["training", "development", "production"]
    manifest: RepositoryPath
    project: RepositoryPath
    toolchain_id: Identifier
    tags: tuple[Identifier, ...]
    products: tuple[Identifier, ...]
    readiness: Literal["INPUTS_PRESENT", "NEEDS_INPUTS"]
    missing_inputs: tuple[RepositoryPath, ...] = ()
    next_command: NonEmptyText


class McpProjectReport(StrictModel):
    """One project's declared inputs; inspection never authorizes manufacturing."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    project: InventoryProject
    manifest: ProjectManifest
    contract: ProjectTestContract | None


class InventoryGroup(StrictModel):
    """One product or tag and its selected project IDs."""

    id: Identifier
    project_ids: tuple[Identifier, ...]


class InventoryToolchain(StrictModel):
    id: Identifier
    kicad_version: NonEmptyText


class TemplateInventoryReport(StrictModel):
    """Read-only discovery; input presence is not validation or release approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_INVENTORY"] = "TEMPLATE_INVENTORY"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    projects: tuple[InventoryProject, ...] = ()
    products: tuple[InventoryGroup, ...] = ()
    tags: tuple[InventoryGroup, ...] = ()
    toolchains: tuple[InventoryToolchain, ...] = ()
    issues: tuple[PolicyIssue, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()


class DiagnosticFinding(StrictModel):
    """One observed failure or review task with a concrete repair path."""

    severity: Literal["BLOCKING", "REVIEW"]
    code: NonEmptyText
    location: NonEmptyText
    observed: NonEmptyText
    action: NonEmptyText
    guide: RepositoryPath


class DiagnosticReport(StrictModel):
    """A local coaching view; success never constitutes engineering approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PROJECT_DIAGNOSTICS"] = "PROJECT_DIAGNOSTICS"
    build_authorized: Literal[False] = False
    project_id: NonEmptyText
    scope: Literal["import", "project"]
    status: Literal["PASS", "NEEDS_WORK"]
    findings: tuple[DiagnosticFinding, ...]
    next_command: NonEmptyText
    follow_up_command: NonEmptyText | None = None
    run_directory: str | None = None


class LocalRescueReport(StrictModel):
    """Partial, read-only island inspection that cannot satisfy repository gates."""

    schema_version: Literal["1"] = "1"
    lane: Literal["LOCAL_PROJECT_RESCUE"] = "LOCAL_PROJECT_RESCUE"
    status: Literal["UNVERIFIED_GLOBAL"] = "UNVERIFIED_GLOBAL"
    build_authorized: Literal[False] = False
    ci_eligible: Literal[False] = False
    release_eligible: Literal[False] = False
    project_id: NonEmptyText
    selected_manifest: RepositoryPath | None = None
    local_inspection: Literal["CLEAR", "NEEDS_REPAIR"]
    findings: tuple[DiagnosticFinding, ...] = ()
    omitted_checks: tuple[NonEmptyText, ...]
    next_command: NonEmptyText
    run_directory: NonEmptyText


class TemplatePreflightReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_PREFLIGHT"] = "TEMPLATE_PREFLIGHT"
    build_authorized: Literal[False] = False
    template_version: TemplateVersion | None = None
    status: Literal["PASS", "FAIL"]
    issues: tuple[PolicyIssue, ...]


class TemplateBootstrapReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_BOOTSTRAP"] = "TEMPLATE_BOOTSTRAP"
    build_authorized: Literal[False] = False
    template_version: TemplateVersion | None = None
    destination: NonEmptyText
    status: Literal["PASS", "FAIL"]
    issues: tuple[PolicyIssue, ...]
    removed: tuple[RepositoryPath, ...] = ()


class TemplateUpgradePlan(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_UPGRADE_PLAN"] = "TEMPLATE_UPGRADE_PLAN"
    build_authorized: Literal[False] = False
    current_version: TemplateVersion | None = None
    target_version: NonEmptyText
    status: Literal["PASS", "FAIL"]
    upgrades: tuple[TemplateUpgrade, ...]
    issues: tuple[PolicyIssue, ...]


class SupplierOffer(StrictModel):
    id: Identifier
    part_id: Identifier
    supplier: NonEmptyText
    supplier_sku: NonEmptyText
    source_url: NonEmptyText
    region: NonEmptyText
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    quantity_break: PositiveCount
    unit_price_minor: NonNegativeCount
    availability: NonEmptyText
    lead_time_days: NonNegativeCount | None = None


class SourcingSnapshot(StrictModel):
    schema_version: Literal["1"] = "1"
    snapshot_id: Identifier
    source_commit: GitCommit
    observed_at: AwareDatetime
    offers: tuple[SupplierOffer, ...]


class SourcingSnapshotReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["SOURCING_SNAPSHOT"] = "SOURCING_SNAPSHOT"
    build_authorized: Literal[False] = False
    snapshot_id: Identifier
    offers: NonNegativeCount
    status: Literal["PASS", "FAIL"]
    issues: tuple[PolicyIssue, ...]


class CheckMetric(StrictModel):
    name: Identifier
    status: Literal["PASS", "FAIL"]
    findings: NonNegativeCount


class DeviationMetrics(StrictModel):
    total: NonNegativeCount
    approved: NonNegativeCount
    open: NonNegativeCount
    closed: NonNegativeCount
    expired: NonNegativeCount


class TemplateMetricsReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_METRICS"] = "TEMPLATE_METRICS"
    build_authorized: Literal[False] = False
    checks: tuple[CheckMetric, ...]
    stale_evidence: NonNegativeCount
    deviations: DeviationMetrics


class CheckEvidence(StrictModel):
    status: Literal["PASS", "FAIL", "NOT_RUN"]
    returncode: int | None = None
    error: NonEmptyText | None = None
    findings: int | None = None
    expected_ignored_checks: tuple[Identifier, ...] = ()
    files: tuple[RepositoryPath, ...] = ()
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    identity_status: Literal["PASS", "NOT_APPLICABLE"] | None = None
    observed_version: NonEmptyText | None = None
    image: NonEmptyText | None = None


class NetlistContract(StrictModel):
    components: Mapping[Identifier, ComponentContract]
    nets: Mapping[NetName, tuple[Reference, ...]]
    unconnected_nets: Mapping[NetName, tuple[Reference, ...]] = Field(default_factory=dict)
    dnp_components: tuple[Identifier, ...] = ()
    component_symbols: Mapping[Identifier, NonEmptyText] = Field(default_factory=dict)
    pin_functions: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)
    pin_electrical_types: Mapping[Reference, NonEmptyText] = Field(default_factory=dict)
    component_pin_numbers: Mapping[Identifier, tuple[NonEmptyText, ...]] = Field(
        default_factory=dict
    )

    @model_validator(mode="before")
    @classmethod
    def separate_native_unconnected_nets(
        cls, value: NetlistRawValue, info: ValidationInfo
    ) -> object:
        return normalize_native_unconnected_nets(value, info)


ReturnNetGroup = _return_net_models.ReturnNetGroup
NumberedPowerRailGroup = _power_rail_models.NumberedPowerRailGroup


class ValidationSummary(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["KICAD_CLI"] = "KICAD_CLI"
    timestamp_utc: NonEmptyText
    checked_commit: NonEmptyText
    source: SourceState | None = None
    project_id: Identifier | None = None
    pr_head_commit: str | None = None
    assurance_profile: Literal["training", "development", "production"] | None = None
    not_for_manufacture: bool | None = None
    project_kind: ProjectKind | None = None
    checks: Mapping[Identifier, CheckEvidence]
    status: Literal["PASS", "FAIL"]
    artifacts_sha256: Mapping[RepositoryPath, Digest]


class ProjectCheckSummary(StrictModel):
    id: Identifier
    status: Literal["PASS", "FAIL"]
    summary: RepositoryPath


class CheckAllSummary(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["KICAD_CLI_ALL_PROJECTS"] = "KICAD_CLI_ALL_PROJECTS"
    governance: GovernanceLintReport
    repository: RepositoryPolicyReport
    product_policy: ProductPolicyReport
    projects: tuple[ProjectCheckSummary, ...]
    status: Literal["PASS", "FAIL"]


class FaultProbeCase(StrictModel):
    id: Identifier
    status: Literal["PASS", "FAIL"]
    expected_failing_check: Identifier
    observed_status: Literal["PASS", "FAIL", "NOT_RUN"] | None = None
    observed_returncode: int | None = None


class FaultProbeReport(StrictModel):
    lane: Literal["KICAD_CLI"] = "KICAD_CLI"
    not_for_manufacture: Literal[True] = True
    cases: tuple[FaultProbeCase, ...]
    status: Literal["PASS", "FAIL"]


class UnitTestReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    returncode: int


class SkippedCheck(StrictModel):
    status: Literal["NOT_RUN"] = "NOT_RUN"
    reason: NonEmptyText


class FailedCheck(StrictModel):
    status: Literal["FAIL"] = "FAIL"
    error: NonEmptyText


class ProjectTestsReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    commands: Mapping[Identifier, CommandEvidence]


class StaticPipelineReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    source: SourceState | None = None
    scope: Literal["static_only", "repository_static"] = "static_only"
    tooling_version: NonEmptyText | None = None
    build_authorized: Literal[False] = False
    registry: GovernanceLintReport
    repository: RepositoryPolicyReport
    documentation: DocumentationPolicyReport
    rumdl: CommandEvidence
    mdrepo: CommandEvidence
    product: ProductPolicyReport
    generation: GenerationReport
    ruff: CommandEvidence | None = None
    pyright: CommandEvidence | None = None
    unit_tests: CommandEvidence | None = None
    project_tests: ProjectTestsReport

    @model_validator(mode="after")
    def explicit_tooling_boundary(self) -> StaticPipelineReport:
        if self.scope == "static_only" and any(
            command is None for command in (self.ruff, self.pyright, self.unit_tests)
        ):
            raise ValueError("Legacy full reports require all tooling quality commands")
        if self.scope == "repository_static" and self.tooling_version is None:
            raise ValueError(
                "Project repository reports must identify the installed tooling version"
            )
        return self


class ProjectStaticPipelineReport(StrictModel):
    """Fast local policy result for explicitly selected design projects."""

    status: Literal["PASS", "FAIL"]
    scope: Literal["project_static"] = "project_static"
    build_authorized: Literal[False] = False
    projects: tuple[Identifier, ...]
    registry: GovernanceLintReport
    repository: RepositoryPolicyReport
    product: ProductPolicyReport
    generation: GenerationReport
    project_tests: ProjectTestsReport


class ProjectVerificationReport(StrictModel):
    """One local project attempt with retained portable and optional native evidence."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PROJECT_VERIFY"] = "PROJECT_VERIFY"
    build_authorized: Literal[False] = False
    project_id: Identifier
    depth: Literal["portable", "native", "electrical"]
    runner: Literal["none", "local", "container"] = "none"
    run_directory: NonEmptyText
    portable: ProjectStaticPipelineReport | None = None
    doctor: TemplateDoctorReport | None = None
    dependency_command: CommandEvidence | None = None
    native_command: CommandEvidence | None = None
    native: CheckAllSummary | None = None
    design_lint: DesignLintReport | None = None
    electrical: ElectricalAnalysisReport | None = None
    diagnosis: DiagnosticReport | None = None
    status: Literal["PASS", "FAIL", "ERROR"]
    next_actions: tuple[NonEmptyText, ...] = ()
    error: str | None = None


class ScopedReleasePortableReport(StrictModel):
    """Committed-source binding for the selected portable release lane.

    This is deliberately a different type from StaticPipelineReport: a
    selected lane can never masquerade as the repository-wide portable gate.
    """

    schema_version: Literal["1"] = "1"
    scope: Literal["release_projects"] = "release_projects"
    source: SourceState
    projects: tuple[Identifier, ...]
    checks: ProjectStaticPipelineReport


class ContractDifference(StrictModel):
    kind: Literal["component", "net"]
    identifier: NonEmptyText
    difference: Literal["observed_only", "authored_only", "different"]


class ContractCoachReport(StrictModel):
    """Observed netlist inventory for human contract review, never an approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["CONTRACT_COACH"] = "CONTRACT_COACH"
    status: Literal["READY_FOR_REVIEW", "BLOCKED"]
    project_id: Identifier
    project_kind: ProjectKind | None = None
    review_state: Literal["UNREVIEWED"] = "UNREVIEWED"
    electrical_coverage: Literal[False] = False
    build_authorized: Literal[False] = False
    selected_runner: Literal["local", "container"] | None = None
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    netlist_sha256: Digest | None = None
    native_summary: str | None = None
    native_status: Literal["PASS", "FAIL"] | None = None
    observed: NetlistContract | None = None
    authored: NetlistContract | None = None
    differences: tuple[ContractDifference, ...] = ()
    return_net_groups: tuple[ReturnNetGroup, ...] = ()
    similar_connector_pin_groups: tuple[SimilarConnectorPinGroup, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()
    commands: Mapping[Identifier, CommandEvidence] = Field(default_factory=dict)
    receipt_dir: str | None = None


ConnectorMappedPinEvidence = _connector_coverage_models.ConnectorMappedPinEvidence
ConnectorCoverageEntry = _connector_coverage_models.ConnectorCoverageEntry
ConnectorCoverageReport = _connector_coverage_models.ConnectorCoverageReport


class McpArtifactEntry(StrictModel):
    path: RepositoryPath
    kind: Literal["file", "directory"]
    size_bytes: NonNegativeCount | None = None
    sha256: Digest | None = None


class McpArtifactList(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    directory: RepositoryPath
    entries: tuple[McpArtifactEntry, ...]
    offset: NonNegativeCount
    total_entries: NonNegativeCount
    truncated: bool
    next_offset: NonNegativeCount | None = None


class McpFileContent(StrictModel):
    """Bounded Unicode text or metadata; offsets count characters, never bytes."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    path: RepositoryPath
    sha256: Digest
    size_bytes: NonNegativeCount
    content_kind: Literal["text", "binary", "metadata_only"]
    text: str | None = None
    offset: NonNegativeCount
    total_characters: NonNegativeCount | None = None
    truncated: bool = False
    next_offset: NonNegativeCount | None = None
    note: str | None = None


class McpEditPreview(StrictModel):
    """A proposed exact replacement, without a claim of engineering validation."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    checks_required: Literal[True] = True
    project_id: Identifier
    path: RepositoryPath
    before_sha256: Digest
    after_sha256: Digest
    diff: str
    validation: Literal["JSON_MODEL", "TEXT_ONLY"]
    next_command: NonEmptyText


class McpEditResult(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    checks_required: Literal[True] = True
    status: Literal["APPLIED"] = "APPLIED"
    project_id: Identifier
    path: RepositoryPath
    before_sha256: Digest
    after_sha256: Digest
    readback_sha256: Digest
    next_command: NonEmptyText


class McpScopeReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    run_directory: NonEmptyText
    report: StaticPipelineReport | ProjectStaticPipelineReport


class McpGenerationReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["PASS"] = "PASS"
    directory: RepositoryPath
    files: tuple[RepositoryPath, ...]


Resolution = Literal[
    "source_present",
    "toolchain_dependent",
    "embedded_present",
    "broken",
]
InventoryStatus = Literal["READY", "REVIEW", "FAIL"]
ExportMode = Literal["inspect", "generate"]
ExportStatus = Literal["PASS", "FAIL", "ERROR"]
SelectedRunner = Literal["none", "local", "container"]
ThreeDView = Literal[
    "top",
    "bottom",
    "left",
    "right",
    "front",
    "back",
    "angled",
    "angled-90",
    "angled-180",
    "angled-270",
]
THREE_D_VIEWS: tuple[ThreeDView, ...] = (
    "top",
    "bottom",
    "left",
    "right",
    "front",
    "back",
    "angled",
    "angled-90",
    "angled-180",
    "angled-270",
)
DEFAULT_THREE_D_VIEWS: tuple[ThreeDView, ...] = THREE_D_VIEWS


class ModelAssignment(StrictModel):
    """A raw observed model reference and its static source-resolution finding."""

    # Keep raw paths, including empty/nonportable input, so failed references can
    # be reported faithfully. Only a resolved source_path is a repository path.
    path: str
    line: PositiveCount
    resolution: Resolution
    source_path: RepositoryPath | None = None
    hidden: bool = False
    reason: str | None = None


class FootprintModels(StrictModel):
    """Observed footprint metadata; malformed identifiers remain diagnosable."""

    reference: str
    footprint_id: str
    line: PositiveCount
    models: tuple[ModelAssignment, ...]
    candidate_assets: tuple[RepositoryPath, ...]
    status: InventoryStatus


class ModelInventoryReport(StrictModel):
    """Static model assignments, without native geometry or manufacturing approval."""

    schema_version: Literal["1"] = "1"
    scope: Literal["static_inventory"] = "static_inventory"
    build_authorized: Literal[False] = False
    project_id: Identifier
    board: RepositoryPath
    status: InventoryStatus
    footprints: tuple[FootprintModels, ...]
    findings: tuple[DiagnosticFinding, ...]
    next_actions: tuple[NonEmptyText, ...]


class ThreeDReport(StrictModel):
    """A versioned 3D receipt for one board and source snapshot, never an approval."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    project_id: Identifier
    mode: ExportMode
    assembly_variant: NonEmptyText | None = None
    status: ExportStatus
    run_directory: NonEmptyText
    toolchain_id: Identifier | None = None
    kicad_version: NonEmptyText | None = None
    runner: SelectedRunner = "none"
    board: RepositoryPath | None = None
    source_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    models: ModelInventoryReport | None = None
    commands: Mapping[Identifier, CommandEvidence] = Field(default_factory=dict)
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    next_actions: tuple[NonEmptyText, ...] = ()
    error: str | None = None


class ModelMapAssignment(StrictModel):
    """An exact placed-footprint reference mapped to reviewed model source."""

    reference: Annotated[str, Field(min_length=1)]
    model: str
    candidate_assets: tuple[RepositoryPath, ...] = ()
    model_sha256: Digest | None = None


class McpModelMapAssignment(StrictModel):
    """MCP JSON-array input, converted to an immutable assignment at the adapter."""

    reference: Annotated[str, Field(min_length=1)]
    model: str
    candidate_assets: list[RepositoryPath] = Field(default_factory=list)
    model_sha256: Digest | None = None


class ModelMap(StrictModel):
    """Explicit assignments bound to the board bytes that the author reviewed."""

    schema_version: Literal["1"] = "1"
    project_id: Identifier
    board_sha256: Digest
    manifest_sha256: Digest
    assignments: Annotated[tuple[ModelMapAssignment, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_references(self) -> ModelMap:
        references = [item.reference for item in self.assignments]
        if len(references) != len(set(references)):
            raise ValueError("Map has duplicate footprint references")
        return self


class ModelPopulationReport(StrictModel):
    """A model-assignment plan or source edit that still requires engineering checks."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    checks_required: Literal[True] = True
    status: Literal["DRAFT", "PLAN", "APPLIED", "FAIL", "ERROR"]
    project_id: Identifier
    run_directory: NonEmptyText
    board: RepositoryPath | None = None
    manifest: RepositoryPath | None = None
    board_sha256: Digest | None = None
    manifest_sha256: Digest | None = None
    draft_map: str | None = None
    locked_map: str | None = None
    model_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    board_diff: str = ""
    manifest_diff: str = ""
    review_notice: NonEmptyText = (
        "A mapped path does not verify package identity, dimensions, orientation, "
        "offset or enclosure fit; inspect the generated geometry in KiCad."
    )
    next_commands: tuple[NonEmptyText, ...] = ()
    error: str | None = None


class PurchasingSchemaModel(StrictModel):
    schema_version: Literal["1"] = "1"

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema_version(cls, value: object) -> str:
        if value != "1":
            raise ValueError("Unsupported purchasing schema version")
        return "1"


class PurchasingPreferences(PurchasingSchemaModel):
    """User-selected quantities and exact supplier IDs; no sourcing authority."""

    boards: PositiveCount = 1
    spare_percent: Annotated[int, Field(ge=0, le=100)] = 0
    spare_minimum: NonNegativeCount = 0
    digikey_skus: Mapping[Identifier, Annotated[str, StringConstraints(min_length=1)]] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def exact_supplier_identifiers(self) -> PurchasingPreferences:
        for identifier in self.digikey_skus.values():
            if identifier != identifier.strip() or any(
                ord(character) < 32 or ord(character) == 127 for character in identifier
            ):
                raise ValueError(
                    "DigiKey identifiers must be exact text without padding or control characters"
                )
        return self


class PurchasingComponent(StrictModel):
    reference: Identifier
    value: str
    footprint: str
    part_id: str | None = None
    dnp: bool = False
    exclude_from_bom: bool = False


class PurchasingLine(StrictModel):
    part_id: Identifier
    revision: Identifier
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    footprint: NonEmptyText
    references: tuple[Identifier, ...]
    per_board: PositiveCount
    required: PositiveCount
    spares: NonNegativeCount
    quantity: PositiveCount
    order_number: NonEmptyText
    order_number_kind: Literal["MPN", "DigiKey"]
    search_url: NonEmptyText


class PurchasingFinding(StrictModel):
    code: Identifier
    references: tuple[Identifier, ...] = ()
    message: NonEmptyText
    action: NonEmptyText


class PurchasingPlan(PurchasingSchemaModel):
    """Metadata readiness for human ordering review, never electrical approval."""

    schema_version: Literal["1"] = "1"
    status: Literal["NEEDS_PARTS", "READY_FOR_ORDER_REVIEW"]
    preferences: PurchasingPreferences
    components: tuple[PurchasingComponent, ...]
    lines: tuple[PurchasingLine, ...]
    findings: tuple[PurchasingFinding, ...]
    excluded_references: tuple[Identifier, ...] = ()
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


class DigiKeyHandoffQuantity(StrictModel):
    quantity: PositiveCount


class DigiKeyHandoffPart(StrictModel):
    requested_part_number: Annotated[NonEmptyText, Field(alias="requestedPartNumber")]
    quantities: Annotated[tuple[DigiKeyHandoffQuantity, ...], Field(min_length=1)]
    customer_reference: Annotated[str, Field(alias="customerReference")]
    notes: str


class DigiKeyHandoffPayload(RootModel[tuple[DigiKeyHandoffPart, ...]]):
    """DigiKey's third-party API accepts a root array of order lines."""

    model_config = ConfigDict(strict=True, frozen=True)


class DigiKeyHandoffUrl(RootModel[str]):
    """DigiKey returns a JSON string, validated as an allowed URL by the adapter."""

    model_config = ConfigDict(strict=True, frozen=True)


class DigiKeyHandoffReply(StrictModel):
    single_use_url: Annotated[
        str,
        StringConstraints(pattern=r"^https://www\.digikey\.com/short/[a-z0-9]{7,8}$"),
    ]


class DigiKeyHandoffResult(StrictModel):
    status: Literal["READY", "BLOCKED", "ERROR"]
    single_use_url: str | None = None
    issues: tuple[NonEmptyText, ...] = ()
    purchase_authorized: Literal[False] = False


class PurchasingReport(PurchasingSchemaModel):
    """Source-bound local parts assistant receipt."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PARTS_TO_ORDER"] = "PARTS_TO_ORDER"
    project_id: Identifier
    status: Literal["BLOCKED", "NEEDS_PARTS", "READY_FOR_ORDER_REVIEW"]
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False
    plan: PurchasingPlan | None = None
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    input_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    netlist_sha256: Digest | None = None
    native_status: Literal["PASS", "FAIL"] | None = None
    selected_runner: Literal["local", "container"] | None = None
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()
    receipt_dir: str
    artifacts: tuple[str, ...] = ()
    evidence: ContractCoachReport | None = None


class McpPurchasingPreferencesResult(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    purchase_authorized: Literal[False] = False
    status: Literal["CREATED", "UPDATED"]
    project_id: Identifier
    path: RepositoryPath
    before_sha256: Digest | None = None
    after_sha256: Digest
    readback_sha256: Digest
    preferences: PurchasingPreferences


SurfaceAlignment = Literal["aligned", "partial", "cli_only", "mcp_only"]


class ToolCliSnapshot(StrictModel):
    module: NonEmptyText
    commands: tuple[NonEmptyText, ...] = ()
    options: tuple[NonEmptyText, ...] = ()


class ToolMcpSnapshot(StrictModel):
    name: Identifier
    parameters: tuple[Identifier, ...] = ()


class ToolSurfaceMapping(StrictModel):
    id: Identifier
    cli: tuple[NonEmptyText, ...] = ()
    mcp: tuple[Identifier, ...] = ()
    alignment: SurfaceAlignment
    reason: NonEmptyText
    scope: Literal["core", "administration", "adapter"]
    gaps: tuple[NonEmptyText, ...] = ()
    constraints: tuple[NonEmptyText, ...] = ()
    exception: NonEmptyText | None = None
    parity_tests: tuple[NonEmptyText, ...] = ()


class ToolSurfacesCatalog(StrictModel):
    schema_version: Literal["2"] = "2"
    cli: tuple[ToolCliSnapshot, ...]
    mcp: tuple[ToolMcpSnapshot, ...]
    capabilities: tuple[ToolSurfaceMapping, ...]


class ToolSurfaceReport(StrictModel):
    schema_version: Literal["2"] = "2"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    coverage_status: Literal["PASS", "FAIL"]
    parity_status: Literal["PASS", "FAIL"]
    behavior_verification: Literal["NOT_RUN"] = "NOT_RUN"
    mcp_verification: Literal["LIVE", "STATIC_ONLY", "UNAVAILABLE"]
    cli: tuple[ToolCliSnapshot, ...]
    mcp: tuple[ToolMcpSnapshot, ...]
    capabilities: tuple[ToolSurfaceMapping, ...]
    issues: tuple[PolicyIssue, ...] = ()
    notes: tuple[NonEmptyText, ...] = ()


class McpNativeScopeReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    run_directory: NonEmptyText
    report: CheckAllSummary


class ElectricalCheck(StrictModel):
    id: NonEmptyText
    status: Literal["PASS", "FAIL", "NOT_RUN", "NOT_APPLICABLE", "NOT_CONFIGURED"]
    detail: NonEmptyText
    observed: FiniteMeasure | None = None
    unit: str | None = None


class ElectricalAnalysisReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["ELECTRICAL_ANALYSIS"] = "ELECTRICAL_ANALYSIS"
    build_authorized: Literal[False] = False
    project_id: Identifier
    source: SourceState | None = None
    status: Literal["PASS", "FAIL", "NOT_CONFIGURED"]
    run_directory: str = ""
    input_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    commands: Mapping[str, CommandEvidence] = Field(default_factory=dict)
    checks: tuple[ElectricalCheck, ...]
    limits: tuple[str, ...] = (
        "Grounding covers declared schematic pins; copper return paths and physical bonds need review.",
        "PCB return paths report native pad/zone connectivity and declared net ties; they do not prove manufactured continuity or first-article acceptance.",
        "Pin relationships compare schematic nets; net ties and physical continuity need separate review.",
        (
            "I2C pull-up ranges compare direct resistors, exact mapped series chains, and mapped array channels; "
            "optional authored rail-to-input voltage checks compare declared limits and exact pin identity, "
            "but do not verify source values, transients, array internals, or off-board networks."
        ),
        (
            "Optional I2C resistor-window checks use project-authored rail, low-level, sink-current, "
            "bus-capacitance and rise-time inputs with an ideal 30%-to-70% RC model; they do not include "
            "component tolerances, nonlinear or active pull-ups, off-board loading, or measured waveforms."
        ),
        (
            "CAN checks compare declared bus pins, local direct/split paths, DNP options, and any mapped "
            "split midpoint capacitor's nominal value and pins; external hardware, physical bus-end placement, "
            "and capacitor placement, derating, impedance, and EMC need separate evidence."
        ),
        (
            "USB-C checks compare declared CC/VBUS/GND pin assignments, fitted Rp/Rd resistors, exact "
            "controller/protection identity, any authored VBUS component/net map, and an explicitly mapped "
            "nominal port-side VBUS capacitance range; it does not verify capacitor derating, tolerance, "
            "dynamic behavior, device conduction, or PCB/contact continuity, while controller behavior, "
            "PD and protection performance need separate evidence."
        ),
        (
            "Direct serial voltage checks compare authored guaranteed output ranges with receiver thresholds "
            "and absolute limits; cited sources, operating conditions, transients, and device behavior are "
            "not independently validated."
        ),
        (
            "Component voltage-rating checks compare exact mapped part identity and pin/net assignments, "
            "a project-authored maximum stress envelope, a datasheet working rating, and a project-selected "
            "utilization limit; the sources and stress derivation are not independently validated."
        ),
        "Simulation results apply only to the reviewed models, cases, timestep and frequency grid.",
        "Power budgets use simultaneous worst-case loads and engineer-supplied derated path ratings.",
        "Physical startup, thermal behavior, RF/EMC and manufacturing acceptance remain unverified.",
        (
            "Test-access contracts check exact schematic pins and separately check PCB footprint/pad, "
            "net and outer-mask declarations; probe clearance, nearby obstructions, covers and "
            "manufacturing test coverage remain unverified."
        ),
    )


class ElectricalSuiteReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    projects: tuple[ElectricalAnalysisReport, ...]


class ElectricalSetupReport(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    status: Literal["CREATED"] = "CREATED"
    project_id: Identifier
    contract: RepositoryPath
    changed: tuple[RepositoryPath, ...]
    next_actions: tuple[NonEmptyText, ...]


class ElectricalInputInventory(StrictModel):
    schema_version: Literal["1"] = "1"
    status: Literal["UNREVIEWED"] = "UNREVIEWED"
    build_authorized: Literal[False] = False
    project_id: Identifier
    run_directory: NonEmptyText
    source_sha256: Mapping[RepositoryPath, Digest]
    model_sha256: Mapping[RepositoryPath, Digest]
    next_actions: tuple[NonEmptyText, ...]


class PartCadComponent(StrictModel):
    reference: Identifier
    symbol_id: str
    value: str
    footprint: str
    part_id: str | None = None
    source_path: RepositoryPath
    uuid: NonEmptyText
    dnp: bool = False
    exclude_from_bom: bool = False


class PartSourceEdit(StrictModel):
    path: RepositoryPath
    before: str | None
    after: str


class PartCadChanges(StrictModel):
    edits: tuple[PartSourceEdit, ...] = ()
    pending_references: tuple[Identifier, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()


class PartSelectionAssignment(StrictModel):
    reference: Identifier
    part_id: Identifier


class PartSelectionMap(PurchasingSchemaModel):
    project_id: Identifier
    preconditions: Mapping[RepositoryPath, Digest | None]
    assignments: tuple[PartSelectionAssignment, ...] = ()
    locked: bool = False
    after_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_assignments(self) -> PartSelectionMap:
        references = [item.reference for item in self.assignments]
        if len(references) != len(set(references)):
            raise ValueError("Part selection repeats a component reference")
        return self


class PartPickerItem(StrictModel):
    component: PartCadComponent
    choice_ids: tuple[Identifier, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()


class PartPickerReport(PurchasingSchemaModel):
    lane: Literal["PART_PICKER"] = "PART_PICKER"
    status: Literal["READY", "NEEDS_CATALOG", "BLOCKED"]
    project_id: Identifier
    items: tuple[PartPickerItem, ...] = ()
    choices: tuple[PartRecord, ...] = ()
    selection_template: PartSelectionMap | None = None
    issues: tuple[NonEmptyText, ...] = ()
    receipt_dir: str
    evidence: ContractCoachReport | None = None
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


class PartSelectionReport(PurchasingSchemaModel):
    lane: Literal["PART_SELECTION"] = "PART_SELECTION"
    status: Literal["PLAN", "APPLIED", "APPLIED_NEEDS_PCB_UPDATE", "BLOCKED"]
    project_id: Identifier
    edits: tuple[PartSourceEdit, ...] = ()
    pending_references: tuple[Identifier, ...] = ()
    locked_map: str | None = None
    issues: tuple[NonEmptyText, ...] = ()
    next_commands: tuple[NonEmptyText, ...] = ()
    receipt_dir: str
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


class AutoCadItem(StrictModel):
    reference: NonEmptyText
    footprint: str
    status: Literal["READY", "ALREADY_PRESENT", "NEEDS_REVIEW"]
    detail: NonEmptyText


class AutoCadPlan(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    preconditions: dict[RepositoryPath, Digest | None]
    after_hashes: dict[RepositoryPath, Digest]


class AutoCadAsset(StrictModel):
    source: NonEmptyText
    sha256: Digest
    destination: RepositoryPath


class AutoCadProvenance(StrictModel):
    schema_version: Literal["1"] = "1"
    footprint: NonEmptyText
    source: NonEmptyText
    source_sha256: Digest
    models: tuple[AutoCadAsset, ...]
    alignment_basis: Literal["matching_pad_geometry_and_authored_model_transforms"] = (
        "matching_pad_geometry_and_authored_model_transforms"
    )
    physical_fit_verified: Literal[False] = False


class AutoCadReport(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    status: Literal["PLAN", "APPLIED", "NEEDS_REVIEW", "BLOCKED"]
    items: tuple[AutoCadItem, ...] = ()
    files: tuple[RepositoryPath, ...] = ()
    issues: tuple[str, ...] = ()
    plan_path: str | None = None
    receipt_directory: str
    diff: str = ""
    build_authorized: Literal[False] = False


class SupplierHandoffPlan(StrictModel):
    """Reviewed, source-bound BOM payload for one explicit supplier submission."""

    schema_version: Literal["1"] = "1"
    supplier: Literal["digikey"] = "digikey"
    project_id: Identifier
    parts_report: RepositoryPath
    report_sha256: Digest
    payload: DigiKeyHandoffPayload
    payload_sha256: Digest
    source_hashes: Mapping[RepositoryPath, Digest]
    preconditions: Mapping[RepositoryPath, Digest | None]
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


class SupplierHandoffReport(StrictModel):
    schema_version: Literal["1"] = "1"
    status: Literal["PREPARED", "SENT", "UNCERTAIN", "BLOCKED"]
    project_id: Identifier
    supplier: Literal["digikey"] = "digikey"
    handoff: RepositoryPath
    handoff_sha256: Digest
    payload_sha256: Digest
    attempt_receipt: RepositoryPath | None = None
    single_use_url: (
        Annotated[
            str,
            StringConstraints(pattern=r"^https://www\.digikey\.com/short/[a-z0-9]{7,8}$"),
        ]
        | None
    ) = None
    issues: tuple[NonEmptyText, ...] = ()
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


ForeignFormat = Literal[
    "auto", "pads", "altium", "eagle", "cadstar", "fabmaster", "pcad", "solidworks"
]


class ForeignPcbReport(StrictModel):
    """Conversion evidence is intentionally weaker than an accepted native design."""

    schema_version: Literal["1"] = "1"
    status: Literal["PASS", "FAIL"]
    review_required: Literal[True] = True
    build_authorized: Literal[False] = False
    project_id: str
    toolchain_id: str
    input_format: str
    source_file: str
    source_sha256: Digest | None = None
    run_directory: str
    runner: Literal["none", "local", "container"] = "none"
    commands: Mapping[Identifier, CommandEvidence] = Field(default_factory=dict)
    native_summary: KiCadForeignImportSummary | None = None
    board_sha256: Digest | None = None
    import_preview: ProjectImportReport | None = None
    next_command: str | None = None
    next_actions: tuple[str, ...] = ()
    error: str | None = None

    @model_validator(mode="after")
    def successful_selection_is_valid(self) -> ForeignPcbReport:
        if self.status == "PASS" and (
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.project_id) is None
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.toolchain_id) is None
            or self.input_format not in ForeignFormat.__args__
        ):
            raise ValueError("Successful conversion needs valid project, toolchain and format IDs")
        return self


class ElectricalChartCase(StrictModel):
    """One chart and numeric export derived from a retained simulation case."""

    id: Identifier
    status: Literal["PASS", "SKIPPED", "FAIL"]
    samples: Annotated[int, Field(ge=0)] = 0
    waveform_sha256: Digest | None = None
    csv: RepositoryPath | None = None
    png: RepositoryPath | None = None
    svg: RepositoryPath | None = None
    detail: NonEmptyText


class ElectricalChartsReport(StrictModel):
    """Chart output remains secondary evidence bound to an analysis receipt."""

    schema_version: Literal["1"] = "1"
    lane: Literal["ELECTRICAL_CHARTS"] = "ELECTRICAL_CHARTS"
    build_authorized: Literal[False] = False
    project_id: Identifier
    status: Literal["PASS", "PARTIAL", "FAIL"]
    source_analysis_status: Literal["PASS", "FAIL", "NOT_CONFIGURED"]
    source_receipt: NonEmptyText
    source_report_sha256: Digest
    run_directory: NonEmptyText
    cases: tuple[ElectricalChartCase, ...]
    grounding_csv: RepositoryPath | None = None
    power_csv: RepositoryPath | None = None
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    next_actions: tuple[NonEmptyText, ...] = ()


class ElectricalChartsSuiteReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["ELECTRICAL_CHARTS_SUITE"] = "ELECTRICAL_CHARTS_SUITE"
    status: Literal["PASS", "PARTIAL", "FAIL"]
    run_directory: NonEmptyText
    reports: tuple[ElectricalChartsReport, ...]


class CadProviderIdentity(StrictModel):
    supplier_id: Annotated[str, StringConstraints(pattern=r"^C[1-9][0-9]*$")]
    component_supplier_id: Annotated[str, StringConstraints(pattern=r"^C[1-9][0-9]*$")]
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    package: NonEmptyText
    symbol_name: NonEmptyText
    model_uuid: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]
    model_title: str = ""


class CadSourceFile(StrictModel):
    path: RepositoryPath
    sha256: Digest
    source_url: str | None = None


class CadSourceBundle(StrictModel):
    schema_version: Literal["1"] = "1"
    provider: Literal["easyeda"] = "easyeda"
    supplier_id: Annotated[str, StringConstraints(pattern=r"^C[1-9][0-9]*$")]
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    package: NonEmptyText
    symbol_file: RepositoryPath
    symbol_name: NonEmptyText
    footprint_file: RepositoryPath
    footprint_name: NonEmptyText
    model_file: RepositoryPath
    files: tuple[CadSourceFile, ...]
    source_url: NonEmptyText
    source_sha256: Digest
    retrieved_at: NonEmptyText
    converter_version: Literal["1.0.1"] = "1.0.1"
    converter_sha256: Digest | None = None
    issues: tuple[NonEmptyText, ...] = ()


class CadSourceReport(StrictModel):
    status: Literal["READY", "BLOCKED"]
    supplier_id: str
    bundle_directory: str | None = None
    bundle: CadSourceBundle | None = None
    cache_hit: bool = False
    issues: tuple[NonEmptyText, ...] = ()
    receipt_directory: str


class CadStepReport(StrictModel):
    schema_version: Literal["1"] = "1"
    status: Literal["REVIEW", "BLOCKED"]
    project_id: Identifier
    supplier_id: str
    source_bundle_sha256: Digest | None = None
    source_step_sha256: Digest | None = None
    kicad_version: str | None = None
    image: str | None = None
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    commands: Mapping[str, CommandEvidence] = Field(default_factory=dict)
    issues: tuple[NonEmptyText, ...] = ()
    receipt_directory: str
    alignment_verified: Literal[False] = False
    physical_fit_verified: Literal[False] = False


class CadBundleCheck(StrictModel):
    status: Literal["READY", "BLOCKED"]
    symbol_pins: tuple[str, ...] = ()
    footprint_pads: tuple[str, ...] = ()
    model_references: tuple[str, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    physical_fit_verified: Literal[False] = False


class CadImportPlan(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    bundle_dir: str
    bundle_sha256: Digest
    preconditions: Mapping[RepositoryPath, Digest | None]
    after_hashes: Mapping[RepositoryPath, Digest]


class CadImportReport(StrictModel):
    status: Literal["PLAN", "APPLIED", "BLOCKED"]
    project_id: Identifier
    symbol_id: str | None = None
    footprint_id: str | None = None
    files: tuple[RepositoryPath, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    check: CadBundleCheck | None = None
    plan_path: str | None = None
    receipt_directory: str
    diff: str = ""
    build_authorized: Literal[False] = False


class CadSourcingReview(StrictModel):
    source: CadSourceReport
    import_plan: CadImportReport | None = None
    review_id: str


def register_design_lint_report(report_type: type[StrictModel]) -> None:
    """Re-export the moved report and resolve the forward model reference."""
    globals()["DesignLintReport"] = report_type
    ProjectVerificationReport.model_rebuild(_types_namespace={"DesignLintReport": report_type})


import sys as _sys

_report_module = _sys.modules.get(f"{__package__}.design_lint_report_models")
if _report_module is None or hasattr(_report_module, "DesignLintReport"):
    from .design_lint_report_models import DesignLintReport

    register_design_lint_report(DesignLintReport)
