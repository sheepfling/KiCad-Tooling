"""CLI/MCP parity regressions for return-like net label groups."""

from __future__ import annotations

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ComponentContract, DesignLintReport
from tests.design_lint_fixtures import four_db9_return_domains
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.return_path_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


class _ReturnLabelParityCases(McpParityHarness):
    async def _case_test_ret_return_names_match_cli_and_mcp(self) -> None:
        native = self.native_evidence()
        netlist_path = native.parent / "netlist.xml"
        base = four_db9_return_domains()
        pins_by_port = {f"J{port}": (f"J{port}.7", f"J{port}.9") for port in range(1, 5)}
        components = {
            **{
                f"J{port}": ComponentContract(value="Synthetic DB9", footprint="Synthetic:DB9")
                for port in range(1, 5)
            },
            "R1": ComponentContract(
                value="1k", footprint="Synthetic:R_0603", part_id="resistor-1k"
            ),
        }

        def write_netlist(return_nets: dict[str, tuple[str, ...]]) -> None:
            observed = base.model_copy(
                update={
                    "nets": {
                        **return_nets,
                        "UNRELATED_A": ("R1.1",),
                        "UNRELATED_B": ("R1.2",),
                    },
                    "components": components,
                    "component_symbols": {**base.component_symbols, "R1": "Device:R"},
                    "component_pin_numbers": {**base.component_pin_numbers, "R1": ("1", "2")},
                    "pin_functions": {
                        **base.pin_functions,
                        "R1.1": "1",
                        "R1.2": "2",
                    },
                }
            )
            netlist_path.write_text(contract_netlist_xml(observed), encoding="utf-8")
            self.rehash_native_netlist(native)

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(return_nets: dict[str, tuple[str, ...]]) -> DesignLintReport:
                write_netlist(return_nets)
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

            numbered = await compare(
                {f"RET{port}": pins_by_port[f"J{port}"] for port in range(1, 5)}
            )
            self.assertIn("net.numbered_returns", {item.rule_id for item in numbered.findings})

            unindexed = await compare(
                {
                    "RET_USB": pins_by_port["J1"],
                    "RET_SERIAL": pins_by_port["J2"],
                    "UNRELATED_C": pins_by_port["J3"],
                    "UNRELATED_D": pins_by_port["J4"],
                }
            )
            self.assertIn(
                "net.return_labels_without_pin_roles",
                {item.rule_id for item in unindexed.findings},
            )

            common = await compare(
                {"RET": tuple(pin for pins in pins_by_port.values() for pin in pins)}
            )
            return_rule_ids = {"net.numbered_returns", "net.return_labels_without_pin_roles"}
            self.assertFalse(return_rule_ids & {item.rule_id for item in common.findings})


def test_ret_return_names_match_cli_and_mcp() -> None:
    run_mcp_parity(
        _ReturnLabelParityCases,
        "_case_test_ret_return_names_match_cli_and_mcp",
    )
