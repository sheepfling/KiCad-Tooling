"""Project-authored serial peer topology requirements."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel
from .reference_bond_models import ReferenceBondRequirement
from .serial_logic_models import SerialLogicLimits, SerialPinNetRequirement


class SerialEndpointRequirement(StrictModel):
    id: Identifier
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    logic_domain: Identifier
    tx: SerialPinNetRequirement
    rx: SerialPinNetRequirement
    reference_pins: tuple[SerialPinNetRequirement, ...] = ()
    logic_limits: SerialLogicLimits | None = None

    @model_validator(mode="after")
    def endpoint_pin_ownership_and_roles(self) -> SerialEndpointRequirement:
        assignments = (self.tx, self.rx, *self.reference_pins)
        if any(
            item.pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for item in assignments
        ):
            raise ValueError("Serial endpoint pins must belong to the declared component")
        pins = [item.pin.casefold() for item in assignments]
        if len(set(pins)) != len(pins):
            raise ValueError("Serial TX, RX, and reference pins must be distinct")
        if self.tx.net == self.rx.net:
            raise ValueError("Serial TX and RX must use distinct signal nets")
        return self


class SerialBridgePathRequirement(StrictModel):
    direction: Literal["a_tx_to_b_rx", "b_tx_to_a_rx"]
    from_pin: Reference
    from_net: NetName
    to_pin: Reference
    to_net: NetName

    @model_validator(mode="after")
    def distinct_path_ends(self) -> SerialBridgePathRequirement:
        if "." not in self.from_pin or "." not in self.to_pin:
            raise ValueError("Serial bridge pins must use COMPONENT.PIN form")
        if self.from_pin == self.to_pin or self.from_net == self.to_net:
            raise ValueError("Serial bridge paths need distinct pins and distinct nets")
        return self


class SerialBridgeRequirement(StrictModel):
    reference: Identifier
    symbol: NonEmptyText
    footprint: NonEmptyText
    paths: Annotated[tuple[SerialBridgePathRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def bridge_pin_ownership(self) -> SerialBridgeRequirement:
        if any(
            pin.rsplit(".", 1)[0].casefold() != self.reference.casefold()
            for path in self.paths
            for pin in (path.from_pin, path.to_pin)
        ):
            raise ValueError("Serial bridge pins must belong to the declared bridge component")
        pins = [pin.casefold() for path in self.paths for pin in (path.from_pin, path.to_pin)]
        if len(set(pins)) != len(pins):
            raise ValueError("Each serial bridge pin must belong to exactly one declared path")
        assignments = [
            (pin.casefold(), net)
            for path in self.paths
            for pin, net in ((path.from_pin, path.from_net), (path.to_pin, path.to_net))
        ]
        pin_nets: dict[str, str] = {}
        for pin, net in assignments:
            if pin in pin_nets and pin_nets[pin] != net:
                raise ValueError("A serial bridge pin cannot map to multiple nets")
            pin_nets[pin] = net
        return self


class SerialDirectPeerRequirement(StrictModel):
    mode: Literal["direct"]
    endpoint: SerialEndpointRequirement


class SerialShiftedPeerRequirement(StrictModel):
    mode: Literal["level_shifted"]
    endpoint: SerialEndpointRequirement
    bridges: Annotated[tuple[SerialBridgeRequirement, ...], Field(min_length=1)]


class SerialExternalPeerRequirement(StrictModel):
    mode: Literal["external"]
    reason: NonEmptyText


SerialPeerRequirement = Annotated[
    SerialDirectPeerRequirement | SerialShiftedPeerRequirement | SerialExternalPeerRequirement,
    Field(discriminator="mode"),
]


class SerialPeerLinkRequirement(StrictModel):
    id: Identifier
    basis: NonEmptyText
    endpoint: SerialEndpointRequirement
    peer: SerialPeerRequirement
    reference_policy: Literal[
        "common_net", "bonded", "separate_nets", "external_unverified", "not_applicable"
    ]
    reference_bond: ReferenceBondRequirement | None = None

    @model_validator(mode="after")
    def compatible_peer_map(self) -> SerialPeerLinkRequirement:
        peer = self.peer
        if isinstance(peer, SerialExternalPeerRequirement):
            if self.reference_policy not in {"external_unverified", "not_applicable"}:
                raise ValueError(
                    "An external serial peer needs external_unverified or not_applicable reference policy"
                )
            if self.reference_policy == "not_applicable" and self.endpoint.reference_pins:
                raise ValueError(
                    "not_applicable reference policy cannot declare endpoint reference pins"
                )
            if self.reference_bond is not None:
                raise ValueError("External serial peers cannot declare an on-board reference bond")
            return self

        remote = peer.endpoint
        if self.endpoint.reference.casefold() == remote.reference.casefold():
            raise ValueError("Serial peer endpoints must be distinct components")
        bridge_refs = (
            tuple(item.reference.casefold() for item in peer.bridges)
            if isinstance(peer, SerialShiftedPeerRequirement)
            else ()
        )
        if len(set(bridge_refs)) != len(bridge_refs):
            raise ValueError("Serial bridge component references must be unique")
        if {self.endpoint.reference.casefold(), remote.reference.casefold()} & set(bridge_refs):
            raise ValueError("Serial endpoint and bridge components must be distinct")
        if self.reference_bond is not None and self.reference_bond.reference.casefold() in {
            self.endpoint.reference.casefold(),
            remote.reference.casefold(),
            *bridge_refs,
        }:
            raise ValueError("Serial reference bond cannot reuse an endpoint or bridge component")

        if isinstance(peer, SerialDirectPeerRequirement):
            if self.endpoint.tx.net != remote.rx.net or self.endpoint.rx.net != remote.tx.net:
                raise ValueError("Direct serial peer maps must cross TX to RX in both directions")
            if self.endpoint.logic_domain != remote.logic_domain:
                raise ValueError(
                    "Direct serial peer endpoints must declare the same logic voltage domain"
                )
        else:
            if self.endpoint.logic_domain == remote.logic_domain:
                raise ValueError(
                    "Level-shifted serial peers must declare different logic voltage domains"
                )
            if not self._has_route(peer, "a_tx_to_b_rx", self.endpoint.tx.net, remote.rx.net):
                raise ValueError("Serial shifted peer map has no A TX to B RX path")
            if not self._has_route(peer, "b_tx_to_a_rx", remote.tx.net, self.endpoint.rx.net):
                raise ValueError("Serial shifted peer map has no B TX to A RX path")

        left_references = {item.net for item in self.endpoint.reference_pins}
        right_references = {item.net for item in remote.reference_pins}
        if self.reference_policy == "common_net":
            if not left_references or not right_references:
                raise ValueError("common_net serial reference policy needs pins on both endpoints")
            if len(left_references) != 1 or left_references != right_references:
                raise ValueError("common_net serial reference pins must share one declared net")
            if self.reference_bond is not None:
                raise ValueError("common_net serial reference policy cannot declare a bond")
        elif self.reference_policy == "separate_nets":
            if not left_references or not right_references:
                raise ValueError(
                    "separate_nets serial reference policy needs pins on both endpoints"
                )
            if len(left_references) != 1 or len(right_references) != 1:
                raise ValueError("Each serial endpoint must use one declared reference net")
            if left_references == right_references:
                raise ValueError("separate_nets serial reference policy needs distinct nets")
            if self.reference_bond is not None:
                raise ValueError("separate_nets serial reference policy cannot declare a bond")
        elif self.reference_policy == "bonded":
            if not left_references or not right_references:
                raise ValueError("bonded serial reference policy needs pins on both endpoints")
            if len(left_references) != 1 or len(right_references) != 1:
                raise ValueError("Each bonded serial endpoint must use one declared reference net")
            if left_references == right_references:
                raise ValueError("bonded serial reference policy needs distinct nets")
            if self.reference_bond is None:
                raise ValueError("bonded serial reference policy needs one exact bond component")
            if {
                self.reference_bond.side_a_net.casefold(),
                self.reference_bond.side_b_net.casefold(),
            } != {net.casefold() for net in left_references | right_references}:
                raise ValueError("Serial reference bond must join the two mapped endpoint nets")
        elif self.reference_bond is not None:
            raise ValueError("Serial reference bond requires the bonded reference policy")
        elif self.reference_policy == "not_applicable":
            if self.endpoint.reference_pins or remote.reference_pins:
                raise ValueError(
                    "not_applicable serial reference policy cannot declare reference pins"
                )
        elif self.reference_policy == "external_unverified":
            raise ValueError("external_unverified reference policy only applies to external peers")
        return self

    @staticmethod
    def _has_route(
        peer: SerialShiftedPeerRequirement,
        direction: Literal["a_tx_to_b_rx", "b_tx_to_a_rx"],
        source: str,
        destination: str,
    ) -> bool:
        if source == destination:
            return False
        graph: dict[str, set[str]] = {}
        for bridge in peer.bridges:
            for path in bridge.paths:
                if path.direction == direction:
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


class SerialPeerAnalysis(StrictModel):
    mode: Literal["required"] = "required"
    basis: NonEmptyText
    links: Annotated[tuple[SerialPeerLinkRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_link_ids(self) -> SerialPeerAnalysis:
        if len({link.id.casefold() for link in self.links}) != len(self.links):
            raise ValueError("Serial peer link IDs must be unique")
        return self
