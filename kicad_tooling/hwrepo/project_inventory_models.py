"""Read-only project inventory and MCP project-detail contracts."""

from __future__ import annotations

from typing import Literal

from .model_primitives import Identifier, NonEmptyText, RepositoryPath, StrictModel
from .policy_issue_models import PolicyIssue
from .project_models import ProjectKind, ProjectManifest, ProjectTestContract


class ProjectDetailRequest(StrictModel):
    """Select one registered project's manifest and authored check contract."""

    project_id: str


class InventoryProject(StrictModel):
    """Declared island and whether its authored inputs are present for a check."""

    id: Identifier
    kind: ProjectKind
    status: Literal["training_fixture", "engineering", "release_candidate"]
    assurance_profile: Literal["training", "development", "production"]
    manifest: RepositoryPath
    project: RepositoryPath
    toolchain_id: Identifier
    tags: tuple[Identifier, ...]
    products: tuple[Identifier, ...]
    readiness: Literal["INPUTS_PRESENT", "NEEDS_INPUTS"]
    missing_inputs: tuple[RepositoryPath, ...] = ()
    next_command: NonEmptyText


class McpProjectReport(StrictModel):
    """One project's declared inputs; inspection never authorizes manufacturing."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    project: InventoryProject
    manifest: ProjectManifest
    contract: ProjectTestContract | None


class InventoryGroup(StrictModel):
    """One product or tag and its selected project IDs."""

    id: Identifier
    project_ids: tuple[Identifier, ...]


class InventoryToolchain(StrictModel):
    id: Identifier
    kicad_version: NonEmptyText


class TemplateInventoryReport(StrictModel):
    """Read-only discovery; input presence is not validation or release approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["TEMPLATE_INVENTORY"] = "TEMPLATE_INVENTORY"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    projects: tuple[InventoryProject, ...] = ()
    products: tuple[InventoryGroup, ...] = ()
    tags: tuple[InventoryGroup, ...] = ()
    toolchains: tuple[InventoryToolchain, ...] = ()
    issues: tuple[PolicyIssue, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()
