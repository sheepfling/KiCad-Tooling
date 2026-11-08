"""CLI/MCP parity for numeric-only connector peer-open review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride, ValidationSummary
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
]

RULE_ID = "connector.generic_peer_pin_open_outlier"


def _netlist_xml(*, fault: bool, part_id_alias: bool = False) -> str:
    references = ("J1", "J2", "J3") if part_id_alias else ("J1", "J2")
    parts = {
        reference: ("NumericPortB" if part_id_alias and reference == "J3" else "NumericPortA")
        for reference in references
    }
    component_rows = []
    for reference in references:
        part_id_field = (
            '<fields><field name="PART_ID">SYNTHETIC-NUMERIC-PEER</field></fields>'
            if part_id_alias
            else ""
        )
        component_rows.append(
            f'<comp ref="{reference}"><value>Generic port</value>'
            f"<footprint>Synthetic:Port</footprint>{part_id_field}"
            f'<libsource lib="Synthetic" part="{parts[reference]}"/></comp>'
        )
    pin_rows = (
        '<pin num="1" name="1" type="passive"/>'
        '<pin num="2" name="2" type="passive"/>'
        '<pin num="3" name="3" type="passive"/>'
    )
    part_rows = "".join(
        f'<libpart lib="Synthetic" part="{part}"><pins>{pin_rows}</pins></libpart>'
        for part in sorted(set(parts.values()))
    )
    assigned_targets = ("J1",) if fault else ("J1", "J2")
    if part_id_alias and not fault:
        assigned_targets = (*assigned_targets, "J3")
    net_rows = [
        '<net name="+5V">'
        + "".join(f'<node ref="{reference}" pin="1"/>' for reference in assigned_targets)
        + "</net>",
        '<net name="GND">'
        + "".join(f'<node ref="{reference}" pin="2"/>' for reference in references)
        + "</net>",
    ]
    net_rows.extend(
        f'<net name="PORT_{reference}"><node ref="{reference}" pin="3"/></net>'
        for reference in references
    )
    return (
        "<export><components>"
        + "".join(component_rows)
        + "</components><libparts>"
        + part_rows
        + "</libparts><nets>"
        + "".join(net_rows)
        + "</nets></export>"
    )


def test_numeric_peer_open_lint_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic parity fixture enables numeric connector peer review",
            ),
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    manifest = read_model(native, ValidationSummary)
    netlist = native.parent / "netlist.xml"

    def write_source_bound_netlist(*, fault: bool, part_id_alias: bool) -> None:
        netlist.write_text(
            _netlist_xml(fault=fault, part_id_alias=part_id_alias),
            encoding="utf-8",
        )
        write_model(
            native,
            manifest.model_copy(
                update={
                    "artifacts_sha256": {
                        **manifest.artifacts_sha256,
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

    cases = (
        (True, False, 1),
        (False, False, 0),
        (True, True, 1),
        (False, True, 0),
    )
    for fault, part_id_alias, expected_count in cases:
        write_source_bound_netlist(fault=fault, part_id_alias=part_id_alias)
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1, 2}, process.stderr + process.stdout
        cli = DesignLintReport.model_validate_json(process.stdout)
        mcp = asyncio.run(inspect_mcp())

        assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
        findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
        assert len(findings) == expected_count, (
            f"fault={fault}, part_id_alias={part_id_alias}: {findings!r}"
        )
        if findings:
            expected_basis = "part_id" if part_id_alias else "exact_symbol"
            assert findings[0].evidence["peer_identity_basis"] == (expected_basis,)
        assert cli.connector_peer_pin_coverage is not None
        assert cli.connector_peer_pin_coverage.generic_peer_pin_open_outlier_finding_count == (
            expected_count
        )
