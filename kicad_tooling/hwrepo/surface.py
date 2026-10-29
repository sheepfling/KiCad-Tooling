"""Typed CLI/MCP coverage inventory and declaration drift checks.

AST and SDK schema handling are adapter boundaries: only validated snapshots
enter the catalog comparison. Discovery never executes CLI entry points or kicad_tooling.
"""

from __future__ import annotations

import ast
import asyncio
from collections.abc import MutableMapping, Sequence
from importlib.util import find_spec
from pathlib import Path
from typing import Literal

from pydantic import JsonValue

from .contracts import read_model, repo_path
from .policy_issue_models import PolicyIssue
from .surface_cli_discovery import discover_cli as _discover_cli
from .surface_mcp_discovery import discover_mcp as _discover_mcp
from .surface_models import (
    ToolCliSnapshot,
    ToolMcpSnapshot,
    ToolSurfaceMapping,
    ToolSurfaceReport,
    ToolSurfacesCatalog,
)

CATALOG = "kicad_tooling/tool-surfaces.json"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PACKAGE_ROOT.parent
# Core workflow requirements cannot be waived by reclassifying/deleting a catalog
# row. Changes to this acceptance scope need an explicit policy/code review.
CORE_WORKFLOWS = frozenset(
    {
        "project-inventory",
        "environment-doctor",
        "project-scaffold",
        "import-design",
        "scan-designs",
        "diagnose-designs",
        "rescue-project",
        "project-verification",
        "scope-checks",
        "native-scope-checks",
        "contract-coach",
        "design-lint",
        "model-coverage",
        "model-population",
        "three-d-export",
        "parts-preparation",
        "purchasing-preferences",
        "review-views",
        "native-release-export",
        "engineering-review",
        "release-readiness",
        "release-packaging",
        "package-verification",
        "package-restore",
        "change-impact",
        "supplier-snapshots",
        "foreign-board-conversion",
        "electrical-setup",
        "electrical-input-capture",
        "electrical-analysis",
        "electrical-scope-checks",
        "reviewed-part-selection",
        "paired-cad-import",
        "supplier-review-handoff",
        "electrical-chart-exports",
        "exact-cad-sourcing",
        "sourced-cad-import",
        "cad-step-alignment",
    }
)


def discover_cli(root: Path) -> tuple[ToolCliSnapshot, ...]:
    """Compatibility export for static first-party CLI declaration discovery."""
    return _discover_cli(root)


def discover_mcp(root: Path) -> tuple[ToolMcpSnapshot, ...]:
    """Compatibility export for static MCP declaration discovery."""
    return _discover_mcp(root)


async def _live_mcp(root: Path) -> tuple[ToolMcpSnapshot, ...]:
    # Keep the SDK optional for every base CLI import and static inventory run.
    from .mcp_server import create_server

    server = create_server(
        root,
        allow_checks=True,
        allow_writes=True,
        allow_edits=True,
        allow_exports=True,
        allow_downloads=True,
        allow_supplier_submissions=True,
    )
    snapshots: list[ToolMcpSnapshot] = []
    for tool in await server.list_tools():
        # input_schema is an SDK JSON boundary. Pydantic immediately validates the
        # extracted names, so framework dictionaries never reach comparison code.
        properties_value: JsonValue = tool.input_schema.get("properties", {})
        if not isinstance(properties_value, dict):
            raise TypeError(f"MCP tool {tool.name} has no object parameter schema")
        properties: dict[str, JsonValue] = properties_value
        snapshots.append(
            ToolMcpSnapshot.model_validate(
                {
                    "name": tool.name,
                    "parameters": tuple(properties),
                }
            )
        )
    return tuple(
        sorted(
            (
                item.model_copy(update={"parameters": tuple(sorted(item.parameters))})
                for item in snapshots
            ),
            key=lambda item: item.name,
        )
    )


def _cli_endpoints(snapshots: tuple[ToolCliSnapshot, ...]) -> set[str]:
    return {f"{item.module} {command}" for item in snapshots for command in item.commands} | {
        item.module for item in snapshots if not item.commands
    }


def _compare(
    actual_cli: tuple[ToolCliSnapshot, ...],
    actual_mcp: tuple[ToolMcpSnapshot, ...],
    catalog: ToolSurfacesCatalog,
) -> list[PolicyIssue]:
    issues: list[PolicyIssue] = []

    def issue(code: str, message: str) -> None:
        issues.append(PolicyIssue(code=code, location=CATALOG, message=message))

    expected_cli = {item.module: item for item in catalog.cli}
    expected_mcp = {item.name: item for item in catalog.mcp}
    if len(expected_cli) != len(catalog.cli) or len(expected_mcp) != len(catalog.mcp):
        issue("duplicate_snapshot", "Catalog contains duplicate CLI modules or MCP tool names")
    for label, actual, expected in (
        ("CLI", {item.module for item in actual_cli}, set(expected_cli)),
        ("MCP", {item.name for item in actual_mcp}, set(expected_mcp)),
    ):
        for name in sorted(actual - expected):
            issue("untracked_surface", f"Untracked {label} entry: {name}")
        for name in sorted(expected - actual):
            issue("stale_surface", f"Catalog {label} entry no longer exists: {name}")
    for cli in actual_cli:
        expected = expected_cli.get(cli.module)
        if expected is not None:
            for label, actual, declared in (
                ("commands", cli.commands, expected.commands),
                ("options", cli.options, expected.options),
            ):
                if set(actual) != set(declared):
                    issue(
                        "cli_signature_drift",
                        f"{cli.module} {label}: "
                        f"added {sorted(set(actual) - set(declared))}; "
                        f"removed {sorted(set(declared) - set(actual))}",
                    )
    for mcp in actual_mcp:
        expected = expected_mcp.get(mcp.name)
        if expected is not None and set(mcp.parameters) != set(expected.parameters):
            issue(
                "mcp_signature_drift",
                f"{mcp.name} parameters: "
                f"added {sorted(set(mcp.parameters) - set(expected.parameters))}; "
                f"removed {sorted(set(expected.parameters) - set(mcp.parameters))}",
            )
    cli_endpoints = _cli_endpoints(actual_cli)
    mcp_names = {item.name for item in actual_mcp}
    mapped_cli: set[str] = set()
    mapped_mcp: set[str] = set()
    ids: set[str] = set()
    for mapping in catalog.capabilities:
        if mapping.id in ids:
            issue("duplicate_mapping", f"Duplicate capability ID: {mapping.id}")
        ids.add(mapping.id)
        cli = set(mapping.cli)
        mcp = set(mapping.mcp)
        valid = (
            (mapping.alignment == "aligned" and cli and mcp and not mapping.gaps)
            or (mapping.alignment == "partial" and cli and mcp and mapping.gaps)
            or (mapping.alignment == "cli_only" and cli and not mcp)
            or (mapping.alignment == "mcp_only" and mcp and not cli)
        )
        if not valid:
            issue("invalid_alignment", f"{mapping.id}: alignment contradicts endpoints/gaps")
        for name in sorted(cli - cli_endpoints):
            issue("stale_mapping", f"{mapping.id}: unknown CLI endpoint {name}")
        for name in sorted(mcp - mcp_names):
            issue("stale_mapping", f"{mapping.id}: unknown MCP tool {name}")
        mapped_cli.update(cli)
        mapped_mcp.update(mcp)
    for name in sorted(cli_endpoints - mapped_cli):
        issue("unmapped_surface", f"CLI endpoint needs a capability classification: {name}")
    for name in sorted(mcp_names - mapped_mcp):
        issue("unmapped_surface", f"MCP tool needs a capability classification: {name}")
    if len(mcp_names) != len(actual_mcp):
        issue("duplicate_registration", "MCP source registers a tool name more than once")
    return issues


def _test_exists(
    root: Path,
    reference: str,
    *,
    ast_cache: MutableMapping[Path, ast.Module | None] | None = None,
) -> bool:
    """Resolve a pytest function or unittest method without importing tests."""
    parts = reference.split(".")
    if len(parts) < 3 or parts[0] != "tests" or not parts[-1].startswith("test_"):
        return False
    if any(not part.isidentifier() for part in parts):
        return False

    def read_tree(module_parts: Sequence[str]) -> ast.Module | None:
        path: Path | None = None
        try:
            path = repo_path(root, "/".join(module_parts) + ".py")
            if not path.is_file():
                return None
            if ast_cache is not None and path in ast_cache:
                return ast_cache[path]
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if ast_cache is not None:
                ast_cache[path] = tree
            return tree
        except (OSError, SyntaxError, ValueError):
            if ast_cache is not None and path is not None:
                ast_cache[path] = None
            return None

    if len(parts) >= 4:
        class_tree = read_tree(parts[:-2])
        if class_tree is not None and any(
            isinstance(node, ast.ClassDef)
            and node.name == parts[-2]
            and any(
                isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                and method.name == parts[-1]
                for method in node.body
            )
            for node in class_tree.body
        ):
            return True

    function_tree = read_tree(parts[:-1])
    return function_tree is not None and any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == parts[-1]
        for node in function_tree.body
    )


def parity_issues(
    root: Path | None, mappings: tuple[ToolSurfaceMapping, ...]
) -> tuple[PolicyIssue, ...]:
    """Check core policy, and resolve test references when package source is available."""
    issues: list[PolicyIssue] = []
    by_id = {mapping.id: mapping for mapping in mappings}
    test_ast_cache: dict[Path, ast.Module | None] = {}
    for identifier in sorted(CORE_WORKFLOWS):
        mapping = by_id.get(identifier)
        if mapping is None or mapping.scope != "core":
            issues.append(
                PolicyIssue(
                    code="core_scope",
                    location=CATALOG,
                    message=f"Required core workflow {identifier} cannot be removed or exempted",
                )
            )
    for mapping in mappings:
        location = f"{CATALOG}#{mapping.id}"
        if mapping.scope != "core":
            if mapping.exception is None:
                issues.append(
                    PolicyIssue(
                        code="missing_exception",
                        location=location,
                        message="Administrative/adapter differences need an explicit reason",
                    )
                )
            continue
        if (
            mapping.alignment != "aligned"
            or not mapping.cli
            or not mapping.mcp
            or mapping.gaps
            or mapping.exception is not None
        ):
            issues.append(
                PolicyIssue(
                    code="core_parity_gap",
                    location=location,
                    message=f"{mapping.id}: Core workflows need both surfaces and no functional gap or exception; "
                    "record permissions and path restrictions in constraints",
                )
            )
        if not mapping.parity_tests:
            issues.append(
                PolicyIssue(
                    code="missing_parity_tests",
                    location=location,
                    message="Core parity requires referenced behavioral regression tests",
                )
            )
        for reference in mapping.parity_tests:
            if root is not None and not _test_exists(root, reference, ast_cache=test_ast_cache):
                issues.append(
                    PolicyIssue(
                        code="missing_parity_test",
                        location=location,
                        message=f"Behavioral test does not exist: {reference}",
                    )
                )
    return tuple(issues)


def inspect_tool_surfaces(root: Path, *, require_live_mcp: bool = False) -> ToolSurfaceReport:
    """Check declared coverage and compare the optional live full MCP registration.

    PASS requires declaration coverage and the core parity policy. Developer source
    inspections also resolve behavioral test references. Installed wheels report those
    sources unavailable; neither mode executes tests or proves their result.
    """
    root = root.resolve()
    issues: list[PolicyIssue] = []
    cli: tuple[ToolCliSnapshot, ...] = ()
    mcp: tuple[ToolMcpSnapshot, ...] = ()
    catalog: ToolSurfacesCatalog | None = None
    verification: Literal["LIVE", "STATIC_ONLY", "UNAVAILABLE"] = "STATIC_ONLY"
    # The developer checkout owns behavioral tests. Installed wheels deliberately
    # exclude them; a consuming project's tests cannot satisfy package parity claims.
    test_root = SOURCE_ROOT if (SOURCE_ROOT / "pyproject.toml").is_file() else None
    notes = [
        "Core parity is required; administration and adapter exceptions stay explicit.",
        (
            "Behavioral tests were NOT_RUN here. This inspection checks declarations "
            "and core parity policy, not behavior or approval."
        ),
    ]
    if test_root is None:
        notes.append(
            "Behavioral test sources are NOT_AVAILABLE in this installed package; "
            "test references were not resolved. Run the tooling source checkout's "
            "acceptance suite with its external project fixture before a release."
        )
    else:
        notes.append(
            "Behavioral test references are resolved in the tooling source checkout; "
            "tests in the consuming project do not supply package parity evidence."
        )
    try:
        catalog = read_model(PACKAGE_ROOT / "tool-surfaces.json", ToolSurfacesCatalog)
        cli = discover_cli(SOURCE_ROOT)
        mcp = discover_mcp(SOURCE_ROOT)
        issues.extend(_compare(cli, mcp, catalog))
    except (OSError, TypeError, ValueError, SyntaxError) as exc:
        issues.append(PolicyIssue(code="surface_discovery", location=CATALOG, message=str(exc)))
    if find_spec("mcp") is None:
        notes.append("Optional MCP SDK is absent; registration was checked from source only.")
        if require_live_mcp:
            verification = "UNAVAILABLE"
            issues.append(
                PolicyIssue(
                    code="live_mcp_unavailable",
                    location="kicad_tooling/hwrepo/mcp_server.py",
                    message="Install the pinned dev or mcp extra to require live MCP verification.",
                )
            )
    else:
        try:
            live = asyncio.run(_live_mcp(root))
            verification = "LIVE"
            if live != mcp:
                issues.append(
                    PolicyIssue(
                        code="mcp_registration_drift",
                        location="kicad_tooling/hwrepo/mcp_server.py",
                        message="Actual full-server names/parameters differ from source declarations: "
                        f"source={[(item.name, item.parameters) for item in mcp]}; "
                        f"live={[(item.name, item.parameters) for item in live]}",
                    )
                )
            notes.append(
                "Live metadata checked with every startup capability enabled; "
                "no registered tool was executed."
            )
        except (ImportError, OSError, TypeError, ValueError, RuntimeError) as exc:
            verification = "UNAVAILABLE"
            issues.append(
                PolicyIssue(
                    code="live_mcp_unavailable",
                    location="kicad_tooling/hwrepo/mcp_server.py",
                    message=str(exc),
                )
            )
    coverage_status: Literal["PASS", "FAIL"] = "FAIL" if issues else "PASS"
    parity = parity_issues(test_root, () if catalog is None else catalog.capabilities)
    return ToolSurfaceReport(
        status="FAIL" if issues or parity else "PASS",
        coverage_status=coverage_status,
        parity_status="FAIL" if parity else "PASS",
        mcp_verification=verification,
        cli=cli,
        mcp=mcp,
        capabilities=() if catalog is None else catalog.capabilities,
        issues=(*issues, *parity),
        notes=tuple(notes),
    )


def format_surfaces(report: ToolSurfaceReport) -> str:
    """Show every classification and its concrete lead/lag explanation."""
    lines = [
        (
            f"Tool surfaces: {report.status}; coverage: {report.coverage_status}; "
            f"core parity policy: {report.parity_status}; MCP: {report.mcp_verification}"
        ),
        f"Behavior tests: {report.behavior_verification} (run the tooling acceptance suite)",
    ]
    for capability in report.capabilities:
        alignment = capability.alignment.replace("_", "-")
        lines.append(f"{capability.scope}/{alignment}: {capability.id} — {capability.reason}")
        lines.append(f"  CLI: {', '.join(capability.cli) or '(none)'}")
        lines.append(f"  MCP: {', '.join(capability.mcp) or '(none)'}")
        lines.extend(f"  Functional gap: {gap}" for gap in capability.gaps)
        lines.extend(f"  Adapter constraint: {item}" for item in capability.constraints)
        if capability.exception is not None:
            lines.append(f"  Exception: {capability.exception}")
        lines.extend(f"  Test: {item}" for item in capability.parity_tests)
    lines.extend(f"{issue.code}: {issue.message}" for issue in report.issues)
    lines.extend(report.notes)
    return "\n".join(lines)
