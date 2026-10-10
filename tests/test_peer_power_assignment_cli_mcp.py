"""Component peer power assignment parity across CLI and MCP."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport
from tests.component_peer_power_assignment_support import (
    RULE_ID,
    peer_pin_netlist_xml,
    peer_power_netlist,
)

pytestmark = [
    pytest.mark.component_lint,
    pytest.mark.design_lint,
    pytest.mark.parity_lint,
    pytest.mark.power_lint,
]


def test_shared_part_id_power_assignment_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    import asyncio
    import json

    from mcp import Client

    from kicad_tooling.hwrepo.contracts import read_model, write_model
    from kicad_tooling.hwrepo.evidence import digest
    from kicad_tooling.hwrepo.mcp_server import create_server
    from kicad_tooling.hwrepo.models import ValidationSummary
    from tests.synthetic_design_lint_project import (
        run_design_lint_cli,
        synthetic_design_lint_project,
    )

    root, summary_path = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    netlist_path = summary_path.parent / "netlist.xml"
    summary = read_model(summary_path, ValidationSummary)
    part_ids = {"U1": "SYNTHETIC-POWER-001", "U2": "synthetic-power-001"}

    for split_domains, expected_roles in (
        (True, {"ground/return", "supply"}),
        (False, set()),
    ):
        observed = peer_power_netlist(
            part_ids=part_ids,
            supply_nets=("+3V3", "+5V") if split_domains else ("+3V3", "+3V3"),
            return_nets=("GND", "AGND") if split_domains else ("GND", "GND"),
        )
        netlist_path.write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
        write_model(
            summary_path,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist_path),
                    }
                }
            ),
        )

        process = run_design_lint_cli(tmp_path, root, summary_path)
        assert process.returncode == 1, process.stderr + process.stdout
        cli_report = DesignLintReport.model_validate_json(process.stdout)

        async def inspect_mcp() -> DesignLintReport:
            async with Client(create_server(root), mode="legacy") as client:
                result = await client.call_tool(
                    "inspect_design_lint",
                    {
                        "project_id": "controller",
                        "native_summary": summary_path.relative_to(root).as_posix(),
                    },
                )
                assert not result.is_error, result.content
                assert result.structured_content is not None
                return DesignLintReport.model_validate_json(json.dumps(result.structured_content))

        mcp_report = asyncio.run(inspect_mcp())
        assert cli_report == mcp_report
        assert cli_report.status == "REVIEW"
        findings = [item for item in cli_report.findings if item.rule_id == RULE_ID]
        assert {item.evidence["peer_role"][0] for item in findings} == expected_roles
