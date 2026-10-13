"""Project-authored USB SuperSpeed endpoint and reference-domain requirements."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel
from .reference_bond_models import ReferenceBondRequirement
from .usb_reference_pin_models import UsbReferencePinRequirement


class UsbSuperspeedReferencePathRequirement(StrictModel):
    """Exact direct USB SuperSpeed P/N path plus its reviewed reference policy."""

    id: Identifier
    basis: NonEmptyText
    connector_reference: Identifier
    expected_connector_symbol: NonEmptyText
    expected_connector_footprint: NonEmptyText
    phy_reference: Identifier
    expected_phy_symbol: NonEmptyText
    expected_phy_footprint: NonEmptyText
    connector_signal_family: Literal["USB SuperSpeed TX", "USB SuperSpeed RX"]
    phy_signal_family: Literal["USB SuperSpeed TX", "USB SuperSpeed RX"]
    connector_positive_pin: Reference
    phy_positive_pin: Reference
    positive_net: NetName
    connector_negative_pin: Reference
    phy_negative_pin: Reference
    negative_net: NetName
    connector_reference_pins: Annotated[tuple[UsbReferencePinRequirement, ...], Field(min_length=1)]
    phy_reference_pins: Annotated[tuple[UsbReferencePinRequirement, ...], Field(min_length=1)]
    reference_policy: Literal["common_net", "separate_nets", "bonded"]
    reference_bond: ReferenceBondRequirement | None = None

    @model_validator(mode="after")
    def complete_endpoint_and_reference_map(self) -> UsbSuperspeedReferencePathRequirement:
        if self.connector_reference.casefold() == self.phy_reference.casefold():
            raise ValueError("USB connector and PHY references must differ")
        if (self.connector_signal_family, self.phy_signal_family) not in {
            ("USB SuperSpeed TX", "USB SuperSpeed RX"),
            ("USB SuperSpeed RX", "USB SuperSpeed TX"),
        }:
            raise ValueError("USB SuperSpeed peer maps must join opposite TX/RX families")

        endpoint_pins = (
            (self.connector_positive_pin, self.connector_reference),
            (self.connector_negative_pin, self.connector_reference),
            (self.phy_positive_pin, self.phy_reference),
            (self.phy_negative_pin, self.phy_reference),
        )
        for pin, reference in endpoint_pins:
            if "." not in pin or pin.rsplit(".", 1)[0].casefold() != reference.casefold():
                raise ValueError("USB SuperSpeed data pins must belong to their mapped endpoint")
        if (
            len(
                {
                    self.connector_positive_pin.casefold(),
                    self.connector_negative_pin.casefold(),
                    self.phy_positive_pin.casefold(),
                    self.phy_negative_pin.casefold(),
                }
            )
            != 4
        ):
            raise ValueError("USB SuperSpeed positive and negative pins must be distinct")
        if self.positive_net.casefold() == self.negative_net.casefold():
            raise ValueError("USB SuperSpeed positive and negative paths need distinct nets")

        for item, endpoint in (
            *((item, self.connector_reference) for item in self.connector_reference_pins),
            *((item, self.phy_reference) for item in self.phy_reference_pins),
        ):
            if item.pin.rsplit(".", 1)[0].casefold() != endpoint.casefold():
                raise ValueError("USB reference pins must belong to their declared endpoint")
        connector_reference_pin_ids = tuple(
            item.pin.casefold() for item in self.connector_reference_pins
        )
        phy_reference_pin_ids = tuple(item.pin.casefold() for item in self.phy_reference_pins)
        if len(set(connector_reference_pin_ids)) != len(connector_reference_pin_ids):
            raise ValueError("USB connector reference-pin requirements must be unique")
        if len(set(phy_reference_pin_ids)) != len(phy_reference_pin_ids):
            raise ValueError("USB PHY reference-pin requirements must be unique")
        if set(connector_reference_pin_ids) & set(phy_reference_pin_ids):
            raise ValueError("USB endpoint reference pins must be distinct")
        if (set(connector_reference_pin_ids) | set(phy_reference_pin_ids)) & {
            self.connector_positive_pin.casefold(),
            self.connector_negative_pin.casefold(),
            self.phy_positive_pin.casefold(),
            self.phy_negative_pin.casefold(),
        }:
            raise ValueError("USB SuperSpeed data and reference pins must be distinct")

        connector_nets = {item.net.casefold() for item in self.connector_reference_pins}
        phy_nets = {item.net.casefold() for item in self.phy_reference_pins}
        if len(connector_nets) != 1 or len(phy_nets) != 1:
            raise ValueError("Each USB SuperSpeed endpoint must use one mapped reference net")
        if self.reference_policy == "common_net":
            if connector_nets != phy_nets:
                raise ValueError("common_net USB reference pins must share one declared net")
            if self.reference_bond is not None:
                raise ValueError("common_net USB reference policy cannot declare a bond")
        elif self.reference_policy == "separate_nets":
            if connector_nets == phy_nets:
                raise ValueError("separate_nets USB reference policy needs distinct nets")
            if self.reference_bond is not None:
                raise ValueError("separate_nets USB reference policy cannot declare a bond")
        else:
            if connector_nets == phy_nets:
                raise ValueError("bonded USB reference policy needs distinct endpoint nets")
            if self.reference_bond is None:
                raise ValueError("bonded USB reference policy needs one exact bond component")
            if {
                self.reference_bond.side_a_net.casefold(),
                self.reference_bond.side_b_net.casefold(),
            } != connector_nets | phy_nets:
                raise ValueError("USB reference bond must join the mapped endpoint nets")
            if self.reference_bond.reference.casefold() in {
                self.connector_reference.casefold(),
                self.phy_reference.casefold(),
            }:
                raise ValueError("USB reference bond cannot reuse an endpoint reference")
        return self
