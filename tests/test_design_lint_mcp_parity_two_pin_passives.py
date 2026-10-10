"""Design-lint CLI/MCP parity cases: design lint mcp parity two pin passives."""

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


class _DesignLintMcpParityTwoPinPassivesCases(McpParityHarness):
    async def _case_test_same_net_two_pin_passive_lint_cli_mcp_parity(self) -> None:
        """Compare the same-net review finding and its distinct-net control."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="R1" pin="1"/>'
                nets += '<node ref="R1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="INPUT"><node ref="R1" pin="1"/></net>'
                    '<net name="OUTPUT"><node ref="R1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="R1"><value>10k</value><footprint>Synthetic:R_0603</footprint>'
                '<libsource lib="Device" part="R"/></comp>'
                '</components><libparts><libpart lib="Device" part="R"><pins>'
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
                if item.rule_id == "component.two_pin_passive_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"],
                (
                    "R1.1 -> SHARED",
                    "R1.2 -> SHARED",
                ),
            )
            self.assertEqual(finding.evidence["symbol"], ("Device:R",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_passive_same_net",
                {item.rule_id for item in control.findings},
            )

    async def _case_test_same_net_two_pin_diode_lint_cli_mcp_parity(self) -> None:
        """Compare the same-net diode review finding and distinct-net control."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="D1" pin="1"/>'
                nets += '<node ref="D1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="ANODE"><node ref="D1" pin="1"/></net>'
                    '<net name="CATHODE"><node ref="D1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="D1"><value>1N4148</value>'
                "<footprint>Synthetic:SOD-123</footprint>"
                '<libsource lib="Device" part="D"/></comp>'
                '</components><libparts><libpart lib="Device" part="D"><pins>'
                '<pin num="1" name="A" type="passive"/>'
                '<pin num="2" name="K" type="passive"/>'
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
                if item.rule_id == "component.two_pin_diode_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"],
                ("D1.1 -> SHARED", "D1.2 -> SHARED"),
            )
            self.assertEqual(finding.evidence["symbol"], ("Device:D",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_diode_same_net",
                {item.rule_id for item in control.findings},
            )

    async def _case_test_same_net_two_pin_ferrite_lint_cli_mcp_parity(self) -> None:
        """Compare the ferrite bypass hint and distinct-net control on both surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="FB1" pin="1"/>'
                nets += '<node ref="FB1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="INPUT"><node ref="FB1" pin="1"/></net>'
                    '<net name="OUTPUT"><node ref="FB1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="FB1"><value>600R@100MHz</value>'
                "<footprint>Synthetic:Ferrite_0603</footprint>"
                '<libsource lib="Device" part="FerriteBead"/></comp>'
                '</components><libparts><libpart lib="Device" part="FerriteBead"><pins>'
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
                if item.rule_id == "component.two_pin_ferrite_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"],
                ("FB1.1 -> SHARED", "FB1.2 -> SHARED"),
            )
            self.assertEqual(finding.evidence["symbol"], ("Device:FerriteBead",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_ferrite_same_net",
                {item.rule_id for item in control.findings},
            )

    async def _case_test_same_net_two_pin_switch_lint_cli_mcp_parity(self) -> None:
        """Compare exact SPST bypass review and the distinct-net control on both surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="SW1" pin="1"/>'
                nets += '<node ref="SW1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="INPUT"><node ref="SW1" pin="1"/></net>'
                    '<net name="OUTPUT"><node ref="SW1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="SW1"><value>Synthetic SPST</value>'
                "<footprint>Synthetic:SPST_THT</footprint>"
                '<libsource lib="Switch" part="SW_SPST"/></comp>'
                "</components><libparts>"
                '<libpart lib="Switch" part="SW_SPST"><pins>'
                '<pin num="1" name="A" type="passive"/>'
                '<pin num="2" name="B" type="passive"/>'
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

            write_netlist(same_net=True)
            fault = await compare()
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "component.two_pin_switch_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"], ("SW1.1 -> SHARED", "SW1.2 -> SHARED")
            )
            self.assertEqual(finding.evidence["symbol"], ("Switch:SW_SPST",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_switch_same_net",
                {item.rule_id for item in control.findings},
            )


def test_same_net_two_pin_passive_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityTwoPinPassivesCases,
        "_case_test_same_net_two_pin_passive_lint_cli_mcp_parity",
    )


def test_same_net_two_pin_diode_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityTwoPinPassivesCases,
        "_case_test_same_net_two_pin_diode_lint_cli_mcp_parity",
    )


def test_same_net_two_pin_ferrite_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityTwoPinPassivesCases,
        "_case_test_same_net_two_pin_ferrite_lint_cli_mcp_parity",
    )


def test_same_net_two_pin_switch_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityTwoPinPassivesCases,
        "_case_test_same_net_two_pin_switch_lint_cli_mcp_parity",
    )
