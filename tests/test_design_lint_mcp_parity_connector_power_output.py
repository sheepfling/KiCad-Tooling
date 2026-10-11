"""CLI/MCP parity for generic unassigned connector power-output review."""

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
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    ProjectManifest,
    ValidationSummary,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "connector.unconnected_power_output"


def test_generic_connector_power_output_review_cli_mcp_parity(tmp_path: Path) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.schematic_component_inventory",
                mode="off",
                reason="Synthetic parity fixture isolates connector power-output review",
            ),
            DesignLintRuleOverride(
                rule_id="protection.unreviewed_interface_pin",
                mode="off",
                reason="Synthetic parity fixture isolates connector power-output review",
            ),
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        root / "catalog/interfaces.json",
        InterfacesCatalog(
            schema_version="1",
            interfaces=(
                InterfaceRecord(
                    id="synthetic-port",
                    revision="synthetic-1",
                    pins=(
                        InterfacePin(
                            number="1",
                            signal="OUTPUT",
                            role="signal",
                            direction="output",
                            voltage_domain="synthetic-output",
                            mating="synthetic peer",
                            orientation="straight",
                            mechanical_clearance="synthetic",
                        ),
                        InterfacePin(
                            number="2",
                            signal="GND",
                            role="return",
                            direction="bidirectional",
                            voltage_domain="synthetic-reference",
                            mating="synthetic peer",
                            orientation="straight",
                            mechanical_clearance="synthetic",
                        ),
                    ),
                ),
            ),
        ),
    )
    connector_reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis="Synthetic parity fixture includes a reviewed interface for each connector",
            interface_id="synthetic-port",
            pin_map={"1": "1", "2": "2"},
        )
        for reference in ("J1", "J2")
    )
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "interfaces": ("synthetic-port",),
                "connector_reviews": connector_reviews,
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic fixture inventories generic connector ports J1 and J2"
                ),
            }
        ),
    )
    netlist = native.parent / "netlist.xml"
    summary = read_model(native, ValidationSummary)

    def write_netlist(connected: bool) -> None:
        power_net = (
            '<net name="POWER_OUTPUT_TEST"><node ref="J1" pin="1"/><node ref="J2" pin="1"/></net>'
            if connected
            else ""
        )
        netlist.write_text(
            "<export><components>"
            + "".join(
                f'<comp ref="J{index}"><value>Synthetic port</value>'
                "<footprint>Synthetic:Port</footprint>"
                '<libsource lib="Synthetic" part="GenericPowerOutputPort"/></comp>'
                for index in (1, 2)
            )
            + "</components><libparts>"
            '<libpart lib="Synthetic" part="GenericPowerOutputPort"><pins>'
            '<pin num="1" name="1" type="power_out"/>'
            '<pin num="2" name="GND" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="GND"><node ref="J1" pin="2"/>'
            '<node ref="J2" pin="2"/></net>'
            f"{power_net}</nets></export>",
            encoding="utf-8",
        )
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

    for connected, expected_status in ((False, "REVIEW"), (True, "PASS")):
        write_netlist(connected)
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli = DesignLintReport.model_validate_json(process.stdout)
        mcp = asyncio.run(inspect_mcp())

        assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
        assert cli.status == expected_status, (cli.issues, [item.rule_id for item in cli.findings])
        expected_rules = {RULE_ID} if not connected else set()
        assert {
            item.rule_id for item in cli.findings if item.disposition != "RULE_OFF"
        } == expected_rules
