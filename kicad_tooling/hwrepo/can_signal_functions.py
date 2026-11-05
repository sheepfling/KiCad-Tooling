"""Recognize explicit CAN/FDCAN TX and RX function names."""

from __future__ import annotations

import re
from typing import Literal

_CAN_PREFIX = re.compile(r"^(can|fdcan)([0-9]*)(txd?|rxd?)$")
_CAN_SUFFIX = re.compile(r"^(txd?|rxd?)(can|fdcan)([0-9]*)$")


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
