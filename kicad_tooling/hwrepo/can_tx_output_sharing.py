"""Review multiple CAN controller transmit pins sharing one schematic net."""

from __future__ import annotations

from .can_signal_functions import can_signal_role_and_channel
from .component_references import is_integrated_circuit_reference
from .design_lint_tx_output_sharing_candidate_evidence import (
    CanTxOutputSharingEvidence,
    TxOutputSharingCandidate,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .signal_pair_tx_output_sharing import tx_output_sharing_groups

RULE_ID = "bus.can_tx_outputs_share_net"


def can_tx_output_sharing_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find multiple fitted CAN transmit-function pins on one native net."""
    findings: list[Candidate] = []
    for group in tx_output_sharing_groups(
        observed,
        role_and_channel=can_signal_role_and_channel,
        is_supported_reference=is_integrated_circuit_reference,
        require_pin_inventory=True,
        skip_return_like_nets=False,
    ):
        findings.append(
            TxOutputSharingCandidate.from_source_evidence(
                CanTxOutputSharingEvidence(observed=observed, group=group),
                subject=f"{', '.join(group.components)}: CAN TX functions share {group.net}",
                message=(
                    f"Fitted CAN transmit-function pins {', '.join(group.pins)} share one "
                    f"schematic net ({group.net}), while their native electrical pin types are "
                    f"{', '.join(group.pin_types)}. Review whether multiple CAN transmitters are "
                    "intentionally sharing this net or whether one pin assignment is wrong. "
                    "Function names do not prove driver behavior or required bus topology."
                ),
            )
        )
    return tuple(findings)
