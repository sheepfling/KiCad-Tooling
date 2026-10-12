"""Typed USB-C contract and analysis models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .analysis_state_models import (
    AnalysisNotApplicable,
    AnalysisPending,
)
from .model_primitives import (
    ElectricalPositive,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeMeasure,
    Reference,
    ResistorReference,
    StrictModel,
)


class UsbCcResistorAttachment(StrictModel):
    """A project-authored Rp or Rd resistor on one connector CC line."""

    kind: Literal["resistor"]
    behavior: Literal["rp", "rd"]
    reference: ResistorReference
    rail_net: NetName
    minimum_ohms: ElectricalPositive
    maximum_ohms: ElectricalPositive

    @model_validator(mode="after")
    def valid_range(self) -> UsbCcResistorAttachment:
        if self.maximum_ohms < self.minimum_ohms:
            raise ValueError("USB-C CC maximum resistance is below its minimum")
        return self


class UsbCcControllerAttachment(StrictModel):
    """An exact CC pin on an external USB-C controller."""

    kind: Literal["controller"]
    controller_pin: Reference

    @field_validator("controller_pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("USB-C controller pins must use COMPONENT.PIN form")
        return value


UsbCcAttachment = Annotated[
    UsbCcResistorAttachment | UsbCcControllerAttachment,
    Field(discriminator="kind"),
]


class UsbCcLineRequirement(StrictModel):
    connector_pin: Reference
    net: NetName
    attachment: UsbCcAttachment

    @field_validator("connector_pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("USB-C connector pins must use COMPONENT.PIN form")
        return value


class UsbCControllerRequirement(StrictModel):
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText


class UsbCNetPinAssignment(StrictModel):
    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("USB-C pin mappings must use COMPONENT.PIN form")
        return value


class UsbCVbusPathElement(StrictModel):
    """One project-mapped component boundary in a USB-C VBUS path."""

    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    port_side_net: NetName
    system_side_net: NetName
    port_side_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    system_side_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    pin_assignments: Annotated[tuple[UsbCNetPinAssignment, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def valid_pin_mapping(self) -> UsbCVbusPathElement:
        port_pins = {pin.casefold() for pin in self.port_side_pins}
        system_pins = {pin.casefold() for pin in self.system_side_pins}
        if len(port_pins) != len(self.port_side_pins):
            raise ValueError("USB-C VBUS path port-side pins must be unique")
        if len(system_pins) != len(self.system_side_pins):
            raise ValueError("USB-C VBUS path system-side pins must be unique")
        if port_pins & system_pins:
            raise ValueError("USB-C VBUS path component sides must use distinct pins")
        if any(
            pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for pin in (*self.port_side_pins, *self.system_side_pins)
        ):
            raise ValueError("USB-C VBUS path pins must belong to the named component")
        mapped: dict[str, str] = {}
        for assignment in self.pin_assignments:
            if assignment.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold():
                raise ValueError("USB-C VBUS path pin mappings must belong to the named component")
            key = assignment.pin.casefold()
            if key in mapped:
                raise ValueError("USB-C VBUS path pin mappings must be unique")
            mapped[key] = assignment.net
        for pin in self.port_side_pins:
            if mapped.get(pin.casefold()) != self.port_side_net:
                raise ValueError("USB-C VBUS path port-side pins must map to the port-side net")
        for pin in self.system_side_pins:
            if mapped.get(pin.casefold()) != self.system_side_net:
                raise ValueError("USB-C VBUS path system-side pins must map to the system-side net")
        if self.port_side_net == self.system_side_net:
            raise ValueError("USB-C VBUS path element must span distinct nets")
        return self


class UsbCVbusPathRequirement(StrictModel):
    """An exact, ordered schematic map from a USB-C connector to a board pin."""

    id: Identifier
    basis: NonEmptyText
    connector_pin: Reference
    connector_net: NetName
    board_pin: Reference
    board_net: NetName
    elements: Annotated[tuple[UsbCVbusPathElement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def continuous_path(self) -> UsbCVbusPathRequirement:
        if self.connector_pin.casefold() == self.board_pin.casefold():
            raise ValueError("USB-C VBUS path endpoint pins must be distinct")
        if self.connector_net == self.board_net:
            raise ValueError("USB-C VBUS path endpoint nets must be distinct")
        references = [item.reference.casefold() for item in self.elements]
        if len(set(references)) != len(references):
            raise ValueError("USB-C VBUS path component references must be unique")
        nets = [self.connector_net]
        expected_net = self.connector_net
        for element in self.elements:
            if element.port_side_net != expected_net:
                raise ValueError("USB-C VBUS path elements must form one ordered net chain")
            expected_net = element.system_side_net
            nets.append(expected_net)
        if expected_net != self.board_net:
            raise ValueError("USB-C VBUS path must end on the declared board-side net")
        if len(set(nets)) != len(nets):
            raise ValueError("USB-C VBUS path nets must not repeat")
        return self


class UsbCProtectionComponentRequirement(StrictModel):
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pins: Annotated[tuple[UsbCNetPinAssignment, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def pins_belong_to_component(self) -> UsbCProtectionComponentRequirement:
        if len({item.pin for item in self.pins}) != len(self.pins):
            raise ValueError("USB-C protection pin mappings must be unique")
        if any(item.pin.rsplit(".", 1)[0] != self.reference for item in self.pins):
            raise ValueError("USB-C protection pin mappings must belong to the named component")
        return self


class UsbCProtectionAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    components: Annotated[tuple[UsbCProtectionComponentRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_components(self) -> UsbCProtectionAnalysis:
        refs = [item.reference.casefold() for item in self.components]
        if len(set(refs)) != len(refs):
            raise ValueError("USB-C protection component references must be unique")
        return self


class UsbCVbusCapacitorRequirement(StrictModel):
    """One exact fitted capacitor mapped across the port-side VBUS and return nets."""

    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    pins: Annotated[tuple[UsbCNetPinAssignment, UsbCNetPinAssignment], Field(min_length=2)]

    @model_validator(mode="after")
    def valid_pin_map(self) -> UsbCVbusCapacitorRequirement:
        if len({item.pin.casefold() for item in self.pins}) != 2:
            raise ValueError("USB-C VBUS capacitor must map two unique pins")
        if any(
            item.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold() for item in self.pins
        ):
            raise ValueError("USB-C VBUS capacitor pins must belong to the named component")
        if self.pins[0].net.casefold() == self.pins[1].net.casefold():
            raise ValueError("USB-C VBUS capacitor pins must connect to distinct nets")
        return self


class UsbCVbusCapacitanceRequirement(StrictModel):
    """Project-sourced nominal total capacitance limits for one USB-C port."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    minimum_nf: NonNegativeMeasure
    maximum_nf: ElectricalPositive
    capacitors: Annotated[tuple[UsbCVbusCapacitorRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def valid_range_and_unique_components(self) -> UsbCVbusCapacitanceRequirement:
        if self.maximum_nf < self.minimum_nf:
            raise ValueError("USB-C VBUS capacitance maximum is below its minimum")
        references = [item.reference.casefold() for item in self.capacitors]
        if len(set(references)) != len(references):
            raise ValueError("USB-C VBUS capacitor references must be unique")
        return self


class UsbCPortRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    connector: Identifier
    role: Literal["source", "sink", "dual_role", "debug_accessory"]
    cc1: UsbCcLineRequirement
    cc2: UsbCcLineRequirement
    vbus_net: NetName
    vbus_pins: Annotated[tuple[UsbCNetPinAssignment, ...], Field(min_length=2)]
    ground_net: NetName
    ground_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    vbus_capacitance: Annotated[
        UsbCVbusCapacitanceRequirement | AnalysisNotApplicable | AnalysisPending,
        Field(discriminator="mode"),
    ]
    source_rail: NetName | None = None
    controller: UsbCControllerRequirement | None = None
    vbus_path: UsbCVbusPathRequirement | None = None
    protection: Annotated[
        UsbCProtectionAnalysis | AnalysisNotApplicable | AnalysisPending,
        Field(discriminator="mode"),
    ]

    @model_validator(mode="after")
    def valid_port_topology(self) -> UsbCPortRequirement:
        nets = (self.cc1.net, self.cc2.net, self.vbus_net, self.ground_net)
        if len(set(nets)) != len(nets):
            raise ValueError("USB-C CC1, CC2, VBUS, and ground nets must be distinct")
        connector_prefix = f"{self.connector}."
        connector_pins = (self.cc1.connector_pin, self.cc2.connector_pin)
        if any(not pin.startswith(connector_prefix) for pin in connector_pins):
            raise ValueError("USB-C CC pins must belong to the declared connector")
        if not any(
            assignment.pin.startswith(connector_prefix) and assignment.net == self.vbus_net
            for assignment in self.vbus_pins
        ):
            raise ValueError("USB-C VBUS pins must include a pin on the declared connector")
        if all(assignment.pin.startswith(connector_prefix) for assignment in self.vbus_pins):
            raise ValueError("USB-C VBUS pins must include a board-side pin")
        if any(
            assignment.pin.startswith(connector_prefix) and assignment.net != self.vbus_net
            for assignment in self.vbus_pins
        ):
            raise ValueError("USB-C connector VBUS pins must use the declared VBUS net")
        if len({assignment.pin for assignment in self.vbus_pins}) != len(self.vbus_pins):
            raise ValueError("USB-C VBUS pin declarations must be unique")
        if self.vbus_path is not None:
            path = self.vbus_path
            mapped_vbus = {(item.pin, item.net) for item in self.vbus_pins}
            if not path.connector_pin.startswith(connector_prefix):
                raise ValueError("USB-C VBUS path connector endpoint must belong to the port")
            if path.connector_net != self.vbus_net:
                raise ValueError("USB-C VBUS path connector endpoint must use the port VBUS net")
            if path.board_pin.startswith(connector_prefix):
                raise ValueError("USB-C VBUS path board endpoint must be a board-side pin")
            if (path.connector_pin, path.connector_net) not in mapped_vbus or (
                path.board_pin,
                path.board_net,
            ) not in mapped_vbus:
                raise ValueError(
                    "USB-C VBUS path endpoints must match declared VBUS pin assignments"
                )
        if not any(pin.startswith(connector_prefix) for pin in self.ground_pins):
            raise ValueError("USB-C ground pins must include a pin on the declared connector")
        if all(pin.startswith(connector_prefix) for pin in self.ground_pins):
            raise ValueError("USB-C ground pins must include a board-side return pin")
        all_pins = (
            *connector_pins,
            *(assignment.pin for assignment in self.vbus_pins),
            *self.ground_pins,
        )
        if len(set(all_pins)) != len(all_pins):
            raise ValueError("USB-C CC, VBUS, and ground pin declarations must be unique")
        if self.source_rail in {self.cc1.net, self.cc2.net, self.ground_net}:
            raise ValueError("USB-C source rail must be distinct from CC and ground nets")
        if self.role != "source" and self.source_rail is not None:
            raise ValueError("Only USB-C source ports may declare a source rail")

        attachments = (self.cc1.attachment, self.cc2.attachment)
        resistor_attachments = tuple(
            item for item in attachments if isinstance(item, UsbCcResistorAttachment)
        )
        controller_attachments = tuple(
            item for item in attachments if isinstance(item, UsbCcControllerAttachment)
        )
        if len({item.reference.casefold() for item in resistor_attachments}) != len(
            resistor_attachments
        ):
            raise ValueError("USB-C CC resistor references must be unique across both lines")
        if self.role == "source":
            if any(item.behavior != "rp" for item in resistor_attachments):
                raise ValueError("USB-C source CC resistors must be declared as Rp")
            if resistor_attachments and self.source_rail is None:
                raise ValueError("USB-C source Rp requirements must name the source rail")
            if self.source_rail is not None and any(
                item.rail_net != self.source_rail for item in resistor_attachments
            ):
                raise ValueError("USB-C source Rp resistors must use the declared source rail")
        elif self.role == "sink":
            if any(item.behavior != "rd" for item in resistor_attachments):
                raise ValueError("USB-C sink CC resistors must be declared as Rd")
            if any(item.rail_net != self.ground_net for item in resistor_attachments):
                raise ValueError("USB-C sink Rd resistors must connect to the declared ground net")
        elif self.role == "dual_role" and len(controller_attachments) != 2:
            raise ValueError("USB-C dual-role ports require controller pins for both CC lines")

        if controller_attachments:
            if self.controller is None:
                raise ValueError("USB-C controller pin mappings need a controller identity")
            if any(
                item.controller_pin.rsplit(".", 1)[0].casefold()
                != self.controller.reference.casefold()
                for item in controller_attachments
            ):
                raise ValueError("USB-C CC controller pins must belong to the declared controller")
            if len({item.controller_pin.casefold() for item in controller_attachments}) != len(
                controller_attachments
            ):
                raise ValueError("USB-C CC controller pins must be unique")
        elif self.controller is not None:
            raise ValueError("USB-C controller identity has no mapped CC pins")
        if (
            self.role in {"source", "sink"}
            and len(attachments) == 2
            and type(attachments[0]) is not type(attachments[1])
        ):
            raise ValueError(
                "USB-C source or sink CC lines must both use resistors or controller pins"
            )
        if self.role == "dual_role" and any(
            not isinstance(item, UsbCcControllerAttachment) for item in attachments
        ):
            raise ValueError("USB-C dual-role ports require controller pins for both CC lines")
        return self


class UsbCAnalysis(StrictModel):
    """Project-authored USB-C port role, CC, VBUS, ground, and protection requirements."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    ports: Annotated[tuple[UsbCPortRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_ports_and_cc_nets(self) -> UsbCAnalysis:
        if len({port.id for port in self.ports}) != len(self.ports):
            raise ValueError("USB-C port IDs must be unique")
        if len({port.connector.casefold() for port in self.ports}) != len(self.ports):
            raise ValueError("USB-C connector references must be unique")
        cc_nets = [net for port in self.ports for net in (port.cc1.net, port.cc2.net)]
        if len(set(cc_nets)) != len(cc_nets):
            raise ValueError("USB-C CC nets must be unique across configured ports")
        return self
