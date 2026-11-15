"""Recognize explicit CAN/FDCAN TX and RX function names."""

from __future__ import annotations

import re
from typing import Literal

from .casefold_mapping_lookup import lookup_unique_casefold
from .netlist_contract_models import NetlistContract

_CAN_PREFIX = re.compile(r"^(can|fdcan)([0-9]*)(txd?|rxd?)$")
_CAN_SUFFIX = re.compile(r"^(txd?|rxd?)(can|fdcan)([0-9]*)$")
_CAN_MODULE_MARKER = re.compile(
    r"(?<![a-z0-9])(?:can|fdcan)[\s_-]+(?:bus[\s_-]+)?(?:transceiver|module)(?![a-z0-9])",
    re.IGNORECASE,
)
_CAN_MODULE_DATA_ROLES: dict[str, Literal["tx", "rx"]] = {
    "tx": "tx",
    "txd": "tx",
    "rx": "rx",
    "rxd": "rx",
}
CAN_MODULE_CHANNEL = "can:module"


def can_module_data_role(value: str) -> Literal["tx", "rx"] | None:
    """Recognize generic data labels only when another clue identifies CAN."""
    function = re.sub(r"[^a-z0-9]", "", value.casefold())
    return _CAN_MODULE_DATA_ROLES.get(function)


def explicit_can_module_identity(observed: NetlistContract, reference: str) -> str | None:
    """Return explicit native CAN module text from one component's value/symbol."""
    component = lookup_unique_casefold(observed.components, reference)
    if component is None:
        return None
    symbol = lookup_unique_casefold(observed.component_symbols, reference)
    identity = " ".join(value for value in (symbol, component.value) if value)
    return identity if _CAN_MODULE_MARKER.search(identity) is not None else None


def can_signal_role_and_channel(value: str) -> tuple[Literal["tx", "rx"], str] | None:
    """Recognize explicit CAN/FDCAN roles without generic UART aliases."""
    function = re.sub(r"[^a-z0-9]", "", value.casefold())
    match = _CAN_PREFIX.fullmatch(function)
    if match is not None:
        protocol, index, signal = match.groups()
    else:
        match = _CAN_SUFFIX.fullmatch(function)
        if match is None:
            return None
        signal, protocol, index = match.groups()
    role: Literal["tx", "rx"] = "tx" if signal.startswith("tx") else "rx"
    channel = f"{protocol}:index{index}" if index else f"{protocol}:default"
    return role, channel


def can_channel_label(channel: str) -> str:
    """Format a recognized CAN/FDCAN channel for stable report evidence."""
    protocol, separator, channel_index = channel.partition(":")
    if not separator or not protocol or not channel_index:
        raise ValueError("CAN channel labels require a recognized protocol channel")
    return (
        protocol.upper()
        if channel_index == "default"
        else f"{protocol.upper()} channel {channel_index.removeprefix('index')}"
    )
