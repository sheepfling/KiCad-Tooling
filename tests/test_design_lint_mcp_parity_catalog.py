"""Design-lint CLI/MCP parity cases: design lint mcp parity catalog."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.design_lint_rule_models import DesignLintRuleCatalog
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintReport,
    ValidationSummary,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _DesignLintMcpParityCatalogCases(McpParityHarness):
    async def _case_test_design_lint_rule_catalog_cli_mcp_parity(self) -> None:
        """List identical typed rules without requiring project or native evidence."""
        async with Client(create_server(self.root), mode="legacy") as client:
            cli = await self.cli(
                "kicad_tooling.design_lint",
                DesignLintRuleCatalog,
                "--catalog",
            )
            mcp = await self.call(
                client,
                "list_design_lint_rules",
                DesignLintRuleCatalog,
            )
        self.assertEqual(cli, mcp)
        self.assertTrue(cli.rules)
        self.assertEqual(cli.sha256, mcp.sha256)

    async def _case_test_empty_native_netlist_blocks_design_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text("<export><components/><nets/></export>", encoding="utf-8")
        summary = read_model(native, ValidationSummary)
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

        async with Client(create_server(self.root), mode="legacy") as client:
            cli = await self.cli(
                "kicad_tooling.design_lint",
                DesignLintReport,
                "--project",
                "controller",
                "--native-summary",
                str(native),
                expected_exit=1,
            )
            mcp = await self.call(
                client,
                "inspect_design_lint",
                DesignLintReport,
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(self.root).as_posix(),
                },
            )

        self.assertEqual(cli, mcp)
        self.assertEqual(mcp.status, "BLOCKED")
        self.assertIn("contains no component records", mcp.issues[0])
        self.assertFalse(mcp.findings)
        self.assertIsNone(mcp.netlist_sha256)


def test_design_lint_rule_catalog_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityCatalogCases, "_case_test_design_lint_rule_catalog_cli_mcp_parity"
    )


def test_empty_native_netlist_blocks_design_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityCatalogCases,
        "_case_test_empty_native_netlist_blocks_design_lint_cli_mcp_parity",
    )
