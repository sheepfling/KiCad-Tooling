"""Non-authorizing authored-versus-observed netlist review records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .command_evidence_models import CommandEvidence
from .connector_peer_pin_models import SimilarConnectorPinGroup
from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel
from .netlist_contract_models import NetlistContract
from .project_models import ProjectKind
from .return_net_models import ReturnNetGroup


class ContractDifference(StrictModel):
    kind: Literal["component", "net"]
    identifier: NonEmptyText
    difference: Literal["observed_only", "authored_only", "different"]


class ContractCoachReport(StrictModel):
    """Observed netlist inventory for human contract review, never an approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["CONTRACT_COACH"] = "CONTRACT_COACH"
    status: Literal["READY_FOR_REVIEW", "BLOCKED"]
    project_id: Identifier
    project_kind: ProjectKind | None = None
    review_state: Literal["UNREVIEWED"] = "UNREVIEWED"
    electrical_coverage: Literal[False] = False
    build_authorized: Literal[False] = False
    selected_runner: Literal["local", "container"] | None = None
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    netlist_sha256: Digest | None = None
    native_summary: str | None = None
    native_status: Literal["PASS", "FAIL"] | None = None
    observed: NetlistContract | None = None
    authored: NetlistContract | None = None
    differences: tuple[ContractDifference, ...] = ()
    return_net_groups: tuple[ReturnNetGroup, ...] = ()
    similar_connector_pin_groups: tuple[SimilarConnectorPinGroup, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()
    commands: Mapping[Identifier, CommandEvidence] = Field(default_factory=dict)
    receipt_dir: str | None = None
