"""CLI/MCP parity for source-mapped connector contacts sharing native nets."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Literal

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_connector_mapped_contact_sharing_candidate_evidence import (
    MappedContactSharingRuleId,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    NetlistContract,
    ProjectManifest,
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
    pytest.mark.evidence_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]

SHIELD_RULE_ID = "connector.mapped_shield_signal_share_net"
RETURN_RULE_ID = "connector.mapped_signal_return_share_net"
INTERFACE_ID = "synthetic-mapped-contact-sharing"
_ROLES: tuple[tuple[Literal["shield", "return"], str, MappedContactSharingRuleId, str], ...] = (
    ("shield", "CHASSIS_SHIELD", SHIELD_RULE_ID, "shield_component_pin"),
    ("return", "SIGNAL_RETURN", RETURN_RULE_ID, "return_component_pin"),
)


def _install_reviewed_contact_interface(
    root: Path,
    *,
    primary_role: Literal["shield", "return"],
    primary_signal: str,
) -> Path:
    primary_voltage = "chassis" if primary_role == "shield" else "signal-return"
    interface = InterfaceRecord(
        id=INTERFACE_ID,
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal=primary_signal,
                role=primary_role,
                direction="passive",
                voltage_domain=primary_voltage,
                mating=primary_signal,
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="UART_RX",
                role="signal",
                direction="input",
                voltage_domain="logic-3v3",
                mating="UART_TX",
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
    manifest_path = root / "projects/controller/project.json"
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
                        basis="Synthetic independently reviewed connector pinout",
                        interface_id=INTERFACE_ID,
                        pin_map={"1": "1", "2": "2"},
                    ),
                ),
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic review covers the complete connector inventory"
                ),
            }
        ),
    )
    return catalog_path


@pytest.mark.design_lint_rule(rule_id=SHIELD_RULE_ID)
@pytest.mark.design_lint_rule(rule_id=RETURN_RULE_ID)
def test_mapped_contact_sharing_findings_match_between_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
    )
    observed = NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic connector", footprint="Synthetic:2Pin")
        },
        nets={"SHARED_SIGNAL_NET": ("J1.1", "J1.2")},
        component_symbols={"J1": "Connector_Generic:Conn_02"},
        component_pin_numbers={"J1": ("1", "2")},
        pin_functions={"J1.1": "Pin_1", "J1.2": "Pin_2"},
        pin_electrical_types={"J1.1": "passive", "J1.2": "passive"},
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

    for role, signal, rule_id, primary_key in _ROLES:
        catalog_path = _install_reviewed_contact_interface(
            root,
            primary_role=role,
            primary_signal=signal,
        )
        install_synthetic_netlist(native, contract_netlist_xml(observed))
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli_report = DesignLintReport.model_validate_json(process.stdout)
        mcp_report = asyncio.run(inspect_mcp())

        assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
        assert cli_report.connector_coverage is not None
        assert cli_report.connector_coverage.status == "COMPLETE"
        assert cli_report.connector_coverage.interface_catalog_sha256 == digest(catalog_path)
        (finding,) = tuple(item for item in cli_report.findings if item.rule_id == rule_id)
        assert finding.evidence[primary_key] == ("J1.1",)
        assert finding.evidence["signal_component_pin"] == ("J1.2",)
        assert finding.evidence["assigned_net"] == ("SHARED_SIGNAL_NET",)
        assert finding.evidence["interface_catalog_sha256"] == (digest(catalog_path),)
