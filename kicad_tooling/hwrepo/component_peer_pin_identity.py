"""Shared identity context for component peer-pin review candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .component_peer_pin_scan import PeerPinAssignmentOutlier


@dataclass(frozen=True, slots=True)
class ComponentPeerPinIdentityContext:
    """Named identity and copy-ready wording for component-peer findings."""

    subject_identity: str
    identity_description: str
    independent_net_note: str
    peer_identity_basis: Literal["exact_symbol", "part_id"]
    peer_identity: str
    peer_symbols: tuple[str, ...]

    @property
    def evidence(self) -> dict[str, tuple[str, ...]]:
        """Project typed identity fields into the established finding payload."""
        evidence: dict[str, tuple[str, ...]] = {
            "peer_group_basis": (self.peer_identity_basis,),
            "peer_group_identity": (self.peer_identity,),
            "peer_group_symbols": self.peer_symbols,
        }
        if self.peer_identity_basis == "exact_symbol":
            evidence["symbol"] = (self.peer_identity,)
        return evidence


def component_peer_pin_identity_context(
    group: PeerPinAssignmentOutlier,
) -> ComponentPeerPinIdentityContext:
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
    return ComponentPeerPinIdentityContext(
        subject_identity=subject_identity,
        identity_description=identity_text,
        independent_net_note=independent_net_text,
        peer_identity_basis=group.peer_identity_basis,
        peer_identity=group.peer_identity,
        peer_symbols=group.peer_symbols,
    )
