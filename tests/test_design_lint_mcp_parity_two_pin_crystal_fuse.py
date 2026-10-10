"""Design-lint CLI/MCP parity cases: design lint mcp parity two pin crystal fuse."""

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
    parse_model_text,
    read_model,
    write_model,
)
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


class _DesignLintMcpParityTwoPinCrystalFuseCases(McpParityHarness):
    async def _case_test_same_net_two_pin_crystal_lint_cli_mcp_parity(self) -> None:
        """Compare the same-net crystal review finding and distinct-net control."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="Y1" pin="1"/>'
                nets += '<node ref="Y1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="XTAL_IN"><node ref="Y1" pin="1"/></net>'
                    '<net name="XTAL_OUT"><node ref="Y1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="Y1"><value>16 MHz</value>'
                "<footprint>Synthetic:Crystal</footprint>"
                '<libsource lib="Device" part="Crystal"/></comp>'
                '</components><libparts><libpart lib="Device" part="Crystal"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                f"</pins></libpart></libparts><nets>{nets}</nets></export>",
                encoding="utf-8",
            )
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

        write_netlist(same_net=True)
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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
                return mcp

            fault = await compare()
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "component.two_pin_crystal_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"],
                ("Y1.1 -> SHARED", "Y1.2 -> SHARED"),
            )
            self.assertEqual(finding.evidence["symbol"], ("Device:Crystal",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_crystal_same_net",
                {item.rule_id for item in control.findings},
            )

    async def _case_test_same_net_two_pin_fuse_lint_cli_mcp_parity(self) -> None:
        """Compare the same-net fuse review finding and distinct-net control."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="F1" pin="1"/>'
                nets += '<node ref="F1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="INPUT"><node ref="F1" pin="1"/></net>'
                    '<net name="OUTPUT"><node ref="F1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="F1"><value>1A</value><footprint>Synthetic:Fuse_1206</footprint>'
                '<libsource lib="Device" part="Fuse"/></comp>'
                '</components><libparts><libpart lib="Device" part="Fuse"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                f"</pins></libpart></libparts><nets>{nets}</nets></export>",
                encoding="utf-8",
            )
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

        write_netlist(same_net=True)
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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
                return mcp

            fault = await compare()
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item for item in fault.findings if item.rule_id == "component.two_pin_fuse_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"],
                ("F1.1 -> SHARED", "F1.2 -> SHARED"),
            )
            self.assertEqual(finding.evidence["symbol"], ("Device:Fuse",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_fuse_same_net",
                {item.rule_id for item in control.findings},
            )


def test_same_net_two_pin_crystal_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityTwoPinCrystalFuseCases,
        "_case_test_same_net_two_pin_crystal_lint_cli_mcp_parity",
    )


def test_same_net_two_pin_fuse_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityTwoPinCrystalFuseCases,
        "_case_test_same_net_two_pin_fuse_lint_cli_mcp_parity",
    )
