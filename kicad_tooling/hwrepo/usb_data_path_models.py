"""Project-authored USB data-path requirements and reference-domain policy."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .model_primitives import (
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    ResistorReference,
    StrictModel,
    UsbDataPortGroup,
)
from .reference_bond_models import ReferenceBondRequirement
from .usb_data_path_component_models import (
    UsbDataPathInlinePinRequirement,
    UsbDataPathProtectionShuntRequirement,
)


class UsbDataSeriesResistorRequirement(StrictModel):
    """Exact project-selected USB data-line resistor and accepted nominal range."""

    reference: ResistorReference
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_resistance_range(self) -> UsbDataSeriesResistorRequirement:
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("USB data series-resistor range is reversed")
        return self


class UsbDataPathInlineComponentRequirement(StrictModel):
    """Reviewed exact pass-through pin map for one multi-pin USB inline component."""

    reference: Identifier
    expected_symbol: NonEmptyText
    expected_footprint: NonEmptyText
    positive_connector_pin: Reference
    positive_phy_pin: Reference
    negative_connector_pin: Reference
    negative_phy_pin: Reference
    pins: Annotated[tuple[UsbDataPathInlinePinRequirement, ...], Field(min_length=4)]

    @property
    def data_pins(self) -> tuple[str, ...]:
        return (
            self.positive_connector_pin,
            self.positive_phy_pin,
            self.negative_connector_pin,
            self.negative_phy_pin,
        )

    @model_validator(mode="after")
    def complete_distinct_component_pin_map(self) -> UsbDataPathInlineComponentRequirement:
        reference_prefix = f"{self.reference}.".casefold()
        pins = tuple(item.pin.casefold() for item in self.pins)
        if any(not item.pin.casefold().startswith(reference_prefix) for item in self.pins):
            raise ValueError("USB inline-component pin maps must belong to the declared component")
        if len(set(pins)) != len(pins):
            raise ValueError("USB inline-component pin maps must be unique")
        data_pins = tuple(pin.casefold() for pin in self.data_pins)
        if any(not pin.startswith(reference_prefix) for pin in data_pins):
            raise ValueError("USB inline data-path pins must belong to the declared component")
        if len(set(data_pins)) != len(data_pins):
            raise ValueError("USB inline D+ and D- pins must be distinct")
        if not set(data_pins) <= set(pins):
            raise ValueError("USB inline pin inventory must include all four data-path pins")
        return self


class UsbDataPathLineRequirement(StrictModel):
    """PHY-specific path; parallel pin tuples list every same-net contact."""

    line: Literal["D+", "D-"]
    connector_pin: Reference
    phy_pin: Reference
    connector_net: NetName
    phy_net: NetName
    topology: Literal["direct", "series_resistor", "inline_component"]
    connector_parallel_pins: tuple[Reference, ...] = ()
    phy_parallel_pins: tuple[Reference, ...] = ()
    series_resistor: UsbDataSeriesResistorRequirement | None = None

    @property
    def connector_pins(self) -> tuple[str, ...]:
        return (self.connector_pin, *self.connector_parallel_pins)

    @property
    def phy_pins(self) -> tuple[str, ...]:
        return (self.phy_pin, *self.phy_parallel_pins)

    @model_validator(mode="after")
    def topology_matches_resistor_disposition(self) -> UsbDataPathLineRequirement:
        for pin in (*self.connector_pins, *self.phy_pins):
            if "." not in pin:
                raise ValueError("USB data endpoint pins must use COMPONENT.PIN form")
        if len({pin.casefold() for pin in self.connector_pins}) != len(self.connector_pins):
            raise ValueError("USB connector data pins must be unique")
        if len({pin.casefold() for pin in self.phy_pins}) != len(self.phy_pins):
            raise ValueError("USB PHY data pins must be unique")
        if self.topology == "direct":
            if self.connector_net != self.phy_net or self.series_resistor is not None:
                raise ValueError(
                    "Direct USB data paths need one shared net and no series-resistor map"
                )
        elif self.topology == "series_resistor" and (
            self.connector_net == self.phy_net or self.series_resistor is None
        ):
            raise ValueError(
                "USB data series-resistor paths need distinct nets and an exact resistor map"
            )
        elif self.topology == "inline_component" and (
            self.connector_net == self.phy_net or self.series_resistor is not None
        ):
            raise ValueError(
                "USB inline-component paths need distinct nets and no series-resistor map"
            )
        return self


class UsbReferencePinRequirement(StrictModel):
    """One source-reviewed USB endpoint reference pin and expected native net."""

    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("USB reference pin mappings must use COMPONENT.PIN form")
        return value


class UsbDataInterfaceRequirement(StrictModel):
    """Reviewed connector-to-PHY USB 2.0 data pair and selected topology."""

    id: Identifier
    basis: NonEmptyText
    connector_reference: Identifier
    expected_connector_symbol: NonEmptyText
    expected_connector_footprint: NonEmptyText
    phy_reference: Identifier
    expected_phy_symbol: NonEmptyText
    expected_phy_footprint: NonEmptyText
    data_port_group: UsbDataPortGroup | None = None
    positive: UsbDataPathLineRequirement
    negative: UsbDataPathLineRequirement
    inline_component: UsbDataPathInlineComponentRequirement | None = None
    protection_shunts: tuple[UsbDataPathProtectionShuntRequirement, ...] = ()
    connector_reference_pins: tuple[UsbReferencePinRequirement, ...] = ()
    phy_reference_pins: tuple[UsbReferencePinRequirement, ...] = ()
    reference_policy: Literal["common_net", "bonded", "separate_nets"] | None = None
    reference_bond: ReferenceBondRequirement | None = None

    @model_validator(mode="after")
    def complete_distinct_pair(self) -> UsbDataInterfaceRequirement:
        if self.connector_reference.casefold() == self.phy_reference.casefold():
            raise ValueError("USB connector and PHY references must differ")
        if self.positive.line != "D+" or self.negative.line != "D-":
            raise ValueError("USB data pair must map one D+ line and one D- line")
        inline_lines = tuple(
            line.topology == "inline_component" for line in (self.positive, self.negative)
        )
        if self.inline_component is None and any(inline_lines):
            raise ValueError("USB inline-component data paths need an exact component map")
        if self.inline_component is not None and inline_lines != (True, True):
            raise ValueError("USB inline-component maps must cover both D+ and D- paths")
        if self.inline_component is not None and self.protection_shunts:
            raise ValueError(
                "USB inline-component and protection-shunt maps cannot be combined in one interface"
            )
        if self.protection_shunts and any(
            line.topology != "direct" for line in (self.positive, self.negative)
        ):
            raise ValueError("USB protection-shunt maps currently require direct data paths")
        if any(
            any(
                not pin.casefold().startswith(f"{self.connector_reference}.".casefold())
                for pin in line.connector_pins
            )
            or any(
                not pin.casefold().startswith(f"{self.phy_reference}.".casefold())
                for pin in line.phy_pins
            )
            for line in (self.positive, self.negative)
        ):
            raise ValueError("USB data endpoints must belong to the declared connector and PHY")
        if any(
            item.pin.rsplit(".", 1)[0].casefold() != self.connector_reference.casefold()
            for item in self.connector_reference_pins
        ):
            raise ValueError("USB connector reference pins must belong to the declared connector")
        if any(
            item.pin.rsplit(".", 1)[0].casefold() != self.phy_reference.casefold()
            for item in self.phy_reference_pins
        ):
            raise ValueError("USB PHY reference pins must belong to the declared PHY")
        connector_reference_ids = [item.pin.casefold() for item in self.connector_reference_pins]
        phy_reference_ids = [item.pin.casefold() for item in self.phy_reference_pins]
        if len(set(connector_reference_ids)) != len(connector_reference_ids):
            raise ValueError("USB connector reference pin mappings must be unique")
        if len(set(phy_reference_ids)) != len(phy_reference_ids):
            raise ValueError("USB PHY reference pin mappings must be unique")
        signal_pin_ids = {
            item.casefold()
            for item in (
                *self.positive.connector_pins,
                *self.positive.phy_pins,
                *self.negative.connector_pins,
                *self.negative.phy_pins,
            )
        }
        if signal_pin_ids & (set(connector_reference_ids) | set(phy_reference_ids)):
            raise ValueError("USB data and reference pin mappings must be distinct")
        if self.reference_policy is None:
            if self.connector_reference_pins or self.phy_reference_pins or self.reference_bond:
                raise ValueError("USB reference pin mappings need an explicit reference policy")
        else:
            if not self.connector_reference_pins or not self.phy_reference_pins:
                raise ValueError("USB reference policy needs mapped pins on both connector and PHY")
            connector_reference_nets = {
                item.net.casefold() for item in self.connector_reference_pins
            }
            phy_reference_nets = {item.net.casefold() for item in self.phy_reference_pins}
            if len(connector_reference_nets) != 1 or len(phy_reference_nets) != 1:
                raise ValueError("Each USB endpoint must use one declared reference net")
            if self.reference_policy == "common_net":
                if connector_reference_nets != phy_reference_nets:
                    raise ValueError("common_net USB reference pins must share one declared net")
                if self.reference_bond is not None:
                    raise ValueError("common_net USB reference policy cannot declare a bond")
            elif self.reference_policy == "separate_nets":
                if connector_reference_nets == phy_reference_nets:
                    raise ValueError("separate_nets USB reference policy needs distinct nets")
                if self.reference_bond is not None:
                    raise ValueError("separate_nets USB reference policy cannot declare a bond")
            elif connector_reference_nets == phy_reference_nets:
                raise ValueError("bonded USB reference policy needs distinct endpoint nets")
            elif self.reference_bond is None:
                raise ValueError("bonded USB reference policy needs one exact bond component")
            elif {
                self.reference_bond.side_a_net.casefold(),
                self.reference_bond.side_b_net.casefold(),
            } != connector_reference_nets | phy_reference_nets:
                raise ValueError("USB reference bond must join the mapped connector and PHY nets")
            elif self.reference_bond.reference.casefold() in {
                self.connector_reference.casefold(),
                self.phy_reference.casefold(),
            }:
                raise ValueError("USB reference bond cannot reuse an endpoint component")
        if self.reference_bond is not None and self.reference_bond.reference.casefold() in {
            line.series_resistor.reference.casefold()
            for line in (self.positive, self.negative)
            if line.series_resistor is not None
        }:
            raise ValueError("USB reference bond cannot reuse a data-line series resistor")
        if self.inline_component is not None:
            if self.inline_component.reference.casefold() in {
                self.connector_reference.casefold(),
                self.phy_reference.casefold(),
            }:
                raise ValueError("USB inline component cannot reuse an endpoint reference")
            if self.reference_bond is not None and (
                self.inline_component.reference.casefold()
                == self.reference_bond.reference.casefold()
            ):
                raise ValueError("USB inline component cannot reuse the reference-bond component")
            mapped_component_pins = {
                item.pin.casefold(): item for item in self.inline_component.pins
            }
            for line, connector_pin, phy_pin in (
                (
                    self.positive,
                    self.inline_component.positive_connector_pin,
                    self.inline_component.positive_phy_pin,
                ),
                (
                    self.negative,
                    self.inline_component.negative_connector_pin,
                    self.inline_component.negative_phy_pin,
                ),
            ):
                for pin, net in (
                    (connector_pin, line.connector_net),
                    (phy_pin, line.phy_net),
                ):
                    requirement = mapped_component_pins[pin.casefold()]
                    if requirement.disposition != "net" or requirement.net is None:
                        raise ValueError("USB inline data-path pins must have expected nets")
                    if requirement.net.casefold() != net.casefold():
                        raise ValueError(
                            "USB inline data-path pin nets must match the line's endpoint nets"
                        )
        if self.protection_shunts:
            expected_data_nets = {
                "D+": self.positive.connector_net.casefold(),
                "D-": self.negative.connector_net.casefold(),
            }
            reserved_pins = {
                pin.casefold()
                for pin in (
                    *self.positive.connector_pins,
                    *self.positive.phy_pins,
                    *self.negative.connector_pins,
                    *self.negative.phy_pins,
                    *(item.pin for item in self.connector_reference_pins),
                    *(item.pin for item in self.phy_reference_pins),
                )
            }
            series_references = {
                line.series_resistor.reference.casefold()
                for line in (self.positive, self.negative)
                if line.series_resistor is not None
            }
            if self.reference_bond is not None:
                reserved_pins.update(
                    {
                        self.reference_bond.side_a_pin.casefold(),
                        self.reference_bond.side_b_pin.casefold(),
                    }
                )
            shunt_references = [item.reference.casefold() for item in self.protection_shunts]
            if len(set(shunt_references)) != len(shunt_references):
                raise ValueError("USB protection-shunt references must be unique")
            for shunt in self.protection_shunts:
                if shunt.reference.casefold() in {
                    self.connector_reference.casefold(),
                    self.phy_reference.casefold(),
                    *series_references,
                    *(
                        ()
                        if self.reference_bond is None
                        else (self.reference_bond.reference.casefold(),)
                    ),
                } or (
                    self.inline_component is not None
                    and shunt.reference.casefold() == self.inline_component.reference.casefold()
                ):
                    raise ValueError(
                        "USB protection-shunt reference must be unique in the interface"
                    )
                shunt_pin_ids = {item.pin.casefold() for item in shunt.pins}
                if reserved_pins & shunt_pin_ids:
                    raise ValueError(
                        "USB protection-shunt pins must be distinct from endpoint pins"
                    )
                for data_pin in shunt.data_pins:
                    if data_pin.net.casefold() != expected_data_nets[data_pin.line]:
                        raise ValueError(
                            "USB protection-shunt data pin nets must match direct endpoint nets"
                        )
        mapped_signal_and_reference_pins = {
            item.casefold()
            for item in (
                *self.positive.connector_pins,
                *self.positive.phy_pins,
                *self.negative.connector_pins,
                *self.negative.phy_pins,
                *(item.pin for item in self.connector_reference_pins),
                *(item.pin for item in self.phy_reference_pins),
            )
        }
        if (
            self.reference_bond is not None
            and {
                self.reference_bond.side_a_pin.casefold(),
                self.reference_bond.side_b_pin.casefold(),
            }
            & mapped_signal_and_reference_pins
        ):
            raise ValueError("USB reference-bond pins must be distinct from endpoint pins")
        pins = (
            *self.positive.connector_pins,
            *self.positive.phy_pins,
            *self.negative.connector_pins,
            *self.negative.phy_pins,
        )
        if len({pin.casefold() for pin in pins}) != len(pins):
            raise ValueError("USB data pair endpoint pins must be unique")
        positive_nets = {
            self.positive.connector_net.casefold(),
            self.positive.phy_net.casefold(),
        }
        negative_nets = {
            self.negative.connector_net.casefold(),
            self.negative.phy_net.casefold(),
        }
        if positive_nets & negative_nets:
            raise ValueError("USB D+ and D- paths must use distinct declared nets")
        resistors = tuple(
            line.series_resistor.reference.casefold()
            for line in (self.positive, self.negative)
            if line.series_resistor is not None
        )
        if len(set(resistors)) != len(resistors):
            raise ValueError("USB D+ and D- paths must use distinct series resistors")
        if set(resistors) & {
            self.connector_reference.casefold(),
            self.phy_reference.casefold(),
        }:
            raise ValueError("USB data resistor cannot reuse a connector or PHY reference")
        if self.inline_component is not None and self.inline_component.reference.casefold() in {
            *resistors,
            self.connector_reference.casefold(),
            self.phy_reference.casefold(),
        }:
            raise ValueError("USB inline component reference must be unique within the interface")
        return self


class UsbDataPathMap(StrictModel):
    """Project-authored USB connector-to-PHY topology; no universal resistor is assumed."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    interfaces: Annotated[tuple[UsbDataInterfaceRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_interfaces_and_resistors(self) -> UsbDataPathMap:
        if len({item.id.casefold() for item in self.interfaces}) != len(self.interfaces):
            raise ValueError("USB data interface IDs must be unique")
        connector_references = [item.connector_reference.casefold() for item in self.interfaces]
        if len(set(connector_references)) != len(connector_references):
            raise ValueError("USB data connector references must be unique")
        resistor_references = [
            line.series_resistor.reference.casefold()
            for item in self.interfaces
            for line in (item.positive, item.negative)
            if line.series_resistor is not None
        ]
        if len(set(resistor_references)) != len(resistor_references):
            raise ValueError("USB data series resistors must be unique across mapped paths")
        inline_references = [
            item.inline_component.reference.casefold()
            for item in self.interfaces
            if item.inline_component is not None
        ]
        if len(set(inline_references)) != len(inline_references):
            raise ValueError("USB inline components must be unique across mapped paths")
        if set(inline_references) & set(resistor_references):
            raise ValueError("USB inline components cannot also be mapped as series resistors")
        endpoint_references = {
            reference.casefold()
            for item in self.interfaces
            for reference in (item.connector_reference, item.phy_reference)
        }
        if set(inline_references) & endpoint_references:
            raise ValueError("USB inline components cannot also be mapped endpoints")
        reference_bond_references = {
            item.reference_bond.reference.casefold()
            for item in self.interfaces
            if item.reference_bond is not None
        }
        if set(inline_references) & reference_bond_references:
            raise ValueError("USB inline components cannot also be mapped reference bonds")
        protection_shunt_references = [
            shunt.reference.casefold()
            for item in self.interfaces
            for shunt in item.protection_shunts
        ]
        if len(set(protection_shunt_references)) != len(protection_shunt_references):
            raise ValueError("USB protection-shunt components must be unique across mapped paths")
        if set(protection_shunt_references) & (
            set(inline_references) | set(resistor_references) | reference_bond_references
        ):
            raise ValueError("USB protection shunts cannot also be mapped path components")
        if set(protection_shunt_references) & endpoint_references:
            raise ValueError("USB protection shunts cannot also be mapped endpoints")
        return self
