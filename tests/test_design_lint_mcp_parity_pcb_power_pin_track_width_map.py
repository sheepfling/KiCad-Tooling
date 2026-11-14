"""CLI/MCP parity for power-pin track-width map coverage review."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride, ValidationSummary
from tests.design_lint_fixtures.pcb_power_pin_track_width import (
    NETLIST_FIXTURE,
    native_power_netlist,
    power_track_width_map,
)
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.power_lint,
    pytest.mark.design_lint_rule(rule_id="pcb.power_pin_net_track_width_map_coverage"),
]

RULE_ID = "pcb.power_pin_net_track_width_map_coverage"
EXPECTED_NETLIST_SHA256 = "e1c4969123837d1ae59b790eb4373071a3a8008311bf2b0664ed7429e476111d"


def test_unmapped_power_pin_nets_and_mapped_control_match_cli_and_mcp(
    tmp_path: Path,
) -> None:
    assert hashlib.sha256(NETLIST_FIXTURE.read_bytes()).hexdigest() == EXPECTED_NETLIST_SHA256
    assert native_power_netlist().pin_electrical_types["U1.1"] == "power_in"

    base_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic project opts into power-net width-map review.",
            ),
        )
    )
    policies = (
        ("fault", parity_design_lint_policy(base_policy), {"INPUT", "RETURN"}),
        (
            "mapped-control",
            parity_design_lint_policy(
                base_policy.model_copy(
                    update={"pcb_track_width_map": power_track_width_map("INPUT", "RETURN")}
                )
            ),
            set(),
        ),
    )

    async def inspect_mcp(root: Path, native: Path) -> DesignLintReport:
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

    for case, policy, expected_nets in policies:
        root, native = synthetic_design_lint_project(tmp_path / case, policy)
        install_source_bound_drc_receipt(root, native)
        netlist_path = native.parent / "netlist.xml"
        shutil.copyfile(NETLIST_FIXTURE, netlist_path)
        summary = read_model(native, ValidationSummary)
        summary = summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "netlist.xml": digest(netlist_path),
                }
            }
        )
        write_model(native, summary)

        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli = DesignLintReport.model_validate_json(process.stdout)
        mcp = asyncio.run(inspect_mcp(root, native))
        assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
        findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
        assert {item.evidence["net"][0] for item in findings} == expected_nets
