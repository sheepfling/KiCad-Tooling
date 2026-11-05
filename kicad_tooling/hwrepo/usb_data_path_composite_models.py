"""Validation for shared USB inline-path and protection-component maps."""

from __future__ import annotations

from typing import Protocol


class _PinMap(Protocol):
    @property
    def pin(self) -> str: ...

    @property
    def disposition(self) -> str: ...

    @property
    def net(self) -> str | None: ...


class _InlineMap(Protocol):
    @property
    def reference(self) -> str: ...

    @property
    def expected_symbol(self) -> str: ...

    @property
    def expected_footprint(self) -> str: ...

    @property
    def pins(self) -> tuple[_PinMap, ...]: ...

    @property
    def positive_connector_pin(self) -> str: ...

    @property
    def positive_phy_pin(self) -> str: ...

    @property
    def negative_connector_pin(self) -> str: ...

    @property
    def negative_phy_pin(self) -> str: ...


class _ProtectionDataPin(Protocol):
    @property
    def pin(self) -> str: ...

    @property
    def line(self) -> str: ...

    @property
    def net(self) -> str: ...


class _ProtectionMap(Protocol):
    @property
    def reference(self) -> str: ...

    @property
    def expected_symbol(self) -> str: ...

    @property
    def expected_footprint(self) -> str: ...

    @property
    def pins(self) -> tuple[_PinMap, ...]: ...

    @property
    def data_pins(self) -> tuple[_ProtectionDataPin, ...]: ...


class _PathLine(Protocol):
    @property
    def connector_net(self) -> str: ...

    @property
    def phy_net(self) -> str: ...


def validate_composite_inline_protection_map(
    inline: _InlineMap,
    protection: _ProtectionMap,
    positive: _PathLine,
    negative: _PathLine,
) -> None:
    """Require identical full component maps and four exact line-side data pins."""
    inline_pins = {item.pin.casefold(): item for item in inline.pins}
    protection_pins = {item.pin.casefold(): item for item in protection.pins}
    if (
        protection.reference.casefold() != inline.reference.casefold()
        or protection.expected_symbol != inline.expected_symbol
        or protection.expected_footprint != inline.expected_footprint
        or protection_pins.keys() != inline_pins.keys()
        or any(
            protection_pins[pin].disposition != inline_pins[pin].disposition
            or (protection_pins[pin].net or "").casefold()
            != (inline_pins[pin].net or "").casefold()
            for pin in inline_pins
        )
    ):
        raise ValueError("Composite USB inline protection maps need one exact identity and pin map")

    expected_data_pins = {
        (
            "D+",
            inline.positive_connector_pin.casefold(),
            positive.connector_net.casefold(),
        ),
        ("D+", inline.positive_phy_pin.casefold(), positive.phy_net.casefold()),
        (
            "D-",
            inline.negative_connector_pin.casefold(),
            negative.connector_net.casefold(),
        ),
        ("D-", inline.negative_phy_pin.casefold(), negative.phy_net.casefold()),
    }
    actual_data_pins = {
        (item.line, item.pin.casefold(), item.net.casefold()) for item in protection.data_pins
    }
    if actual_data_pins != expected_data_pins:
        raise ValueError("Composite USB protection data pins must map both sides of D+ and D-")
