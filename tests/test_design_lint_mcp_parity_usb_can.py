"""Design-lint CLI/MCP parity cases: design lint mcp parity usb can."""

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


class _DesignLintMcpParityCanCases(McpParityHarness):
    async def _case_test_can_peer_pair_divergence_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            """<export>
  <components>
    <comp ref="U1"><value>Synthetic CAN node</value><libsource lib="Synthetic" part="CanNode"/></comp>
    <comp ref="U2"><value>Synthetic CAN node</value><libsource lib="Synthetic" part="CanNode"/></comp>
    <comp ref="U3"><value>Synthetic CAN node</value><libsource lib="Synthetic" part="CanNode"/></comp>
    <comp ref="R1"><value>120R</value><libsource lib="Device" part="R"/></comp>
    <comp ref="R2"><value>120R</value><libsource lib="Device" part="R"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="CanNode"><pins>
      <pin num="1" name="CANH" type="passive"/>
      <pin num="2" name="CAN_L" type="passive"/>
    </pins></libpart>
    <libpart lib="Device" part="R"><pins>
      <pin num="1" name="~" type="passive"/>
      <pin num="2" name="~" type="passive"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="NET_A"><node ref="U1" pin="1"/><node ref="U2" pin="1"/>
      <node ref="U3" pin="1"/><node ref="R1" pin="1"/><node ref="R2" pin="1"/></net>
    <net name="NET_B"><node ref="U1" pin="2"/><node ref="U2" pin="2"/>
      <node ref="R1" pin="2"/></net>
    <net name="NET_C"><node ref="U3" pin="2"/><node ref="R2" pin="2"/></net>
  </nets>
</export>
""",
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
        self.assertEqual(mcp.status, "REVIEW")
        self.assertEqual(
            {item.rule_id for item in mcp.findings},
            {"bus.can_peer_assignment_divergence"},
        )
        finding = mcp.findings[0]
        self.assertEqual(finding.evidence["shared_net"], ("NET_A",))
        self.assertEqual(finding.evidence["complementary_nets"], ("NET_B", "NET_C"))


def test_can_peer_pair_divergence_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityCanCases, "_case_test_can_peer_pair_divergence_lint_cli_mcp_parity"
    )
