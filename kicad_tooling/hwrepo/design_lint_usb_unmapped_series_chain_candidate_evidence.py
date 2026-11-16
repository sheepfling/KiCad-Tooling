"""Source projection and report candidate for unmapped USB series chains."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .design_lint_usb_data_path_inputs import UsbDataPathCandidateInputs
from .usb_peer_unsupported_series_chain_types import (
    UsbPeerUnsupportedSeriesChain,
    UsbSeriesLinePath,
)

USB_UNMAPPED_SERIES_CHAIN_RULE_ID: DesignLintRuleId = "bus.usb_unmapped_series_chain"


@dataclass(frozen=True, slots=True)
class UsbUnmappedSeriesChainFindingEvidence:
    """Observed chain plus the exact authored USB map input used for coverage."""

    path: UsbPeerUnsupportedSeriesChain
    data_path: UsbDataPathCandidateInputs


def _line_evidence(path: UsbSeriesLinePath) -> tuple[str, ...]:
    if not path.stages:
        return (f"direct: {path.connector_net} -> {path.phy_net}",)
    return tuple(
        f"{stage.reference} {stage.value} {stage.symbol} {stage.footprint}: "
        f"{stage.connector_pin} on {stage.connector_net} -> "
        f"{stage.phy_pin} on {stage.phy_net}"
        for stage in path.stages
    )


def project_usb_unmapped_series_chain_evidence(
    source: UsbUnmappedSeriesChainFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the typed netlist observation into stable, deterministic fields."""
    path = source.path
    evidence = {
        "connector": (path.connector_reference,),
        "PHY": (path.phy_reference,),
        "USB_D+_path": _line_evidence(path.positive),
        "USB_D-_path": _line_evidence(path.negative),
        "USB_topology_kind": ("unbranched_multi_stage_series_chain",),
        "USB_data_map_state": ("no map matches this connector/PHY port group",),
    }
    if path.port_group is not None:
        evidence["USB_port_group"] = (path.port_group,)
    if source.data_path.map_sha256 is not None:
        evidence["USB_data_map_sha256"] = (source.data_path.map_sha256,)
    return CandidateEvidenceProjection(
        rule_id=USB_UNMAPPED_SERIES_CHAIN_RULE_ID,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class UsbUnmappedSeriesChainCandidate(Candidate):
    """Review prompt whose fields are derived from one exact source projection."""

    source_evidence: UsbUnmappedSeriesChainFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UsbUnmappedSeriesChainFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> UsbUnmappedSeriesChainCandidate:
        projection = project_usb_unmapped_series_chain_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_usb_unmapped_series_chain_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("USB series-chain evidence must match its typed source projection")
