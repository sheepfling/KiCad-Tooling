"""Required capability groups passed to the shared design-lint scanner."""

from __future__ import annotations

from dataclasses import dataclass

from .component_peer_pin_scan import ComponentPeerPinAssignmentScans
from .connector_coverage_models import ConnectorCoverageReport
from .connector_return_distribution_models import ConnectorReturnDistributionCoverageReport
from .connector_stateful_contact_models import ConnectorStatefulContactMap
from .crystal_network_models import CrystalNetworkCoverageReport
from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_control_inputs import ControlCandidateInputs
from .design_lint_pcb_inputs import PcbCandidateInputs
from .design_lint_peer_inputs import PeerCandidateInputs
from .design_lint_power_inputs import PowerCandidateInputs
from .design_lint_rule_models import DesignLintRuleCatalog
from .design_lint_types import Candidate
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .external_protection_models import ExternalProtectionCoverageReport
from .model_primitives import Digest
from .netlist_contract_models import NetlistContract
from .rc_filter_models import RcFilterCoverageReport
from .regulator_feedback_models import RegulatorFeedbackCoverageReport
from .schematic_geometry import SchematicGeometryScan
from .signal_divider_models import SignalDividerCoverageReport


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
class MappedCandidateInputs:
    """Source-bound schematic and mapped electrical requirement reports."""

    external_protection: ExternalProtectionCoverageReport | None
    crystal_network: CrystalNetworkCoverageReport | None
    regulator_feedback: RegulatorFeedbackCoverageReport | None
    signal_divider: SignalDividerCoverageReport | None
    rc_filter: RcFilterCoverageReport | None


@dataclass(frozen=True, slots=True)
class DesignLintCandidateInputs:
    """All required theme groups for shared legacy and prepared scans."""

    observed: NetlistContract
    catalog: DesignLintRuleCatalog
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
    usb_data_path: UsbDataPathCandidateInputs
    netlist_sha256: Digest | None = None
    schematic_source_candidates: tuple[Candidate, ...] = ()

    def __post_init__(self) -> None:
        if self.bus.observed is not self.observed and self.bus.observed != self.observed:
            raise ValueError("Candidate inputs must share one observed native netlist")
        if self.control.observed is not self.observed and self.control.observed != self.observed:
            raise ValueError("Candidate inputs must share one observed native netlist")
        if self.bus.reviewed_connector_references != self.reviewed_connector_references:
            raise ValueError("Candidate inputs must share reviewed connector references")
        if self.bus.component_peer_findings:
            raise ValueError("Component peer findings are computed by the candidate scanner")
