"""Source-bound schematic connectivity snapshots and review deltas."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    RepositoryPath,
    StrictModel,
)


class NetlistPinConnectivityState(StrictModel):
    """One pin's native net assignment and the other pins on that net."""

    net: NetName | None = None
    peers: tuple[Reference, ...] = ()

    @model_validator(mode="after")
    def peers_are_canonical(self) -> NetlistPinConnectivityState:
        if self.net is None and self.peers:
            raise ValueError("An unassigned pin cannot have connected peers")
        if tuple(sorted(set(self.peers))) != self.peers:
            raise ValueError("Pin peers must be unique and sorted")
        return self


class DesignLintConnectivitySnapshot(StrictModel):
    """Native, project-bound pin-to-net state suitable for later comparison."""

    schema_version: Literal["1"] = "1"
    project_id: Identifier
    source_hashes: Mapping[RepositoryPath, Digest]
    netlist_sha256: Digest
    kicad_version: NonEmptyText
    toolchain_image: NonEmptyText
    coverage: Literal["COMPLETE", "PARTIAL"]
    pin_states: Mapping[Reference, NetlistPinConnectivityState] = Field(default_factory=dict)
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def snapshot_is_source_bound_and_consistent(self) -> DesignLintConnectivitySnapshot:
        if not self.source_hashes:
            raise ValueError("A connectivity snapshot needs source hashes")
        if self.coverage == "COMPLETE" and self.issue is not None:
            raise ValueError("A complete connectivity snapshot cannot have an issue")
        if self.coverage == "PARTIAL" and self.issue is None:
            raise ValueError("A partial connectivity snapshot must explain its evidence gap")
        for pin, state in self.pin_states.items():
            if pin in state.peers:
                raise ValueError("A pin cannot be its own connectivity peer")
            for peer in state.peers:
                peer_state = self.pin_states.get(peer)
                if peer_state is None or pin not in peer_state.peers or peer_state.net != state.net:
                    raise ValueError("Pin peer evidence must be symmetric on the same native net")
        return self


class DesignLintConnectivityChange(StrictModel):
    """A pin added, removed, or assigned to different native connectivity."""

    pin: Reference
    kind: Literal["PIN_ADDED", "PIN_REMOVED", "ASSIGNMENT_CHANGED"]
    baseline: NetlistPinConnectivityState | None = None
    current: NetlistPinConnectivityState | None = None

    @model_validator(mode="after")
    def changed_sides_match_kind(self) -> DesignLintConnectivityChange:
        if self.kind == "PIN_ADDED" and (self.baseline is not None or self.current is None):
            raise ValueError("An added pin must have only current connectivity evidence")
        if self.kind == "PIN_REMOVED" and (self.baseline is None or self.current is not None):
            raise ValueError("A removed pin must have only baseline connectivity evidence")
        if self.kind == "ASSIGNMENT_CHANGED" and (
            self.baseline is None or self.current is None or self.baseline == self.current
        ):
            raise ValueError("A connectivity change needs different states on both sides")
        return self
