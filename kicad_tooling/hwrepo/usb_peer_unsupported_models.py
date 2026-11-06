"""Typed coverage evidence for unsupported USB multi-pin data topologies."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    StrictModel,
    UsbDataPortGroup,
)


class UsbPeerUnsupportedMultiPinPathCoverage(StrictModel):
    """Observed endpoint nets sharing pins on one unmapped multi-pin component."""

    connector_reference: Identifier
    phy_reference: Identifier
    component_reference: Identifier
    component_symbol: NonEmptyText
    component_footprint: NonEmptyText
    component_pin_count: Annotated[int, Field(ge=3)]
    port_group: UsbDataPortGroup | None = None
    topology: Literal["split_endpoint_nets", "shared_data_net_attachment"] = "split_endpoint_nets"
    positive_connector_net: NetName
    positive_phy_net: NetName
    positive_connector_component_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    positive_phy_component_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    negative_connector_net: NetName
    negative_phy_net: NetName
    negative_connector_component_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]
    negative_phy_component_pins: Annotated[tuple[Reference, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def assignments_match_candidate(self) -> UsbPeerUnsupportedMultiPinPathCoverage:
        if (
            self.connector_reference.casefold() == self.phy_reference.casefold()
            or self.component_reference.casefold()
            in {self.connector_reference.casefold(), self.phy_reference.casefold()}
        ):
            raise ValueError("USB unsupported-path evidence must identify three distinct parts")
        positive_keys = {
            self.positive_connector_net.casefold(),
            self.positive_phy_net.casefold(),
        }
        negative_keys = {
            self.negative_connector_net.casefold(),
            self.negative_phy_net.casefold(),
        }
        if self.topology == "split_endpoint_nets":
            if (
                len(positive_keys) != 2
                or len(negative_keys) != 2
                or len(positive_keys | negative_keys) != 4
            ):
                raise ValueError("Split USB multi-pin candidates require four distinct data nets")
        elif len(positive_keys) != 1 or len(negative_keys) != 1 or positive_keys == negative_keys:
            raise ValueError("USB data-net attachments require one shared net per data line")
        pin_groups = (
            self.positive_connector_component_pins,
            self.positive_phy_component_pins,
            self.negative_connector_component_pins,
            self.negative_phy_component_pins,
        )
        folded_groups = tuple(tuple(pin.casefold() for pin in group) for group in pin_groups)
        if any(len(set(group)) != len(group) for group in folded_groups):
            raise ValueError("USB multi-pin component pin assignments must be unique")
        candidate_pin_groups = (
            (folded_groups[0], folded_groups[2])
            if self.topology == "shared_data_net_attachment"
            else folded_groups
        )
        if self.topology == "shared_data_net_attachment" and (
            folded_groups[0] != folded_groups[1] or folded_groups[2] != folded_groups[3]
        ):
            raise ValueError("USB data-net attachment pins must match each shared data line")
        all_pins = tuple(pin for group in candidate_pin_groups for pin in group)
        if len(set(all_pins)) != len(all_pins):
            raise ValueError("USB multi-pin data lines must use distinct component pins")
        if self.component_pin_count < len(all_pins):
            raise ValueError("USB multi-pin candidate inventory must contain its assigned pins")
        if any(
            tuple(sorted(group, key=lambda pin: (pin.casefold(), pin))) != group
            for group in pin_groups
        ):
            raise ValueError("USB multi-pin candidate pin assignments must be ordered")
        if any(
            pin.rsplit(".", 1)[0].casefold() != self.component_reference.casefold()
            for group in pin_groups
            for pin in group
        ):
            raise ValueError("USB multi-pin candidate assignments must belong to the component")
        if self.port_group is not None and not self.port_group.isdecimal():
            raise ValueError("USB multi-pin candidate port groups must be decimal numbers")
        return self
