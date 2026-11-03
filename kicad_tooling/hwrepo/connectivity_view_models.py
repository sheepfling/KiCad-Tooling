"""Bounded, source-linked one-hop netlist connectivity review."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import Digest, Identifier, NetName, Reference, RepositoryPath, StrictModel
from .netlist_membership import PinStatus


class ConnectivityPin(StrictModel):
    pin: Reference
    expected_net: NetName | None = None
    observed_nets: tuple[NetName, ...] = ()
    status: PinStatus


class AdjacentNet(StrictModel):
    net: NetName | None = None
    pins: tuple[Reference, ...]
    state: Literal["CONNECTED", "UNCONNECTED"]


class ComponentNeighborhood(StrictModel):
    reference: Identifier
    selected_pins: tuple[Reference, ...]
    other_nets: tuple[AdjacentNet, ...]
    observed_symbol: str | None = None
    observed_footprint: str | None = None
    dnp: bool = False


class ConnectivityViewReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["NET_CONNECTIVITY_VIEW"] = "NET_CONNECTIVITY_VIEW"
    build_authorized: Literal[False] = False
    physical_continuity_assessed: Literal[False] = False
    project_id: Identifier
    net: NetName
    authored_roles: tuple[str, ...] = ()
    source_receipt: RepositoryPath
    source_report_sha256: Digest
    requirements_sha256: Digest
    observed_sha256: Digest | None = None
    native_netlist_sha256: Digest | None = None
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    source_status: Literal["CURRENT", "STALE", "UNKNOWN", "UNAVAILABLE"]
    observation_status: Literal["RETAINED", "UNREVIEWED"]
    pins: tuple[ConnectivityPin, ...]
    components: tuple[ComponentNeighborhood, ...]
    issues: tuple[str, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
