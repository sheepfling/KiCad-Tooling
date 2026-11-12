"""CLI/MCP parity for malformed PCB netclass inventory shapes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import run_design_lint_cli, synthetic_design_lint_project

RULE_ID = "pcb.drc_malformed_netclass_inventory"
SETTINGS_DIR = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings"
CASES = (
    ("fault-netclass-classes-object.kicad_pro", True),
    ("fault-netclass-class-entry-null.kicad_pro", True),
    ("fault-netclass-class-entry-missing-name.kicad_pro", True),
    ("fault-netclass-class-name-null.kicad_pro", True),
    ("fault-netclass-class-name-number.kicad_pro", True),
    ("fault-netclass-class-name-boolean.kicad_pro", True),
    ("fault-netclass-class-name-array.kicad_pro", True),
    ("fault-netclass-class-name-object.kicad_pro", True),
    ("fault-netclass-class-name-empty.kicad_pro", True),
    ("control-netclass-assignment-default.kicad_pro", False),
    ("control-netclass-assignment-array-narrow.kicad_pro", False),
    ("control-netclass-assignment-array-empty.kicad_pro", False),
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


@pytest.mark.parametrize(("settings_name", "should_review"), CASES)
def test_malformed_netclass_inventory_matches_between_cli_and_mcp(
    tmp_path: Path,
    settings_name: str,
    should_review: bool,
) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
        kicad_version="10.0.8",
        image="registry.invalid/kicad:10.0.8@sha256:" + "b" * 64,
        project_settings_source=(SETTINGS_DIR / settings_name).read_text(encoding="utf-8"),
    )
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
    cli_report = parse_model_text(process.stdout, DesignLintReport)

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

    mcp_report = asyncio.run(inspect_mcp())

    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    findings = [item for item in mcp_report.findings if item.rule_id == RULE_ID]
    assert len(findings) == (1 if should_review else 0)
    if should_review:
        assert findings[0].subject.startswith(
            "projects/controller/kicad/controller.kicad_pro#net_settings.classes"
        )
