"""Review multiple fitted serial transmit functions assigned to one schematic net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .serial_participants import is_serial_ic_reference, serial_function_role_and_channel
from .signal_pair_tx_output_sharing import tx_output_sharing_groups

RULE_ID = "bus.serial_tx_outputs_share_net"


def serial_tx_output_sharing_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find unambiguous TX-function groups not already typed as output conflicts.

    A net with two or more native ``output`` pins is left to ERC. This review
    prompt focuses on same-role serial pins whose native electrical types do
    not already identify an output-to-output conflict.
    """
    return tuple(
        Candidate(
            rule_id=RULE_ID,
            subject=f"{', '.join(group.components)}: serial TX functions share {group.net}",
            message=(
                f"Fitted IC transmit-function pins {', '.join(group.pins)} share one schematic net "
                f"({group.net}), while their native electrical pin types are "
                f"{', '.join(group.pin_types)}. Review whether multiple transmitters are "
                "intentionally sharing this net or whether one pin assignment is wrong. "
                "The function names do not prove driver behavior or required peer topology."
            ),
            evidence={
                "components": group.components,
                "channels": tuple(channel.upper() for channel in group.channels),
                "functions": group.functions,
                "pins": group.pins,
                "pin_types": group.pin_types,
                "net": (group.net,),
            },
        )
        for group in tx_output_sharing_groups(
            observed,
            role_and_channel=serial_function_role_and_channel,
            is_supported_reference=is_serial_ic_reference,
            require_pin_inventory=False,
            skip_return_like_nets=True,
        )
    )
