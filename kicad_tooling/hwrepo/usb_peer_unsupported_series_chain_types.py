"""Typed observations for bounded unmapped USB resistor-chain candidates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UsbSeriesResistorStage:
    """One fully inventoried fitted resistor between adjacent data nets."""

    reference: str
    symbol: str
    footprint: str
    value: str
    connector_pin: str
    phy_pin: str
    connector_net: str
    phy_net: str


@dataclass(frozen=True, slots=True)
class UsbSeriesLinePath:
    """One exact direct or unbranched resistor-only endpoint line path."""

    connector_net: str
    phy_net: str
    stages: tuple[UsbSeriesResistorStage, ...]


@dataclass(frozen=True, slots=True)
class UsbPeerUnsupportedSeriesChain:
    """One USB pair whose exact netlist topology includes a multi-stage line."""

    connector_reference: str
    phy_reference: str
    port_group: str | None
    positive: UsbSeriesLinePath
    negative: UsbSeriesLinePath
