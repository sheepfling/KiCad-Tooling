"""Typed project requirements for source-bound PCB return-path checks."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .model_primitives import Identifier, NetName, NonEmptyText, Reference, StrictModel


class PcbReturnEndpointRequirement(StrictModel):
    """One exact PCB pad and its independently reviewed expected net/footprint."""

    pad: Reference
    net: NetName
    footprint: NonEmptyText

    @model_validator(mode="after")
    def exact_pad_reference(self) -> PcbReturnEndpointRequirement:
        if self.pad.count(".") != 1:
            raise ValueError("PCB return endpoints must use an exact reference.pad number")
        if self.net.startswith("/"):
            raise ValueError("Use the native net name without a leading slash")
        return self


class PcbReturnBondRequirement(StrictModel):
    """One reviewed, fitted KiCad net-tie footprint and its exact bridge groups."""

    reference: Identifier
    footprint: NonEmptyText
    pad_groups: Annotated[tuple[tuple[Reference, ...], ...], Field(min_length=1)]

    @model_validator(mode="after")
    def exact_bridge_groups(self) -> PcbReturnBondRequirement:
        if not self.pad_groups or any(len(group) < 2 for group in self.pad_groups):
            raise ValueError("Each declared PCB return bond group needs at least two exact pads")
        pads = [pad for group in self.pad_groups for pad in group]
        if any(pad.count(".") != 1 for pad in pads):
            raise ValueError("PCB return bond groups must use exact reference.pad numbers")
        if len({pad.casefold() for pad in pads}) != len(pads):
            raise ValueError("PCB return bond pads must occur in exactly one declared group")
        prefix = f"{self.reference}.".casefold()
        if any(not pad.casefold().startswith(prefix) for pad in pads):
            raise ValueError("PCB return bond pads must belong to the declared component")
        return self


class PcbReturnDomainRequirement(StrictModel):
    """A required physical return domain; separate domains declare isolation."""

    id: Identifier
    basis: NonEmptyText
    topology: Literal["direct", "bonded"]
    endpoints: Annotated[tuple[PcbReturnEndpointRequirement, ...], Field(min_length=2)]
    bonds: tuple[PcbReturnBondRequirement, ...] = ()

    @model_validator(mode="after")
    def valid_return_topology(self) -> PcbReturnDomainRequirement:
        pads = [item.pad.casefold() for item in self.endpoints]
        if len(set(pads)) != len(pads):
            raise ValueError("PCB return domain endpoints must be unique")
        if len({item.reference.casefold() for item in self.bonds}) != len(self.bonds):
            raise ValueError("PCB return bond component references must be unique")
        if self.topology == "direct":
            if self.bonds:
                raise ValueError("Direct PCB return domains cannot declare net-tie bonds")
            if len({item.net.casefold() for item in self.endpoints}) != 1:
                raise ValueError("Direct PCB return endpoints must declare one common net")
        else:
            if not self.bonds:
                raise ValueError("Bonded PCB return domains must declare exact net-tie groups")
            if len({item.net.casefold() for item in self.endpoints}) < 2:
                raise ValueError(
                    "Bonded PCB return domains must declare at least two distinct nets"
                )
        return self


class PcbReturnPathsAnalysis(StrictModel):
    """Source-bound PCB copper connectivity requirements for reviewed returns."""

    mode: Literal["required"] = "required"
    basis: NonEmptyText
    domains: Annotated[tuple[PcbReturnDomainRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_domains_and_endpoints(self) -> PcbReturnPathsAnalysis:
        if len({domain.id.casefold() for domain in self.domains}) != len(self.domains):
            raise ValueError("PCB return domain IDs must be unique")
        pads = [item.pad.casefold() for domain in self.domains for item in domain.endpoints]
        bonds = [bond.reference.casefold() for domain in self.domains for bond in domain.bonds]
        if len(set(pads)) != len(pads):
            raise ValueError("PCB return endpoint pads must belong to one domain only")
        if len(set(bonds)) != len(bonds):
            raise ValueError("PCB return bond components must belong to one domain only")
        return self
