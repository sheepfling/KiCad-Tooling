"""CLI/MCP parity regressions for return-like net label groups."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    ProjectManifest,
)
from tests.design_lint_fixtures import four_db9_return_domains
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
    pytest.mark.return_path_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def test_ret_return_names_match_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
    )
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic DB9 parity fixture covers all four connector instances"
                )
            }
        ),
    )

    base = four_db9_return_domains()
    pins_by_port = {f"J{port}": (f"J{port}.7", f"J{port}.9") for port in range(1, 5)}
    components = {
        f"J{port}": ComponentContract(value="Synthetic DB9", footprint="Synthetic:DB9")
        for port in range(1, 5)
    }

    def install_return_nets(return_nets: Mapping[str, tuple[str, ...]]) -> None:
        observed = base.model_copy(update={"components": components, "nets": return_nets})
        install_synthetic_netlist(native, contract_netlist_xml(observed))

    async def exercise() -> None:
        async with Client(create_server(root), mode="legacy") as client:

            async def compare(
                return_nets: Mapping[str, tuple[str, ...]],
            ) -> DesignLintReport:
                install_return_nets(return_nets)
                process = run_design_lint_cli(tmp_path, root, native)
                assert process.returncode in {0, 1}, process.stderr + process.stdout
                cli = DesignLintReport.model_validate_json(process.stdout)
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
                assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
                assert process.returncode == (0 if cli.status == "PASS" else 1)
                return mcp

            numbered = await compare(
                {f"RET{port}": pins_by_port[f"J{port}"] for port in range(1, 5)}
            )
            assert "net.numbered_returns" in {item.rule_id for item in numbered.findings}

            unindexed = await compare(
                {
                    "RET_USB": pins_by_port["J1"],
                    "RET_SERIAL": pins_by_port["J2"],
                    "UNRELATED_C": pins_by_port["J3"],
                    "UNRELATED_D": pins_by_port["J4"],
                }
            )
            assert "net.return_labels_without_pin_roles" in {
                item.rule_id for item in unindexed.findings
            }

            common = await compare(
                {"RET": tuple(pin for pins in pins_by_port.values() for pin in pins)}
            )
            return_rule_ids = {"net.numbered_returns", "net.return_labels_without_pin_roles"}
            assert not return_rule_ids & {item.rule_id for item in common.findings}

    asyncio.run(exercise())
