"""CLI/MCP parity for the exact-role-mapped custom passive review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentRoleBinding,
    ComponentRoleMap,
    ComponentRolePin,
    DesignLintPolicy,
    DesignLintReport,
    ValidationSummary,
)
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
]


def test_mapped_custom_capacitor_same_net_lint_cli_mcp_parity(tmp_path: Path) -> None:
    """The authored role map enables the same review finding on each surface."""
    role_map = ComponentRoleMap(
        entries=(
            ComponentRoleBinding(
                part_id="synthetic-capacitor",
                symbol="Vendor:CAP123",
                footprint="Synthetic:CAP123_0603",
                role="capacitor",
                pins=(
                    ComponentRolePin(number="1", function="1", electrical_type="passive"),
                    ComponentRolePin(number="2", function="2", electrical_type="passive"),
                ),
                basis="Synthetic parity fixture reviewed this exact custom capacitor identity",
            ),
        )
    )
    root, native = synthetic_design_lint_project(
        tmp_path, DesignLintPolicy(component_role_map=role_map)
    )
    netlist = native.parent / "netlist.xml"

    def write_netlist(same_net: bool) -> None:
        nets = (
            '<net name="BYPASSED"><node ref="C1" pin="1"/><node ref="C1" pin="2"/></net>'
            if same_net
            else '<net name="+3V3"><node ref="C1" pin="1"/></net>'
            '<net name="GND"><node ref="C1" pin="2"/></net>'
        )
        netlist.write_text(
            "<export><components>"
            '<comp ref="C1"><value>100nF</value>'
            "<footprint>Synthetic:CAP123_0603</footprint>"
            '<fields><field name="PART_ID">synthetic-capacitor</field></fields>'
            '<libsource lib="Vendor" part="CAP123"/></comp>'
            "</components><libparts>"
            '<libpart lib="Vendor" part="CAP123"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/>'
            f"</pins></libpart></libparts><nets>{nets}</nets></export>",
            encoding="utf-8",
        )
        summary = read_model(native, ValidationSummary)
        write_model(
            native,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist),
                    }
                }
            ),
        )

    async def inspect_mcp() -> DesignLintReport:
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(root).as_posix(),
                },
            )
            assert not result.is_error, result.content
            assert result.structured_content is not None
            return DesignLintReport.model_validate_json(json.dumps(result.structured_content))

    def compare() -> DesignLintReport:
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli_report = parse_model_text(process.stdout, DesignLintReport)
        mcp_report = asyncio.run(inspect_mcp())
        assert cli_report == mcp_report
        return cli_report

    write_netlist(same_net=True)
    fault = compare()
    finding = next(
        item for item in fault.findings if item.rule_id == "component.two_pin_passive_same_net"
    )
    assert finding.evidence["role_part_id"] == ("synthetic-capacitor",)
    assert finding.evidence["classified_role"] == ("capacitor",)

    write_netlist(same_net=False)
    control = compare()
    assert "component.two_pin_passive_same_net" not in {item.rule_id for item in control.findings}
