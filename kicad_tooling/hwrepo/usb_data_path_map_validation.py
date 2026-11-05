"""Map-wide USB endpoint and component-reference consistency checks."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class _SeriesResistor(Protocol):
    @property
    def reference(self) -> str: ...


class _Line(Protocol):
    @property
    def series_resistor(self) -> _SeriesResistor | None: ...


class _InlineComponent(Protocol):
    @property
    def reference(self) -> str: ...


class _ReferenceBond(Protocol):
    @property
    def reference(self) -> str: ...


class _ProtectionShunt(Protocol):
    @property
    def reference(self) -> str: ...


class _Interface(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def connector_reference(self) -> str: ...

    @property
    def phy_reference(self) -> str: ...

    @property
    def positive(self) -> _Line: ...

    @property
    def negative(self) -> _Line: ...

    @property
    def inline_component(self) -> _InlineComponent | None: ...

    @property
    def reference_bond(self) -> _ReferenceBond | None: ...

    @property
    def protection_shunts(self) -> tuple[_ProtectionShunt, ...]: ...


class _SuperSpeedInterface(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def connector_reference(self) -> str: ...

    @property
    def phy_reference(self) -> str: ...

    @property
    def connector_signal_family(self) -> str: ...

    @property
    def phy_signal_family(self) -> str: ...


def validate_usb_data_path_map_references(
    interfaces: Sequence[_Interface],
    superspeed_interfaces: Sequence[_SuperSpeedInterface],
) -> None:
    """Validate uniqueness and prevent component-reference reuse across paths."""
    if not interfaces and not superspeed_interfaces:
        raise ValueError("USB data path maps need at least one USB 2.0 or SuperSpeed interface")
    interface_ids = [item.id.casefold() for item in (*interfaces, *superspeed_interfaces)]
    if len(set(interface_ids)) != len(interface_ids):
        raise ValueError("USB interface IDs must be unique")
    connector_references = [item.connector_reference.casefold() for item in interfaces]
    if len(set(connector_references)) != len(connector_references):
        raise ValueError("USB data connector references must be unique")
    superspeed_paths = [
        (
            item.connector_reference.casefold(),
            item.phy_reference.casefold(),
            item.connector_signal_family,
            item.phy_signal_family,
        )
        for item in superspeed_interfaces
    ]
    if len(set(superspeed_paths)) != len(superspeed_paths):
        raise ValueError("USB SuperSpeed reference paths must be unique")

    mapped_resistors = [
        line.series_resistor.reference.casefold()
        for item in interfaces
        for line in (item.positive, item.negative)
        if line.series_resistor is not None
    ]
    if len(set(mapped_resistors)) != len(mapped_resistors):
        raise ValueError("USB data series resistors must be unique across mapped paths")
    resistor_references = set(mapped_resistors)
    inline_references = {
        item.inline_component.reference.casefold()
        for item in interfaces
        if item.inline_component is not None
    }
    if len(inline_references) != sum(item.inline_component is not None for item in interfaces):
        raise ValueError("USB inline components must be unique across mapped paths")
    if inline_references & resistor_references:
        raise ValueError("USB inline components cannot also be mapped as series resistors")

    endpoint_references = {
        reference.casefold()
        for item in interfaces
        for reference in (item.connector_reference, item.phy_reference)
    }
    if inline_references & endpoint_references:
        raise ValueError("USB inline components cannot also be mapped endpoints")
    reference_bond_references = {
        item.reference_bond.reference.casefold()
        for item in interfaces
        if item.reference_bond is not None
    }
    if inline_references & reference_bond_references:
        raise ValueError("USB inline components cannot also be mapped reference bonds")

    protection_references = [
        shunt.reference.casefold() for item in interfaces for shunt in item.protection_shunts
    ]
    if len(set(protection_references)) != len(protection_references):
        raise ValueError("USB protection-shunt components must be unique across mapped paths")
    composite_references = {
        item.inline_component.reference.casefold()
        for item in interfaces
        if item.inline_component is not None
        and any(
            shunt.reference.casefold() == item.inline_component.reference.casefold()
            for shunt in item.protection_shunts
        )
    }
    if (
        set(protection_references) & (resistor_references | reference_bond_references)
        or (set(protection_references) & inline_references) != composite_references
    ):
        raise ValueError(
            "USB protection shunts cannot reuse path components except for an exact composite map"
        )
    if set(protection_references) & endpoint_references:
        raise ValueError("USB protection shunts cannot also be mapped endpoints")
