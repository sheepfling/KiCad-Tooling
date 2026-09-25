"""Typed CLI/MCP coverage inventory and declaration drift checks.

AST and SDK schema handling are adapter boundaries: only validated snapshots
enter the catalog comparison. Discovery never executes CLI entry points or kicad_tooling.
"""
from __future__ import annotations

import ast
import asyncio
from importlib.util import find_spec
from pathlib import Path
from typing import Literal, cast

from pydantic import JsonValue

from .contracts import read_model, repo_path
from .models import (
    PolicyIssue,
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
CORE_WORKFLOWS = frozenset({
    "project-inventory", "environment-doctor", "project-scaffold", "import-design",
    "scan-designs", "diagnose-designs", "rescue-project", "project-verification",
    "scope-checks", "native-scope-checks", "contract-coach", "model-coverage",
    "model-population", "three-d-export", "parts-preparation", "purchasing-preferences",
    "review-views", "native-release-export", "engineering-review", "release-readiness",
    "release-packaging", "package-verification", "package-restore", "change-impact",
    "supplier-snapshots", "foreign-board-conversion", "electrical-setup",
    "electrical-input-capture", "electrical-analysis", "electrical-scope-checks",
    "reviewed-part-selection", "paired-cad-import", "supplier-review-handoff",
    "electrical-chart-exports", "exact-cad-sourcing", "sourced-cad-import",
    "cad-step-alignment",
})


def _strings(node: ast.AST, location: str) -> tuple[str, ...]:
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)) or any(
        not isinstance(item, ast.Constant) or not isinstance(item.value, str)
        for item in node.elts
    ):
        raise ValueError(f"{location}: surface choices must be literal strings")
    return tuple(item.value for item in node.elts
                 if isinstance(item, ast.Constant) and isinstance(item.value, str))


def _string(node: ast.AST, location: str) -> str:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        raise TypeError(f"{location}: surface name must be a literal string")
    return node.value


def discover_cli(root: Path) -> tuple[ToolCliSnapshot, ...]:
    """Discover first-party Python CLI modules, command choices and option names."""
    snapshots: list[ToolCliSnapshot] = []
    for candidate in sorted(repo_path(root, "kicad_tooling").rglob("*.py")):
        path = repo_path(root, candidate.relative_to(root).as_posix())
        if not path.is_file():
            raise ValueError(f"CLI source must be a regular file: {path}")
        if path.name == "__main__.py":
            # The installed entry point dispatches existing commands; it adds no
            # new workflow capability of its own.
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        # Public CLIs use a main function or a __main__ module/guard. Supporting
        # either catches a new entry point even before it follows our convention.
        is_cli = path.name == "__main__.py" or any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main"
            for node in tree.body
        ) or any(
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name) and node.left.id == "__name__"
            and any(isinstance(value, ast.Constant) and value.value == "__main__"
                    for value in node.comparators)
            for node in ast.walk(tree)
        )
        if not is_cli:
            continue
        commands: set[str] = set()
        options: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            location = f"{path.relative_to(root)}:{node.lineno}"
            if node.func.attr == "add_parser":
                if not node.args:
                    raise ValueError(f"{location}: subcommand name is missing")
                commands.add(_string(node.args[0], location))
                for keyword in node.keywords:
                    if keyword.arg == "aliases":
                        commands.update(_strings(keyword.value, location))
            if node.func.attr != "add_argument":
                continue
            names = tuple(_string(value, location) for value in node.args)
            options.update(name for name in names if name.startswith("-"))
            if names and not names[0].startswith("-"):
                for keyword in node.keywords:
                    if keyword.arg == "choices":
                        commands.update(_strings(keyword.value, location))
        module = ".".join(path.relative_to(root).with_suffix("").parts)
        snapshots.append(ToolCliSnapshot(
            module=module, commands=tuple(sorted(commands)), options=tuple(sorted(options)),
        ))
    return tuple(snapshots)


def _is_tool_call(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "tool")


def discover_mcp(root: Path) -> tuple[ToolMcpSnapshot, ...]:
    """Read all conditional registrations without importing the optional SDK."""
    path = repo_path(root, "kicad_tooling/hwrepo/mcp_server.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {
        node.name: node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    snapshots: list[ToolMcpSnapshot] = []
    recognized: set[int] = set()
    for node in ast.walk(tree):
        function: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        declaration: ast.Call | None = None
        if isinstance(node, ast.Call) and _is_tool_call(node.func):
            if len(node.args) != 1 or not isinstance(node.args[0], ast.Name):
                raise ValueError(f"{path}:{node.lineno}: unsupported MCP tool registration")
            function = functions.get(node.args[0].id)
            declaration = node.func if isinstance(node.func, ast.Call) else None
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = [value for value in node.decorator_list if _is_tool_call(value)]
            if decorators:
                if len(decorators) != 1:
                    raise ValueError(f"{path}:{node.lineno}: repeated MCP tool decorator")
                function = node
                declaration = decorators[0] if isinstance(decorators[0], ast.Call) else None
        if declaration is None:
            continue
        if function is None or declaration.args:
            raise ValueError(f"{path}:{declaration.lineno}: unsupported MCP tool registration")
        recognized.add(id(declaration))
        name = function.name
        for keyword in declaration.keywords:
            if keyword.arg == "name":
                name = _string(keyword.value, f"{path}:{declaration.lineno}")
        arguments = function.args
        if arguments.vararg is not None or arguments.kwarg is not None:
            raise ValueError(f"{path}:{declaration.lineno}: variadic MCP tool parameters are unsupported")
        parameters = tuple(sorted(argument.arg for argument in (
            *arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
        )))
        snapshots.append(ToolMcpSnapshot(name=name, parameters=parameters))
    if any(_is_tool_call(node) and id(node) not in recognized for node in ast.walk(tree)):
        raise ValueError(f"{path}: unsupported dynamic MCP tool registration")
    return tuple(sorted(snapshots, key=lambda item: item.name))


async def _live_mcp(root: Path) -> tuple[ToolMcpSnapshot, ...]:
    # Keep the SDK optional for every base CLI import and static inventory run.
    from .mcp_server import create_server

    server = create_server(
        root, allow_checks=True, allow_writes=True, allow_edits=True, allow_exports=True,
        allow_downloads=True, allow_supplier_submissions=True,
    )
    snapshots: list[ToolMcpSnapshot] = []
    for tool in await server.list_tools():
        # input_schema is an SDK JSON boundary. Pydantic immediately validates the
        # extracted names, so framework dictionaries never reach comparison code.
        properties = tool.input_schema.get("properties", {})
        if not isinstance(properties, dict):
            raise TypeError(f"MCP tool {tool.name} has no object parameter schema")
        snapshots.append(ToolMcpSnapshot.model_validate({
            "name": tool.name, "parameters": tuple(cast("dict[str, JsonValue]", properties)),
        }))
    return tuple(sorted((item.model_copy(update={"parameters": tuple(sorted(item.parameters))})
                         for item in snapshots), key=lambda item: item.name))


def _cli_endpoints(snapshots: tuple[ToolCliSnapshot, ...]) -> set[str]:
    return {f"{item.module} {command}" for item in snapshots for command in item.commands} | {
        item.module for item in snapshots if not item.commands
    }


def _compare(
    actual_cli: tuple[ToolCliSnapshot, ...], actual_mcp: tuple[ToolMcpSnapshot, ...],
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
                    issue("cli_signature_drift", f"{cli.module} {label}: "
                          f"added {sorted(set(actual) - set(declared))}; "
                          f"removed {sorted(set(declared) - set(actual))}")
    for mcp in actual_mcp:
        expected = expected_mcp.get(mcp.name)
        if expected is not None and set(mcp.parameters) != set(expected.parameters):
            issue("mcp_signature_drift", f"{mcp.name} parameters: "
                  f"added {sorted(set(mcp.parameters) - set(expected.parameters))}; "
                  f"removed {sorted(set(expected.parameters) - set(mcp.parameters))}")
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


def _test_exists(root: Path, reference: str) -> bool:
    """Resolve a unittest method from source without importing/executing tests."""
    parts = reference.split(".")
    if len(parts) < 4 or parts[0] != "tests" or not parts[-1].startswith("test_"):
        return False
    if any(not part.isidentifier() for part in parts):
        return False
    try:
        path = repo_path(root, "/".join(parts[:-2]) + ".py")
        if not path.is_file():
            return False
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return False
    return any(
        isinstance(node, ast.ClassDef) and node.name == parts[-2]
        and any(isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                and method.name == parts[-1] for method in node.body)
        for node in tree.body
    )


def parity_issues(root: Path, mappings: tuple[ToolSurfaceMapping, ...]) -> tuple[PolicyIssue, ...]:
    """Fail missing core capabilities/test references; retain explicit operator exceptions."""
    issues: list[PolicyIssue] = []
    by_id = {mapping.id: mapping for mapping in mappings}
    for identifier in sorted(CORE_WORKFLOWS):
        mapping = by_id.get(identifier)
        if mapping is None or mapping.scope != "core":
            issues.append(PolicyIssue(code="core_scope", location=CATALOG,
                message=f"Required core workflow {identifier} cannot be removed or exempted"))
    for mapping in mappings:
        location = f"{CATALOG}#{mapping.id}"
        if mapping.scope != "core":
            if mapping.exception is None:
                issues.append(PolicyIssue(code="missing_exception", location=location,
                    message="Administrative/adapter differences need an explicit reason"))
            continue
        if (mapping.alignment != "aligned" or not mapping.cli or not mapping.mcp
                or mapping.gaps or mapping.exception is not None):
            issues.append(PolicyIssue(code="core_parity_gap", location=location,
                message=f"{mapping.id}: Core workflows need both surfaces and no functional gap or exception; "
                        "record permissions and path restrictions in constraints"))
        if not mapping.parity_tests:
            issues.append(PolicyIssue(code="missing_parity_tests", location=location,
                message="Core parity requires referenced behavioral regression tests"))
        for reference in mapping.parity_tests:
            if (root / "tests/test_mcp_parity.py").is_file() and not _test_exists(root, reference):
                issues.append(PolicyIssue(code="missing_parity_test", location=location,
                    message=f"Behavioral test does not exist: {reference}"))
    return tuple(issues)


def inspect_tool_surfaces(root: Path, *, require_live_mcp: bool = False) -> ToolSurfaceReport:
    """Check declared coverage and compare the optional live full MCP registration.

    PASS requires declaration coverage and the core parity policy. This inspection
    verifies behavioral test references; it never runs those tests or proves their result.
    """
    root = root.resolve()
    issues: list[PolicyIssue] = []
    cli: tuple[ToolCliSnapshot, ...] = ()
    mcp: tuple[ToolMcpSnapshot, ...] = ()
    catalog: ToolSurfacesCatalog | None = None
    verification: Literal["LIVE", "STATIC_ONLY", "UNAVAILABLE"] = "STATIC_ONLY"
    notes = ["Core parity is required; administration and adapter exceptions stay explicit.",
             ("Behavioral tests were NOT_RUN here; the acceptance checkout executes them. "
             "This inspection checks declarations and test references, not behavior or approval.")]
    if not (SOURCE_ROOT / "tests/test_mcp_parity.py").is_file():
        notes.append("Behavioral parity test sources are outside this package; "
                     "run them in the populated acceptance checkout before a release.")
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
            issues.append(PolicyIssue(
                code="live_mcp_unavailable", location="kicad_tooling/hwrepo/mcp_server.py",
                message="Install the pinned dev or mcp extra to require live MCP verification.",
            ))
    else:
        try:
            live = asyncio.run(_live_mcp(root))
            verification = "LIVE"
            if live != mcp:
                issues.append(PolicyIssue(
                    code="mcp_registration_drift", location="kicad_tooling/hwrepo/mcp_server.py",
                    message="Actual full-server names/parameters differ from source declarations: "
                    f"source={[(item.name, item.parameters) for item in mcp]}; "
                    f"live={[(item.name, item.parameters) for item in live]}",
                ))
            notes.append("Live metadata checked with every startup capability enabled; "
                         "no registered tool was executed.")
        except (ImportError, OSError, TypeError, ValueError, RuntimeError) as exc:
            verification = "UNAVAILABLE"
            issues.append(PolicyIssue(
                code="live_mcp_unavailable", location="kicad_tooling/hwrepo/mcp_server.py", message=str(exc),
            ))
    coverage_status: Literal["PASS", "FAIL"] = "FAIL" if issues else "PASS"
    parity = parity_issues(SOURCE_ROOT, () if catalog is None else catalog.capabilities)
    return ToolSurfaceReport(
        status="FAIL" if issues or parity else "PASS", coverage_status=coverage_status,
        parity_status="FAIL" if parity else "PASS", mcp_verification=verification,
        cli=cli, mcp=mcp, capabilities=() if catalog is None else catalog.capabilities,
        issues=(*issues, *parity), notes=tuple(notes),
    )


def format_surfaces(report: ToolSurfaceReport) -> str:
    """Show every classification and its concrete lead/lag explanation."""
    lines = [(f"Tool surfaces: {report.status}; coverage: {report.coverage_status}; "
             f"core parity policy: {report.parity_status}; MCP: {report.mcp_verification}"),
             f"Behavior tests: {report.behavior_verification} (run kicad_tooling.ci)"]
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
