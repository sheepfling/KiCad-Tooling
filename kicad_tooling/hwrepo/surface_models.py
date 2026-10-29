"""Typed CLI and MCP capability inventories and parity reports."""

from __future__ import annotations

from typing import Literal

from .model_primitives import Identifier, NonEmptyText, StrictModel
from .policy_issue_models import PolicyIssue

SurfaceAlignment = Literal["aligned", "partial", "cli_only", "mcp_only"]


class ToolCliSnapshot(StrictModel):
    module: NonEmptyText
    commands: tuple[NonEmptyText, ...] = ()
    options: tuple[NonEmptyText, ...] = ()


class ToolMcpSnapshot(StrictModel):
    name: Identifier
    parameters: tuple[Identifier, ...] = ()


class ToolSurfaceMapping(StrictModel):
    id: Identifier
    cli: tuple[NonEmptyText, ...] = ()
    mcp: tuple[Identifier, ...] = ()
    alignment: SurfaceAlignment
    reason: NonEmptyText
    scope: Literal["core", "administration", "adapter"]
    gaps: tuple[NonEmptyText, ...] = ()
    constraints: tuple[NonEmptyText, ...] = ()
    exception: NonEmptyText | None = None
    parity_tests: tuple[NonEmptyText, ...] = ()


class ToolSurfacesCatalog(StrictModel):
    schema_version: Literal["2"] = "2"
    cli: tuple[ToolCliSnapshot, ...]
    mcp: tuple[ToolMcpSnapshot, ...]
    capabilities: tuple[ToolSurfaceMapping, ...]


class ToolSurfaceReport(StrictModel):
    schema_version: Literal["2"] = "2"
    build_authorized: Literal[False] = False
    status: Literal["PASS", "FAIL"]
    coverage_status: Literal["PASS", "FAIL"]
    parity_status: Literal["PASS", "FAIL"]
    behavior_verification: Literal["NOT_RUN"] = "NOT_RUN"
    mcp_verification: Literal["LIVE", "STATIC_ONLY", "UNAVAILABLE"]
    cli: tuple[ToolCliSnapshot, ...]
    mcp: tuple[ToolMcpSnapshot, ...]
    capabilities: tuple[ToolSurfaceMapping, ...]
    issues: tuple[PolicyIssue, ...] = ()
    notes: tuple[NonEmptyText, ...] = ()
