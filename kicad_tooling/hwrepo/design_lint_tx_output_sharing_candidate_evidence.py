"""Typed source projections for CAN and serial TX-sharing findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .can_signal_functions import can_channel_label, can_signal_role_and_channel
from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .serial_participants import is_serial_ic_reference, serial_function_role_and_channel
from .signal_pair_tx_output_sharing import TxOutputSharingGroup, tx_output_sharing_groups

CAN_TX_OUTPUT_SHARING_RULE_ID: DesignLintRuleId = "bus.can_tx_outputs_share_net"
SERIAL_TX_OUTPUT_SHARING_RULE_ID: DesignLintRuleId = "bus.serial_tx_outputs_share_net"


@dataclass(frozen=True, slots=True)
class CanTxOutputSharingEvidence:
    """A current CAN TX group produced by the canonical sharing scan."""

    observed: NetlistContract
    group: TxOutputSharingGroup

    def __post_init__(self) -> None:
        current_groups = tx_output_sharing_groups(
            self.observed,
            role_and_channel=can_signal_role_and_channel,
            is_supported_reference=is_integrated_circuit_reference,
            require_pin_inventory=True,
            skip_return_like_nets=False,
        )
        if self.group not in current_groups:
            raise ValueError("CAN TX group must match the current fitted netlist")


@dataclass(frozen=True, slots=True)
class SerialTxOutputSharingEvidence:
    """A current serial TX group produced by the canonical sharing scan."""

    observed: NetlistContract
    group: TxOutputSharingGroup

    def __post_init__(self) -> None:
        current_groups = tx_output_sharing_groups(
            self.observed,
            role_and_channel=serial_function_role_and_channel,
            is_supported_reference=is_serial_ic_reference,
            require_pin_inventory=False,
            skip_return_like_nets=True,
        )
        if self.group not in current_groups:
            raise ValueError("Serial TX group must match the current fitted netlist")


TxOutputSharingEvidence: TypeAlias = CanTxOutputSharingEvidence | SerialTxOutputSharingEvidence


def project_tx_output_sharing_evidence(
    source: TxOutputSharingEvidence,
) -> CandidateEvidenceProjection:
    """Project protocol-owned source records into their stable wire fields."""
    group = source.group
    if isinstance(source, CanTxOutputSharingEvidence):
        rule_id = CAN_TX_OUTPUT_SHARING_RULE_ID
        channels = tuple(
            sorted((can_channel_label(item) for item in group.channels), key=str.casefold)
        )
    else:
        rule_id = SERIAL_TX_OUTPUT_SHARING_RULE_ID
        channels = tuple(channel.upper() for channel in group.channels)
    return CandidateEvidenceProjection(
        rule_id=rule_id,
        evidence={
            "components": group.components,
            "channels": channels,
            "functions": group.functions,
            "pins": group.pins,
            "pin_types": group.pin_types,
            "net": (group.net,),
        },
    )


@dataclass(frozen=True, slots=True)
class TxOutputSharingCandidate(Candidate):
    """Candidate bound to one current CAN or serial TX-sharing source group."""

    source_evidence: TxOutputSharingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: TxOutputSharingEvidence,
        *,
        subject: str,
        message: str,
    ) -> TxOutputSharingCandidate:
        projection = project_tx_output_sharing_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_tx_output_sharing_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("TX-sharing fields must match their typed source projection")
