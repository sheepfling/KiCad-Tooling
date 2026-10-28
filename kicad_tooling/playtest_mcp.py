"""Exercise the installed MCP surface from the disposable playtest driver."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, TypeAlias, TypedDict, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import AudioContent, EmbeddedResource, ImageContent, ResourceLink, TextContent
from pydantic import JsonValue, TypeAdapter

McpContentBlock: TypeAlias = (
    TextContent | ImageContent | AudioContent | ResourceLink | EmbeddedResource
)


class PlaytestFinding(TypedDict, total=False):
    """Actionable finding fields inspected in CLI and MCP receipts."""

    severity: str
    action: str


class PlaytestProject(TypedDict):
    """Identity fields required to select the disposable reference project."""

    id: str
    toolchain_id: str
    project: str


class PlaytestReport(TypedDict, total=False):
    """Validated JSON envelope fields consumed from the installed tooling."""

    status: str
    build_authorized: bool
    projects: list[PlaytestProject]
    findings: list[PlaytestFinding]
    initialization: str
    directory: str
    copied_sha256: dict[str, str]
    review_required: bool
    components: dict[str, JsonValue]
    nets: dict[str, JsonValue]
    review_state: str
    electrical_coverage: bool


PLAYTEST_REPORT_ADAPTER = TypeAdapter(PlaytestReport)


class PlaytestHost(Protocol):
    """Small callback surface supplied by the command-line rehearsal driver."""

    output: Path
    caller: Path
    environment: dict[str, str]

    def save(self, name: str, document: object) -> None: ...

    def record(self, name: str, passed: bool, **details: JsonValue) -> None: ...


async def run_mcp_playtest(host: PlaytestHost, root: Path, toolchain_id: str) -> None:
    """Record default and explicitly enabled MCP workflows against a disposable root."""
    for writable in (False, True):
        label = "mcp-enabled" if writable else "mcp-default"
        arguments = ["-I", "-B", "-m", "kicad_tooling.mcp", "--root", str(root)]
        if writable:
            arguments += ["--allow-checks", "--allow-writes"]
        parameters = StdioServerParameters(
            command=sys.executable, args=arguments, cwd=host.caller, env=dict(host.environment)
        )
        with (host.output / f"{label}.stderr.log").open("w", encoding="utf-8") as errors:
            async with stdio_client(parameters, errlog=errors) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=120) as client:
                    initialized = await client.initialize()
                    host.save(f"{label}-initialize.json", initialized.model_dump(mode="json"))
                    host.record(f"{label}-initialize", bool(initialized.protocol_version))
                    listing = await client.list_tools()
                    names = {tool.name for tool in listing.tools}
                    host.save(f"{label}-tools.json", listing.model_dump(mode="json"))
                    required = {"list_projects", "read_document"}
                    if writable:
                        required |= {"new_project", "diagnose_project", "check_project"}
                    host.record(
                        f"{label}-capabilities",
                        required <= names
                        and (
                            writable
                            or not names.intersection(
                                {"new_project", "diagnose_project", "check_project"}
                            )
                        ),
                        required=cast(JsonValue, sorted(required)),
                        available=cast(JsonValue, sorted(names)),
                    )

                    async def call(
                        name: str,
                        tool_arguments: Mapping[str, JsonValue],
                        stage: str,
                        expected_status: str,
                    ) -> PlaytestReport:
                        result = await client.call_tool(name, dict(tool_arguments))
                        host.save(f"{stage}.json", result.model_dump(mode="json"))
                        data = PLAYTEST_REPORT_ADAPTER.validate_python(
                            result.structured_content or {}, strict=True
                        )
                        host.record(
                            stage,
                            not result.is_error
                            and data.get("status") == expected_status
                            and data.get("build_authorized") is not True,
                            tool=name,
                            observed_status=data.get("status"),
                            expected_status=expected_status,
                            is_error=result.is_error,
                        )
                        return data

                    inventory = await call("list_projects", {}, f"{label}-inventory", "PASS")
                    host.record(
                        f"{label}-project-identity",
                        "controller" in {item["id"] for item in inventory.get("projects", [])},
                    )
                    document = await client.call_tool("read_document", {"name": "start-here"})
                    content: list[McpContentBlock] = document.content
                    contents = "\n".join(
                        item.text for item in content if isinstance(item, TextContent)
                    )
                    host.save(f"{label}-document.json", document.model_dump(mode="json"))
                    host.record(
                        f"{label}-document",
                        not document.is_error
                        and contents
                        == (root / "docs/workflow/START_HERE.md").read_text(encoding="utf-8"),
                    )
                    if not writable:
                        denied = await client.call_tool(
                            "check_project", {"project_id": "controller"}
                        )
                        host.save("mcp-default-denied-check.json", denied.model_dump(mode="json"))
                        host.record("mcp-default-denied-check", denied.is_error)
                        continue
                    await call(
                        "new_project",
                        {
                            "project_id": "mcp-first",
                            "kind": "pcb",
                            "toolchain_id": toolchain_id,
                        },
                        "mcp-new-project",
                        "PASS",
                    )
                    diagnosis = await call(
                        "diagnose_project",
                        {"project_id": "mcp-first"},
                        "mcp-diagnose-first",
                        "NEEDS_WORK",
                    )
                    host.record(
                        "mcp-actionable-diagnosis",
                        bool(diagnosis.get("findings"))
                        and any(
                            item.get("severity") == "BLOCKING" and item.get("action")
                            for item in diagnosis.get("findings", [])
                        ),
                    )
                    await call(
                        "check_project",
                        {"project_id": "mcp-first"},
                        "mcp-check-incomplete",
                        "FAIL",
                    )
                    await call(
                        "check_project",
                        {"project_id": "controller"},
                        "mcp-check-controller",
                        "PASS",
                    )
