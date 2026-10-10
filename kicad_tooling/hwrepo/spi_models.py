"""Project-authored SPI roster and topology requirements."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class SpiPinNetRequirement(StrictModel):
    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("SPI pin mappings must use COMPONENT.PIN form")
        return value


class SpiPinUnconnectedRequirement(StrictModel):
    mode: Literal["unconnected"] = "unconnected"
    pin: Reference

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("SPI pin mappings must use COMPONENT.PIN form")
        return value


class SpiMisoConnectedRequirement(StrictModel):
    mode: Literal["connected"]
    pin: Reference
    net: NetName

    @field_validator("pin")
    @classmethod
    def pin_is_qualified(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("SPI pin mappings must use COMPONENT.PIN form")
        return value


class SpiPinNotPresent(StrictModel):
    mode: Literal["not_present"]
    reason: NonEmptyText


SpiMisoRequirement = Annotated[
    SpiMisoConnectedRequirement | SpiPinUnconnectedRequirement | SpiPinNotPresent,
    Field(discriminator="mode"),
]


class SpiControllerRequirement(StrictModel):
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    sck: SpiPinNetRequirement
    mosi: SpiPinNetRequirement
    miso: SpiMisoRequirement
    chip_selects: Annotated[tuple[SpiPinNetRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def controller_pin_ownership_and_selects(self) -> SpiControllerRequirement:
        signals: tuple[
            SpiPinNetRequirement | SpiMisoConnectedRequirement | SpiPinUnconnectedRequirement,
            ...,
        ] = (
            self.sck,
            self.mosi,
            *((self.miso,) if not isinstance(self.miso, SpiPinNotPresent) else ()),
            *self.chip_selects,
        )
        if any(
            requirement.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for requirement in signals
        ):
            raise ValueError("SPI controller pins must belong to the declared controller")
        pins = [item.pin.casefold() for item in signals]
        if len(set(pins)) != len(pins):
            raise ValueError("SPI controller signal and chip-select pins must be unique")
        select_nets = [item.net for item in self.chip_selects]
        if len(set(select_nets)) != len(select_nets):
            raise ValueError("SPI controller chip-select nets must be unique")
        data_nets = [self.sck.net, self.mosi.net]
        if isinstance(self.miso, SpiMisoConnectedRequirement):
            data_nets.append(self.miso.net)
        if len(set(data_nets)) != len(data_nets):
            raise ValueError("SPI clock and connected data nets must be distinct")
        if set(data_nets) & set(select_nets):
            raise ValueError("SPI chip-select nets must be separate from clock and data nets")
        return self


class SpiDeviceRequirement(StrictModel):
    id: Identifier
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    sck: SpiPinNetRequirement
    mosi: SpiPinNetRequirement
    miso: SpiMisoRequirement
    chip_select: SpiPinNetRequirement
    shared_select_group: Identifier | None = None

    @model_validator(mode="after")
    def device_pin_ownership_and_uniqueness(self) -> SpiDeviceRequirement:
        signals: tuple[
            SpiPinNetRequirement | SpiMisoConnectedRequirement | SpiPinUnconnectedRequirement,
            ...,
        ] = (
            self.sck,
            self.mosi,
            *((self.miso,) if not isinstance(self.miso, SpiPinNotPresent) else ()),
            self.chip_select,
        )
        if any(
            requirement.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for requirement in signals
        ):
            raise ValueError("SPI device pins must belong to the declared device")
        if len({item.pin.casefold() for item in signals}) != len(signals):
            raise ValueError("SPI device signal and chip-select pins must be unique")
        return self


class SpiBridgePathRequirement(StrictModel):
    signal: Literal["sck", "mosi", "miso"]
    from_pin: Reference
    from_net: NetName
    to_pin: Reference
    to_net: NetName

    @model_validator(mode="after")
    def distinct_path_ends(self) -> SpiBridgePathRequirement:
        if "." not in self.from_pin or "." not in self.to_pin:
            raise ValueError("SPI bridge pins must use COMPONENT.PIN form")
        if self.from_pin == self.to_pin or self.from_net == self.to_net:
            raise ValueError("SPI bridge paths need distinct pins and distinct nets")
        return self


class SpiBridgeRequirement(StrictModel):
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    paths: Annotated[tuple[SpiBridgePathRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def bridge_pins_belong_to_component(self) -> SpiBridgeRequirement:
        if any(
            pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for path in self.paths
            for pin in (path.from_pin, path.to_pin)
        ):
            raise ValueError("SPI bridge pins must belong to the declared bridge component")
        assignments = [
            (pin.casefold(), net)
            for path in self.paths
            for pin, net in ((path.from_pin, path.from_net), (path.to_pin, path.to_net))
        ]
        pin_nets: dict[str, str] = {}
        for pin, net in assignments:
            if pin in pin_nets and pin_nets[pin] != net:
                raise ValueError("An SPI bridge pin cannot map to multiple nets")
            pin_nets[pin] = net
        return self


class SpiBusRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    controller: SpiControllerRequirement
    devices: Annotated[tuple[SpiDeviceRequirement, ...], Field(min_length=1)]
    bridges: tuple[SpiBridgeRequirement, ...] = ()

    @model_validator(mode="after")
    def valid_bus_membership(self) -> SpiBusRequirement:
        device_ids = [item.id for item in self.devices]
        device_references = [item.reference.casefold() for item in self.devices]
        bridge_references = [item.reference.casefold() for item in self.bridges]
        if len(set(device_ids)) != len(device_ids):
            raise ValueError("SPI device IDs must be unique within a bus")
        if len(set(device_references)) != len(device_references):
            raise ValueError("An SPI device reference can appear only once per bus")
        if self.controller.reference.casefold() in {*device_references, *bridge_references}:
            raise ValueError("SPI controller, devices, and bridges must be distinct components")
        if len(set(bridge_references)) != len(bridge_references):
            raise ValueError("SPI bridge component references must be unique within a bus")
        if set(device_references) & set(bridge_references):
            raise ValueError("SPI devices and bridges must be distinct components")

        controller_nets = {self.controller.sck.net, self.controller.mosi.net}
        controller_miso = self.controller.miso
        if isinstance(controller_miso, SpiMisoConnectedRequirement):
            controller_nets.add(controller_miso.net)
        select_nets = {item.net for item in self.controller.chip_selects}
        if controller_nets & select_nets:
            raise ValueError("SPI chip-select nets must be separate from clock and data nets")

        device_selects: dict[str, list[SpiDeviceRequirement]] = {}
        for device in self.devices:
            device_selects.setdefault(device.chip_select.net, []).append(device)
            if device.chip_select.net not in select_nets:
                raise ValueError(
                    f"SPI device {device.id} chip-select net has no declared controller pin"
                )
            device_data_nets = {device.sck.net, device.mosi.net}
            if isinstance(device.miso, SpiMisoConnectedRequirement):
                device_data_nets.add(device.miso.net)
            if device.chip_select.net in device_data_nets:
                raise ValueError(
                    f"SPI device {device.id} chip-select must be separate from data nets"
                )
            if device_data_nets & select_nets:
                raise ValueError(
                    f"SPI device {device.id} data nets overlap a controller chip-select net"
                )
            if device.sck.net != self.controller.sck.net and not self._has_route(
                "sck", self.controller.sck.net, device.sck.net
            ):
                raise ValueError(
                    f"SPI device {device.id} SCK has no declared path to the controller"
                )
            if device.mosi.net != self.controller.mosi.net and not self._has_route(
                "mosi", self.controller.mosi.net, device.mosi.net
            ):
                raise ValueError(
                    f"SPI device {device.id} MOSI has no declared path to the controller"
                )
            if isinstance(device.miso, SpiMisoConnectedRequirement):
                if not isinstance(controller_miso, SpiMisoConnectedRequirement):
                    raise ValueError(  # noqa: TRY004 - malformed contract relationship
                        f"SPI device {device.id} has MISO but the controller MISO is not connected"
                    )
                if device.miso.net != controller_miso.net and not self._has_route(
                    "miso", controller_miso.net, device.miso.net
                ):
                    raise ValueError(
                        f"SPI device {device.id} MISO has no declared path to the controller"
                    )

        for net, devices in device_selects.items():
            if len(devices) == 1:
                if devices[0].shared_select_group is not None:
                    raise ValueError("An SPI shared-select group must name at least two devices")
                continue
            groups = {device.shared_select_group for device in devices}
            if len(groups) != 1 or None in groups:
                raise ValueError(
                    f"SPI chip-select net {net} is shared without one explicit shared-select group"
                )
        missing_membership = select_nets - set(device_selects)
        if missing_membership:
            raise ValueError(
                "Every declared SPI controller chip-select net must map to a device: "
                + ", ".join(sorted(missing_membership))
            )
        return self

    def _has_route(self, signal: str, source: str, destination: str) -> bool:
        graph: dict[str, set[str]] = {}
        for bridge in self.bridges:
            for path in bridge.paths:
                if path.signal == signal:
                    graph.setdefault(path.from_net, set()).add(path.to_net)
                    graph.setdefault(path.to_net, set()).add(path.from_net)
        pending = [source]
        reached: set[str] = set()
        while pending:
            net = pending.pop()
            if net == destination:
                return True
            if net in reached:
                continue
            reached.add(net)
            pending.extend(graph.get(net, ()))
        return False


class SpiAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    buses: Annotated[tuple[SpiBusRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_bus_ids(self) -> SpiAnalysis:
        if len({bus.id for bus in self.buses}) != len(self.buses):
            raise ValueError("SPI bus IDs must be unique")
        return self
