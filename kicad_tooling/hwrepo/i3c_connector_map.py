"""Match source-bound connector maps to I3C signal roles and nets."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Literal

from .bus_signal_roles import i3c_signal_identity
from .connector_coverage_models import ConnectorMappedPinEvidence

I3cSignalRole = Literal["SDA", "SCL"]


def mapped_i3c_signal_role(signal: str) -> I3cSignalRole | None:
    """Recognize a bounded I3C SDA/SCL role in a reviewed interface map."""
    identity = i3c_signal_identity(signal)
    if identity is not None:
        return identity.role
    compact = re.sub(r"[^a-z0-9]", "", signal.casefold())
    if compact == "sda":
        return "SDA"
    if compact == "scl":
        return "SCL"
    return None


def i3c_source_map_covers_role(
    pin: str,
    expected_net: str,
    expected_role: I3cSignalRole,
    mapped: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    """Require exact current map evidence for one connector contact and net."""
    evidence = mapped.get(pin.casefold())
    if evidence is None or mapped_i3c_signal_role(evidence.interface_signal) != expected_role:
        return False
    return tuple(net.casefold() for net in evidence.nets) == (expected_net.casefold(),)
