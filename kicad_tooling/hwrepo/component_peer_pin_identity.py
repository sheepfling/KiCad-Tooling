"""Shared identity context for component peer-pin review candidates."""

from __future__ import annotations

from .component_peer_pin_scan import PeerPinAssignmentOutlier


def component_peer_pin_identity_context(
    group: PeerPinAssignmentOutlier,
) -> tuple[str, str, str, dict[str, tuple[str, ...]]]:
    """Describe the exact native identity that made a peer group comparable."""
    if group.peer_identity_basis == "part_id":
        subject_identity = f"PART_ID {group.peer_identity}"
        identity_text = (
            f"the same native PART_ID {group.peer_identity!r} across distinct native symbols"
        )
        independent_net_text = "a shared PART_ID does not require peer pins to share a net"
    else:
        subject_identity = group.peer_identity
        identity_text = f"the exact native symbol {group.peer_identity!r}"
        independent_net_text = "identical symbols do not require peer pins to share a net"
    evidence: dict[str, tuple[str, ...]] = {
        "peer_group_basis": (group.peer_identity_basis,),
        "peer_group_identity": (group.peer_identity,),
        "peer_group_symbols": group.peer_symbols,
    }
    if group.peer_identity_basis == "exact_symbol":
        evidence["symbol"] = (group.peer_identity,)
    return subject_identity, identity_text, independent_net_text, evidence
