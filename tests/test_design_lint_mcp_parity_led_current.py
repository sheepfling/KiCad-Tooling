"""CLI and MCP use the same mapped LED current-window service."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInventoryReview,
    ProjectManifest,
    ValidationSummary,
)
from tests.design_lint_fixtures.led_current import led_current_map
from tests.mcp_parity_support import parity_design_lint_policy
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]

RULE_ID = "component.mapped_led_current_range_mismatch"


def _netlist_xml(resistor_value: str) -> str:
    return (
        "<export><components>"
        '<comp ref="D1"><value>Synthetic green LED</value>'
        "<footprint>Synthetic:LED_0603</footprint>"
        '<libsource lib="Device" part="LED"/></comp>'
        f'<comp ref="R1"><value>{resistor_value}</value>'
        "<footprint>Synthetic:R_0603</footprint>"
        '<libsource lib="Device" part="R"/></comp>'
        "</components><libparts>"
        '<libpart lib="Device" part="LED"><pins>'
        '<pin num="1" name="A" type="passive"/>'
        '<pin num="2" name="K" type="passive"/>'
        "</pins></libpart>"
        '<libpart lib="Device" part="R"><pins>'
        '<pin num="1" name="~" type="passive"/>'
        '<pin num="2" name="~" type="passive"/>'
        "</pins></libpart></libparts><nets>"
        '<net name="+3V3"><node ref="R1" pin="1"/></net>'
        '<net name="LED_A"><node ref="D1" pin="1"/>'
        '<node ref="R1" pin="2"/></net>'
        '<net name="GND"><node ref="D1" pin="2"/></net>'
        "</nets></export>"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_led_current_map_findings_and_coverage_match_cli_and_mcp(tmp_path: Path) -> None:
    asyncio.run(_assert_cli_mcp_parity(tmp_path))


async def _assert_cli_mcp_parity(base: Path) -> None:
    policy = parity_design_lint_policy(DesignLintPolicy(led_current_map=led_current_map()))
    root, summary_path = synthetic_design_lint_project(
        base,
        policy,
        project_id="controller",
        kicad_version="10.0.5",
        image=PINNED_NATIVE_KICAD_IMAGES["10.0.5"],
    )
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic parity fixture has no external connector interfaces"
                )
            }
        ),
    )

    async with Client(create_server(root), mode="legacy") as client:

        async def compare(resistor_value: str, status: str, exit_code: int) -> DesignLintReport:
            netlist_path = install_synthetic_netlist(
                summary_path,
                _netlist_xml(resistor_value),
            )
            summary = read_model(summary_path, ValidationSummary)
            assert summary.artifacts_sha256["netlist.xml"] == digest(netlist_path)
            cli_process = run_design_lint_cli(base, root, summary_path)
            assert cli_process.returncode == exit_code, (
                cli_process.stderr + cli_process.stdout[-4000:]
            )
            cli = DesignLintReport.model_validate_json(cli_process.stdout)
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": summary_path.relative_to(root).as_posix(),
                },
            )
            assert not result.is_error, result.content
            assert result.structured_content is not None
            mcp = DesignLintReport.model_validate_json(json.dumps(result.structured_content))

            assert cli == mcp
            assert mcp.status == status
            check = next(item for item in mcp.mapped_check_runs if item.rule_id == RULE_ID)
            assert check.status == "EVALUATED"
            assert check.netlist_sha256 == mcp.netlist_sha256
            assert check.requirement_count == 1
            return mcp

        control = await compare("470R", "PASS", 0)
        control_check = next(item for item in control.mapped_check_runs if item.rule_id == RULE_ID)
        assert control_check.finding_count == 0
        assert not any(item.rule_id == RULE_ID for item in control.findings)

        fault = await compare("100R", "REVIEW", 1)
        fault_check = next(item for item in fault.mapped_check_runs if item.rule_id == RULE_ID)
        assert fault_check.finding_count == 1
        finding = next(item for item in fault.findings if item.rule_id == RULE_ID)
        assert finding.evidence["resistor_nominal_ohms"] == ("100",)
        assert finding.evidence["netlist_sha256"] == (fault.netlist_sha256,)
