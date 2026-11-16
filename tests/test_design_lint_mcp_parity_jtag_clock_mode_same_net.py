"""CLI and MCP report parity for the JTAG TCK/TMS same-net heuristic."""

from __future__ import annotations

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ProjectTestContract,
    ValidationSummary,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures.jtag_clock_mode_same_net import (
    jtag_clock_mode_same_net_netlist,
)
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt

RULE_ID = "bus.jtag_tck_tms_same_net"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


class _JtagClockModeSameNetParity(McpParityHarness):
    async def _case_jtag_clock_mode_same_net_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = jtag_clock_mode_same_net_netlist()
        netlist_path = native.parent / "netlist.xml"
        netlist_path.write_text(peer_pin_netlist_xml(netlist), encoding="utf-8")
        self.rehash_native_netlist(native)
        native_summary = read_model(native, ValidationSummary)
        install_source_bound_drc_receipt(
            self.root,
            native,
            board_path=self.island / "kicad/controller.kicad_pcb",
            kicad_version=native_summary.checks["toolchain"].observed_version,
        )

        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = contract.design_lint or DesignLintPolicy()
        overrides = {item.rule_id: item for item in policy.rules}
        overrides[RULE_ID] = DesignLintRuleOverride(
            rule_id=RULE_ID,
            mode="review",
            reason="Exercise the synthetic JTAG TCK/TMS same-net heuristic.",
        )
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": policy.model_copy(
                        update={"rules": tuple(overrides[key] for key in sorted(overrides))}
                    )
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
        findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
        assert tuple(item.subject for item in findings) == (
            "U1: JTAG TCK U1.1 and TMS U1.2 share JTAG_CLOCK_MODE_SHARED",
        )


def test_jtag_clock_mode_same_net_cli_mcp_parity() -> None:
    run_mcp_parity(
        _JtagClockModeSameNetParity,
        "_case_jtag_clock_mode_same_net_cli_mcp_parity",
    )
