"""Keep named mapped peer-supply findings identical through CLI and MCP."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    ProjectManifest,
)
from tests.design_lint_fixtures.connector_mapped_peer_supply_split import (
    mapped_peer_supply_netlist,
)
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
    pytest.mark.evidence_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]

RULE_ID = "connector.mapped_named_peer_supply_split_nets"


def _install_peer_supply_map(root: Path) -> Path:
    interfaces = tuple(
        InterfaceRecord(
            id=f"synthetic-{reference.casefold()}-supply-port",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal=f"POWER_{reference}",
                    role="supply",
                    direction="passive",
                    voltage_domain="board-input",
                    mating=f"POWER_{reference}",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        )
        for reference in ("J1", "J2")
    )
    catalog_path = root / "catalog/interfaces.json"
    write_model(catalog_path, InterfacesCatalog(schema_version="1", interfaces=interfaces))
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "interfaces": tuple(item.id for item in interfaces),
                "connector_reviews": tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="interface",
                        basis="Synthetic independently reviewed connector supply map",
                        interface_id=f"synthetic-{reference.casefold()}-supply-port",
                        pin_map={"1": "1"},
                        supply_comparison_group="external-power",
                        supply_comparison_basis=(
                            "Synthetic reviewer selected these supply peers for comparison"
                        ),
                    )
                    for reference in ("J1", "J2")
                ),
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic review covered both connector references"
                ),
            }
        ),
    )
    return catalog_path


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_peer_supply_split_findings_match_between_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
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

    for case, assignments in (
        ("fault", (("NODE_ALPHA",), ("NODE_BETA",))),
        ("control", (("COMMON_NODE",), ("COMMON_NODE",))),
    ):
        catalog_path = _install_peer_supply_map(root)
        observed = mapped_peer_supply_netlist(assignments=assignments)
        install_synthetic_netlist(native, contract_netlist_xml(observed))
        cli_process = run_design_lint_cli(tmp_path, root, native)
        assert cli_process.returncode in {0, 1}, cli_process.stderr + cli_process.stdout
        cli_report = DesignLintReport.model_validate_json(cli_process.stdout)
        mcp_report = asyncio.run(inspect_mcp())

        assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
        assert cli_report.connector_coverage is not None
        assert cli_report.connector_coverage.status == "COMPLETE"
        assert cli_report.connector_coverage.interface_catalog_sha256 == digest(catalog_path)
        findings = tuple(item for item in cli_report.findings if item.rule_id == RULE_ID)
        if case == "fault":
            (finding,) = findings
            assert finding.evidence["connector_references"] == ("J1", "J2")
            assert finding.evidence["split_native_nets"] == ("NODE_ALPHA", "NODE_BETA")
        else:
            assert not findings
