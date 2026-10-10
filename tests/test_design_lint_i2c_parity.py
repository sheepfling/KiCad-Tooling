"""Cross-surface parity checks for the selected interface lint theme."""

from __future__ import annotations

import pytest
from mcp import Client

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from tests.design_lint_fixtures.i2c_serial_parity import PROJECT_ID
from tests.design_lint_fixtures.parity_harness import I2cSerialParityHarness

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.parity_lint]


class DesignLintI2cParityTests(I2cSerialParityHarness):
    async def test_mapped_array_control_and_missing_array_fault_match_cli_and_mcp(self) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            self._write_native_evidence(missing_array=False)
            control = await self._inspect_both_surfaces(client)
            self.assertEqual(control.i2c_pullup_heuristic_coverage.status, "COMPLETE")
            self.assertEqual(
                control.i2c_pullup_heuristic_coverage.netlist_sha256,
                digest(self.netlist_path),
            )
            self.assertEqual(
                control.i2c_pullup_heuristic_coverage.entries[0].check_ids,
                ("i2c-pullup/main/sda", "i2c-pullup/main/scl"),
            )
            self.assertNotIn("bus.i2c_missing_pullup", {item.rule_id for item in control.findings})
            serial_findings = [
                item for item in control.findings if item.rule_id == "bus.serial_unmapped_peer"
            ]
            self.assertEqual(
                tuple(item.subject for item in serial_findings),
                ("J3: serial-peer map coverage (TX/RX)",),
            )
            self.assertIn("not listed in the project serial-peer map", serial_findings[0].message)
            self.assertEqual(
                serial_findings[0].evidence["electrical_contract_path"],
                (f"projects/{PROJECT_ID}/tests/electrical.json",),
            )
            self.assertEqual(
                serial_findings[0].evidence["electrical_contract_sha256"],
                (digest(self.island / "tests" / "electrical.json"),),
            )

            self._write_native_evidence(missing_array=True)
            fault = await self._inspect_both_surfaces(client)
            self.assertEqual(fault.i2c_pullup_heuristic_coverage.status, "OPEN")
            self.assertEqual(
                fault.i2c_pullup_heuristic_coverage.netlist_sha256,
                digest(self.netlist_path),
            )
            self.assertIn("bus.i2c_missing_pullup", {item.rule_id for item in fault.findings})
            self.assertEqual(
                tuple(
                    item.subject
                    for item in fault.findings
                    if item.rule_id == "bus.serial_unmapped_peer"
                ),
                ("J3: serial-peer map coverage (TX/RX)",),
            )
            await self._check_surface_registration()
