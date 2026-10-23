"""CLI/MCP parity for the project-mapped generic connector signal review."""

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
    pytest.mark.interface_lint,
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
)
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "connector.mapped_interface_signal_unassigned"
SHIELD_RULE_ID = "connector.mapped_interface_shield_unassigned"
INTERFACE_ID = "synthetic-connector-port"


def _install_reviewed_interface(
    root: Path,
    island: Path,
    *,
    target_role: str = "signal",
) -> Path:
    shield = target_role == "shield"
    interface = InterfaceRecord(
        id=INTERFACE_ID,
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="UART_TX",
                role="signal",
                direction="output",
                voltage_domain="logic-3v3",
                mating="UART_RX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="CHASSIS_SHIELD" if shield else "UART_RX",
                role=target_role,
                direction="passive" if shield else "input",
                voltage_domain="chassis" if shield else "logic-3v3",
                mating="CHASSIS_BOND" if shield else "UART_TX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="3",
                signal="SIGNAL_RETURN",
                role="return",
                direction="passive",
                voltage_domain="signal-return",
                mating="SIGNAL_RETURN",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )
    catalog_path = root / "catalog/interfaces.json"
    write_model(
        catalog_path,
        InterfacesCatalog(schema_version="1", interfaces=(interface,)),
    )
    manifest_path = island / "project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "interfaces": (INTERFACE_ID,),
                "connector_reviews": (
                    ConnectorInterfaceReview(
                        reference="J1",
                        disposition="interface",
                        basis="Synthetic independently reviewed UART connector pinout",
                        interface_id=INTERFACE_ID,
                        pin_map={"1": "1", "2": "2", "3": "3"},
                    ),
                ),
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic review covers the complete connector inventory"
                ),
            }
        ),
    )
    return catalog_path


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.design_lint_rule(rule_id=SHIELD_RULE_ID)
def test_mapped_interface_signal_review_cli_mcp_parity(tmp_path: Path) -> None:
    """A mapped open signal is REVIEW on both surfaces and clears when connected."""
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="protection.unreviewed_interface_pin",
                mode="off",
                reason="Synthetic fixture isolates mapped signal assignment behavior",
            ),
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, parity_design_lint_policy(policy))
    island = root / "projects/controller"
    catalog_path = _install_reviewed_interface(root, island)
    fixture_root = Path(__file__).parent / "fixtures/design_lint/mapped-interface-signal-parity"

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
        cli_process = run_design_lint_cli(tmp_path, root, native)
        assert cli_process.returncode in {0, 1}, cli_process.stderr + cli_process.stdout
        cli_report = DesignLintReport.model_validate_json(cli_process.stdout)
        mcp_report = asyncio.run(inspect_mcp())
        assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
        return cli_report

    fault_netlist = (fixture_root / "fault-netlist.xml").read_text(encoding="utf-8")
    install_synthetic_netlist(native, fault_netlist)
    fault = compare()
    assert fault.connector_coverage is not None
    assert fault.connector_coverage.status == "COMPLETE"
    assert fault.connector_coverage.interface_catalog_sha256 == digest(catalog_path)
    assert fault.status == "REVIEW", fault.issues
    findings = [item for item in fault.findings if item.rule_id == RULE_ID]
    assert len(findings) == 1
    assert findings[0].subject == "J1.2: reviewed signal contact has no net assignment"
    assert findings[0].evidence["interface_signal"] == ("UART_RX",)
    assert findings[0].evidence["interface_catalog_sha256"] == (digest(catalog_path),)
    assert findings[0].evidence["assigned_nets"] == ()

    control_netlist = (fixture_root / "control-netlist.xml").read_text(encoding="utf-8")
    install_synthetic_netlist(native, control_netlist)
    control = compare()
    assert control.connector_coverage is not None
    assert control.connector_coverage.status == "COMPLETE"
    assert control.status == "PASS", [
        (item.rule_id, item.subject, item.disposition) for item in control.findings
    ]
    assert RULE_ID not in {item.rule_id for item in control.findings}

    _install_reviewed_interface(root, island, target_role="shield")
    install_synthetic_netlist(native, fault_netlist)
    shield_fault = compare()
    shield_findings = [item for item in shield_fault.findings if item.rule_id == SHIELD_RULE_ID]
    assert shield_fault.connector_coverage is not None
    assert shield_fault.connector_coverage.status == "COMPLETE"
    assert shield_fault.status == "REVIEW"
    assert len(shield_findings) == 1
    assert shield_findings[0].evidence["interface_role"] == ("shield",)
    assert shield_findings[0].evidence["assigned_nets"] == ()

    shield_control_netlist = control_netlist.replace("UART_RX", "CHASSIS")
    install_synthetic_netlist(native, shield_control_netlist)
    shield_control = compare()
    assert shield_control.status == "PASS", [
        (item.rule_id, item.subject, item.disposition) for item in shield_control.findings
    ]
    assert SHIELD_RULE_ID not in {item.rule_id for item in shield_control.findings}
