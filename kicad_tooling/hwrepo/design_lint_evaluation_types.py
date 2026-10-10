"""Typed context for deterministic design-lint report disposition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .bus_signal_pairs import (
    ComplementaryPinFunctionAliasResolution,
)
from .component_peer_pin_models import ComponentPeerPinRuleCoverage
from .component_roles import ComponentRoleResolution
from .connector_peer_pin_models import ConnectorPeerPinHeuristicCoverage
from .design_lint_pcb_coverage_policy import (
    PcbInputCoveragePolicyState,
    PcbMappedCoveragePolicyState,
)
from .design_lint_rule_models import DesignLintRuleCatalog
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .digital_peer_voltage_models import DigitalPeerVoltageRuleCoverage
from .digital_peer_voltage_types import DigitalPeerVoltageLintContext
from .models import (
    ConnectorCoverageReport,
    ConnectorReturnDistributionCoverageReport,
    ContractCoachReport,
    ControlInputBiasHeuristicCoverage,
    CrystalNetworkCoverageReport,
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintMappedCheckRun,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    Digest,
    ExternalProtectionCoverageReport,
    I2cAddressCoverageReport,
    I2cPullupHeuristicCoverage,
    PcbKeepoutCoverageReport,
    PcbProtectionPathCoverageReport,
    RcFilterCoverageReport,
    RegulatorFeedbackCoverageReport,
    RepositoryPath,
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
from .serial_peer_reference_models import SerialPeerReferenceCoverageReport
from .spi_participants import SpiRosterContext
from .usb_c_ports import UsbCPortRosterContext
from .usb_peer_reference_models import UsbPeerReferenceCoverageReport


@dataclass(frozen=True)
class DesignLintEvaluationRequest:
    """Public evaluation inputs grouped for the staged lint workflow."""

    project_id: str
    coach: ContractCoachReport
    policy: DesignLintPolicy
    connector_coverage: ConnectorCoverageReport | None = None
    schematic_geometry: SchematicGeometryScan | None = None
    geometry_coverage: SchematicGeometryCoverage | None = None
    i2c_address_coverage: I2cAddressCoverageReport | None = None
    external_protection_coverage: ExternalProtectionCoverageReport | None = None
    crystal_network_coverage: CrystalNetworkCoverageReport | None = None
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport | None = None
    rc_filter_coverage: RcFilterCoverageReport | None = None
    connector_return_distribution_coverage: ConnectorReturnDistributionCoverageReport | None = None
    pcb_decoupling_coverage: PcbDecouplingCoverageReport | None = None
    pcb_protection_path_coverage: PcbProtectionPathCoverageReport | None = None
    pcb_track_width_coverage: PcbTrackWidthCoverageReport | None = None
    pcb_switching_loop_coverage: PcbSwitchingLoopCoverageReport | None = None
    pcb_differential_pair_coverage: PcbDifferentialPairRuleCoverageReport | None = None
    stm32_pin_map_coverage: Stm32PinMapCoverageReport | None = None
    spi_roster: SpiRosterContext | None = None
    usb_c_port_roster: UsbCPortRosterContext | None = None
    pcb_reference_plane_coverage: PcbReferencePlaneCoverageReport | None = None
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage | None = None
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None
    digital_peer_voltage_context: DigitalPeerVoltageLintContext | None = None
    serial_peer_roster: SerialPeerRosterContext | None = None
    pcb_signal_path_coverage: PcbSignalPathRuleCoverageReport | None = None
    pcb_keepout_coverage: PcbKeepoutCoverageReport | None = None
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport | None = None


@dataclass(frozen=True)
class DesignLintResolvedCoverage:
    """Coverage evidence normalized for candidate evaluation and reporting."""

    geometry: SchematicGeometryCoverage
    i2c_address: I2cAddressCoverageReport
    external_protection: ExternalProtectionCoverageReport
    crystal_network: CrystalNetworkCoverageReport
    regulator_feedback: RegulatorFeedbackCoverageReport
    rc_filter: RcFilterCoverageReport
    connector_return_distribution: ConnectorReturnDistributionCoverageReport
    pcb_decoupling: PcbDecouplingCoverageReport
    pcb_protection_path: PcbProtectionPathCoverageReport
    pcb_track_width: PcbTrackWidthCoverageReport
    pcb_reference_plane: PcbReferencePlaneCoverageReport
    pcb_switching_loop: PcbSwitchingLoopCoverageReport
    pcb_differential_pair: PcbDifferentialPairRuleCoverageReport
    pcb_signal_path: PcbSignalPathRuleCoverageReport
    pcb_keepout: PcbKeepoutCoverageReport
    pcb_rf_module_antenna: PcbRfModuleAntennaCoverageReport
    stm32_pin_map: Stm32PinMapCoverageReport
    control_input_bias: ControlInputBiasHeuristicCoverage | None
    i2c_pullup_heuristic: I2cPullupHeuristicCoverage | None


@dataclass(frozen=True)
class DesignLintEvaluationPreparation:
    """Policy-resolved evidence and rule modes before theme candidate scans."""

    request: DesignLintEvaluationRequest
    catalog: DesignLintRuleCatalog
    source_hashes: Mapping[RepositoryPath, Digest]
    input_pcb_coverage: PcbInputCoveragePolicyState
    mapped_pcb_coverage: PcbMappedCoveragePolicyState
    coverage: DesignLintResolvedCoverage
    component_role_resolution: ComponentRoleResolution
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution
    overrides: Mapping[str, DesignLintRuleOverride]
    ignores: Mapping[str, DesignLintIgnore]
    default_modes: Mapping[DesignLintRuleId, Literal["review", "block", "off"]]


@dataclass(frozen=True)
class DesignLintEvaluationPreparationResult:
    """Either the preparation stage is complete or it produced an early report."""

    prepared: DesignLintEvaluationPreparation | None = None
    report: DesignLintReport | None = None


@dataclass(frozen=True)
class DesignLintEvaluationCandidates:
    """Theme candidates and peer coverage found from prepared evidence."""

    items: tuple[Candidate, ...]
    connector_peer_pin_coverage: ConnectorPeerPinHeuristicCoverage | None
    component_peer_pin_coverage: tuple[ComponentPeerPinRuleCoverage, ...]
    digital_peer_voltage_coverage: tuple[DigitalPeerVoltageRuleCoverage, ...]
    usb_peer_reference_coverage: UsbPeerReferenceCoverageReport | None
    serial_peer_reference_coverage: SerialPeerReferenceCoverageReport | None
    mapped_check_runs: tuple[DesignLintMappedCheckRun, ...]


@dataclass(frozen=True)
class DesignLintFindingDisposition:
    """Resolved finding list and ignore fingerprints observed in this evaluation."""

    seen: frozenset[str]
    findings: tuple[DesignLintFinding, ...]
    issue: str | None = None


@dataclass(frozen=True)
class DesignLintEvaluationReportInput:
    """All independently resolved evidence needed to finalize one lint report."""

    project_id: str
    coach: ContractCoachReport
    policy: DesignLintPolicy
    catalog: DesignLintRuleCatalog
    source_hashes: Mapping[RepositoryPath, Digest]
    seen: frozenset[str]
    findings: tuple[DesignLintFinding, ...]
    geometry_coverage: SchematicGeometryCoverage
    component_role_resolution: ComponentRoleResolution
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution
    i2c_address_coverage: I2cAddressCoverageReport
    external_protection_coverage: ExternalProtectionCoverageReport
    crystal_network_coverage: CrystalNetworkCoverageReport
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport
    rc_filter_coverage: RcFilterCoverageReport
    connector_return_distribution_coverage: ConnectorReturnDistributionCoverageReport
    pcb_decoupling_coverage: PcbDecouplingCoverageReport
    pcb_protection_path_coverage: PcbProtectionPathCoverageReport
    pcb_track_width_coverage: PcbTrackWidthCoverageReport
    pcb_reference_plane_coverage: PcbReferencePlaneCoverageReport
    pcb_switching_loop_coverage: PcbSwitchingLoopCoverageReport
    pcb_differential_pair_coverage: PcbDifferentialPairRuleCoverageReport
    pcb_signal_path_coverage: PcbSignalPathRuleCoverageReport
    pcb_keepout_coverage: PcbKeepoutCoverageReport
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport
    stm32_pin_map_coverage: Stm32PinMapCoverageReport
    mapped_check_runs: tuple[DesignLintMappedCheckRun, ...]
    connector_coverage: ConnectorCoverageReport | None
    connector_peer_pin_coverage: ConnectorPeerPinHeuristicCoverage | None
    component_peer_pin_coverage: tuple[ComponentPeerPinRuleCoverage, ...]
    digital_peer_voltage_coverage: tuple[DigitalPeerVoltageRuleCoverage, ...]
    usb_peer_reference_coverage: UsbPeerReferenceCoverageReport | None
    serial_peer_reference_coverage: SerialPeerReferenceCoverageReport | None
    control_input_bias_coverage: ControlInputBiasHeuristicCoverage | None
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None
