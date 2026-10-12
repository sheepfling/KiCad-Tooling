"""Shared source-bound setup for design-lint CLI/MCP report parity tests."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.models import (
    ComplementaryPinFunctionAlias,
    ComplementaryPinFunctionAliasMap,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ProjectTestContract,
)
from tests.mcp_parity_support import McpParityHarness, comprehensive_lint_netlist


class DesignLintMcpParityReportHarness(McpParityHarness):
    def install_comprehensive_lint_report(self) -> tuple[Path, Path]:
        """Install the tooling-owned report netlist and scoped review policy."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(comprehensive_lint_netlist(), encoding="utf-8")
        self.rehash_native_netlist(native)

        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        pcb_rules = (
            "pcb.schematic_component_inventory",
            "pcb.schematic_pcb_dnp_mismatch",
            "pcb.schematic_pcb_value_mismatch",
            "pcb.schematic_pcb_pad_net_mismatch",
        )
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=tuple(
                            DesignLintRuleOverride(
                                rule_id=rule_id,
                                mode="off",
                                reason="Synthetic report parity has no native PCB snapshot evidence",
                            )
                            for rule_id in pcb_rules
                        ),
                        complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                            entries=(
                                ComplementaryPinFunctionAlias(
                                    symbol="Synthetic:VendorDifferentialDevice",
                                    family="vendor data lane 0",
                                    positive_functions=("OUTP",),
                                    negative_functions=("OUTN",),
                                    basis=(
                                        "Synthetic fixture explicitly defines these native "
                                        "pin functions as a pair"
                                    ),
                                ),
                            )
                        ),
                    )
                }
            ),
        )
        return native, netlist

    async def compare_lint_report(
        self,
        client,
        native: Path,
        expected_status: str,
        expected_exit: int,
    ) -> DesignLintReport:
        cli = await self.cli(
            "kicad_tooling.design_lint",
            DesignLintReport,
            "--project",
            "controller",
            "--native-summary",
            str(native),
            expected_exit=expected_exit,
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
        self.assertEqual(mcp.status, expected_status, mcp.issues)
        return mcp
