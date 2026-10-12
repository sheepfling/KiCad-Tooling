"""CLI/MCP parity for named connector power-input alias review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
]

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ValidationSummary,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "connector.peer_power_input_open_assignment"


def _netlist_xml(*, common_assignment: bool) -> str:
    components = "".join(
        f'<comp ref="J{index}"><value>Synthetic peer</value>'
        "<footprint>Synthetic:2Pin</footprint>"
        '<fields><field name="PART_ID">SYNTHETIC-NAMED-INPUT-001</field></fields>'
        f'<libsource lib="Synthetic" part="Port{alias}"/></comp>'
        for index, alias in ((1, "A"), (2, "B"))
    )
    pins = "".join(
        f'<libpart lib="Synthetic" part="Port{alias}"><pins>'
        '<pin num="1" name="BIAS_IN" type="power_in"/>'
        '<pin num="2" name="Pin_2" type="passive"/>'
        "</pins></libpart>"
        for alias in ("A", "B")
    )
    power_nodes = (
        '<node ref="J1" pin="1"/><node ref="J2" pin="1"/>'
        if common_assignment
        else '<node ref="J1" pin="1"/>'
    )
    return (
        f"<export><components>{components}</components><libparts>{pins}</libparts><nets>"
        '<net name="SYNTHETIC_SIGNAL"><node ref="J1" pin="2"/>'
        '<node ref="J2" pin="2"/></net>'
        f'<net name="SYNTHETIC_BIAS">{power_nodes}</net>'
        "</nets></export>"
    )


def test_named_connector_power_input_open_assignment_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    unrelated_rules = (
        "pcb.schematic_component_inventory",
        "pcb.schematic_pcb_dnp_mismatch",
        "pcb.schematic_pcb_value_mismatch",
        "pcb.schematic_pcb_pad_net_mismatch",
        "protection.unreviewed_interface_pin",
    )
    policy = DesignLintPolicy(
        rules=tuple(
            DesignLintRuleOverride(
                rule_id=rule_id,
                mode="off",
                reason="Synthetic parity fixture omits native PCB snapshots",
            )
            for rule_id in unrelated_rules
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    netlist = native.parent / "netlist.xml"
    summary = read_model(native, ValidationSummary)

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

    for common_assignment, expected_count in (
        (False, 1),
        (True, 0),
    ):
        netlist.write_text(_netlist_xml(common_assignment=common_assignment), encoding="utf-8")
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
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli = DesignLintReport.model_validate_json(process.stdout)
        mcp = asyncio.run(inspect_mcp())

        assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
        assert cli.status in {"PASS", "REVIEW"}
        assert sum(item.rule_id == RULE_ID for item in cli.findings) == expected_count
