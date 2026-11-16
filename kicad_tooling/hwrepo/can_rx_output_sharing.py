"""Review fitted CAN transceiver receiver outputs sharing one schematic net."""

from __future__ import annotations

from .can_signal_functions import (
    CAN_MODULE_CHANNEL,
    can_channel_label,
    can_module_data_role,
    can_signal_role_and_channel,
    explicit_can_module_identity,
)
from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract
from .signal_pair_output_sharing import signal_output_sharing_groups

RULE_ID = "bus.can_rx_outputs_share_net"


def can_rx_output_sharing_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find fitted CAN module RX outputs sharing one exact non-return net."""

    def role_and_channel(reference: str, function: str) -> tuple[str, str] | None:
        if explicit_can_module_identity(observed, reference) is None:
            return None
        protocol_role = can_signal_role_and_channel(function)
        if protocol_role is not None:
            return protocol_role
        if can_module_data_role(function) == "rx":
            return "rx", CAN_MODULE_CHANNEL
        return None

    findings: list[Candidate] = []
    groups = signal_output_sharing_groups(
        observed,
        role_and_channel=role_and_channel,
        expected_role="rx",
        is_supported_reference=is_integrated_circuit_reference,
        require_pin_inventory=True,
        skip_return_like_nets=True,
        exclude_nets_with_incomplete_evidence=True,
    )
    for group in groups:
        identity_basis = tuple(
            sorted(
                {
                    explicit_can_module_identity(observed, reference) or ""
                    for reference in group.components
                },
                key=str.casefold,
            )
        )
        channels = tuple(
            sorted(
                (
                    "CAN module" if item == CAN_MODULE_CHANNEL else can_channel_label(item)
                    for item in group.channels
                ),
                key=str.casefold,
            )
        )
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{', '.join(group.components)}: CAN receiver outputs share {group.net}",
                message=(
                    f"Fitted CAN module receiver-output pins {', '.join(group.pins)} share one "
                    f"schematic net ({group.net}) with native pin types "
                    f"{', '.join(group.pin_types)}. Review whether these outputs are "
                    "intentionally connected. The explicit component text, pin functions, and "
                    "net assignments do not establish output behavior, system topology, PCB "
                    "copper, or off-board wiring."
                ),
                evidence={
                    "components": group.components,
                    "channels": channels,
                    "functions": group.functions,
                    "pins": group.pins,
                    "pin_types": group.pin_types,
                    "net": (group.net,),
                    "identity_basis": identity_basis,
                },
            )
        )
    return tuple(findings)
