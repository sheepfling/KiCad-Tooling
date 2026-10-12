"""CLI/MCP parity for all-open generic connector peer-pin review."""

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
]

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintRuleOverride,
    ProjectManifest,
    ValidationSummary,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "connector.generic_peer_pin_all_open"


def _netlist_xml(*, fault: bool, part_id_aliases: bool = False) -> str:
    power_nodes = "".join(f'<node ref="J{reference}" pin="1"/>' for reference in (1, 2))
    return_nodes = (
        "" if fault else '<net name="GND"><node ref="J1" pin="2"/><node ref="J2" pin="2"/></net>'
    )
    symbol_names = (
        ("GenericPassivePortLeft", "GenericPassivePortRight")
        if part_id_aliases
        else ("GenericPassivePort", "GenericPassivePort")
    )
    components = "".join(
        f'<comp ref="J{reference}"><value>Synthetic peer port</value>'
        "<footprint>Synthetic:Port</footprint>"
        + (
            '<fields><field name="PART_ID">SYNTHETIC-PASSIVE-PORT-001</field></fields>'
            if part_id_aliases
            else ""
        )
        + f'<libsource lib="Synthetic" part="{symbol_name}"/></comp>'
        for reference, symbol_name in zip((1, 2), symbol_names, strict=True)
    )
    libparts = "".join(
        f'<libpart lib="Synthetic" part="{symbol_name}"><pins>'
        '<pin num="1" name="Pin_1" type="passive"/>'
        '<pin num="2" name="Pin_2" type="passive"/>'
        "</pins></libpart>"
        for symbol_name in sorted(set(symbol_names))
    )
    return (
        f"<export><components>{components}</components><libparts>{libparts}</libparts><nets>"
        f'<net name="+5V">{power_nodes}</net>{return_nodes}'
        "</nets></export>"
    )


def test_all_open_generic_peer_pin_lint_cli_mcp_parity(tmp_path: Path) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.schematic_component_inventory",
                mode="off",
                reason="Synthetic parity fixture has no native PCB snapshot",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_pcb_dnp_mismatch",
                mode="off",
                reason="Synthetic parity fixture has no native PCB snapshot",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_pcb_value_mismatch",
                mode="off",
                reason="Synthetic parity fixture has no native PCB snapshot",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_pcb_pad_net_mismatch",
                mode="off",
                reason="Synthetic parity fixture has no native PCB pad snapshot",
            ),
            DesignLintRuleOverride(
                rule_id="protection.unreviewed_interface_pin",
                mode="off",
                reason="Synthetic parity fixture isolates generic peer-pin review",
            ),
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic parity fixture explicitly enables the opt-in heuristic",
            ),
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic parity fixture reviews both generic connector peers"
                ),
                "connector_reviews": tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="not_applicable",
                        basis="Synthetic regression symbol is not a project interface",
                    )
                    for reference in ("J1", "J2")
                ),
            }
        ),
    )
    netlist = native.parent / "netlist.xml"
    summary = read_model(native, ValidationSummary)

    def write_netlist(*, fault: bool, part_id_aliases: bool = False) -> None:
        netlist.write_text(
            _netlist_xml(fault=fault, part_id_aliases=part_id_aliases),
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

    for part_id_aliases in (False, True):
        for fault, expected_status, expected_count in (
            (True, "REVIEW", 1),
            (False, "PASS", 0),
        ):
            write_netlist(fault=fault, part_id_aliases=part_id_aliases)
            process = run_design_lint_cli(tmp_path, root, native)
            assert process.returncode in {0, 1}, process.stderr + process.stdout
            cli = DesignLintReport.model_validate_json(process.stdout)
            mcp = asyncio.run(inspect_mcp())

            assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
            assert cli.status == expected_status, (
                cli.issues,
                [
                    (item.rule_id, item.subject, item.mode, item.disposition)
                    for item in cli.findings
                ],
            )
            findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
            assert len(findings) == expected_count
            assert cli.connector_peer_pin_coverage is not None
            assert cli.connector_peer_pin_coverage.generic_peer_pin_all_open_finding_count == (
                expected_count
            )
            if part_id_aliases and fault:
                assert findings[0].evidence["peer_identity_basis"] == ("part_id",)
                assert findings[0].evidence["peer_identity"] == ("SYNTHETIC-PASSIVE-PORT-001",)
