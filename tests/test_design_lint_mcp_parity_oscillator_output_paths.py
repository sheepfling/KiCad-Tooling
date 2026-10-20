"""CLI and MCP parity for mapped oscillator output paths."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    ProjectManifest,
)
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)
from tests.test_oscillator_output_paths import (
    oscillator_output_netlist,
    oscillator_output_path_map,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def test_oscillator_output_path_matches_cli_and_mcp(tmp_path: Path) -> None:
    policy = parity_design_lint_policy(
        DesignLintPolicy(oscillator_output_path_map=oscillator_output_path_map())
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic oscillator output path parity fixture"
                )
            }
        ),
    )

    def install_netlist(resistor_value: str) -> None:
        install_synthetic_netlist(
            native,
            contract_netlist_xml(oscillator_output_netlist(resistor_value=resistor_value)),
        )

    async def compare_with_mcp() -> tuple[DesignLintReport, DesignLintReport, int]:
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli = DesignLintReport.model_validate_json(process.stdout)
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
        mcp = DesignLintReport.model_validate_json(json.dumps(result.structured_content))
        return cli, mcp, process.returncode

    async def exercise() -> None:
        install_netlist("33R")
        control_cli, control_mcp, control_exit = await compare_with_mcp()
        assert semantic_design_lint_report(control_cli) == semantic_design_lint_report(control_mcp)
        assert control_cli.status == "REVIEW", control_cli.issues
        assert control_exit == 1
        assert "oscillator.output_load_path_mismatch" not in {
            item.rule_id for item in control_cli.findings
        }

        install_netlist("1k")
        fault_cli, fault_mcp, fault_exit = await compare_with_mcp()
        assert semantic_design_lint_report(fault_cli) == semantic_design_lint_report(fault_mcp)
        assert fault_cli.status == "REVIEW", fault_cli.issues
        assert fault_exit == 1
        finding = next(
            item
            for item in fault_cli.findings
            if item.rule_id == "oscillator.output_load_path_mismatch"
        )
        assert any(
            "nominal resistance is 1000 ohms" in issue for issue in finding.evidence["issues"]
        )

    asyncio.run(exercise())
