"""Design-lint CLI/MCP parity cases: design lint mcp parity analog."""

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
    ComponentIdentity,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)
from tests.test_crystal_networks import crystal_map as synthetic_crystal_network_map
from tests.test_rc_filters import rc_filter_map as synthetic_rc_filter_map
from tests.test_regulator_feedback import (
    regulator_feedback_map as synthetic_regulator_feedback_map,
)


class _DesignLintMcpParityAnalogCases(McpParityHarness):
    async def _case_test_regulator_feedback_map_parity(self) -> None:
        """Compare the authored regulator-divider result through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, upper_value: str) -> None:
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>SYNTH-ADJ</value>'
                "<footprint>Synthetic:SOIC-8</footprint>"
                '<libsource lib="Synthetic" part="AdjustableRegulator"/></comp>'
                f'<comp ref="R1"><value>{upper_value}</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                '<comp ref="R2"><value>33k</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="AdjustableRegulator"><pins>'
                '<pin num="1" name="OUT" type="passive"/>'
                '<pin num="2" name="FB" type="input"/>'
                '<pin num="3" name="VIN" type="power_in"/>'
                '<pin num="4" name="GND" type="power_in"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="R"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="REG_OUT"><node ref="U1" pin="1"/>'
                '<node ref="R1" pin="1"/></net>'
                '<net name="FB"><node ref="U1" pin="2"/>'
                '<node ref="R1" pin="2"/><node ref="R2" pin="1"/></net>'
                '<net name="GND"><node ref="R2" pin="2"/>'
                '<node ref="U1" pin="4"/></net>'
                '<net name="VIN"><node ref="U1" pin="3"/></net>'
                "</nets></export>",
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

        write_netlist(upper_value="220k")
        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(required=False, part_ids=()),
                    "interfaces": (),
                    "connector_reviews": (),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic source has no external connector interfaces"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = DesignLintPolicy(regulator_feedback_map=synthetic_regulator_feedback_map())
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(expected_status: str, exit_code: int) -> DesignLintReport:
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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

            out_of_range = await compare("REVIEW", 1)
            entry = out_of_range.regulator_feedback_coverage.entries[0]
            self.assertEqual(entry.status, "OUT_OF_RANGE")
            self.assertEqual(entry.nominal_resistance_ohms["R1"], 220000.0)
            self.assertIn(
                "formula",
                next(
                    item.evidence
                    for item in out_of_range.findings
                    if item.rule_id == "power.regulator_feedback_mismatch"
                ),
            )

            blocking_policy = policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="power.regulator_feedback_mismatch",
                            mode="block",
                            reason="Synthetic output range is a reviewed requirement",
                        ),
                    )
                }
            )
            write_model(contract_path, contract.model_copy(update={"design_lint": blocking_policy}))
            blocked = await compare("FAIL", 1)
            self.assertEqual(
                next(
                    item
                    for item in blocked.findings
                    if item.rule_id == "power.regulator_feedback_mismatch"
                ).mode,
                "block",
            )

    async def _case_test_rc_filter_map_parity(self) -> None:
        """Compare an authored RC filter and a source value mutation through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, capacitor_value: str) -> None:
            netlist.write_text(
                "<export><components>"
                '<comp ref="R1"><value>1k</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                f'<comp ref="C1"><value>{capacitor_value}</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="C"/></comp>'
                "</components><libparts>"
                '<libpart lib="Device" part="R"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="C"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="FILTER_IN"><node ref="R1" pin="1"/></net>'
                '<net name="FILTER_OUT"><node ref="R1" pin="2"/>'
                '<node ref="C1" pin="1"/></net>'
                '<net name="GND"><node ref="C1" pin="2"/></net>'
                "</nets></export>",
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

        write_netlist(capacitor_value="100nF")
        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(required=False, part_ids=()),
                    "interfaces": (),
                    "connector_reviews": (),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic source has no external connector interfaces"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = DesignLintPolicy(rc_filter_map=synthetic_rc_filter_map())
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(expected_status: str, exit_code: int) -> DesignLintReport:
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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

            complete = await compare("PASS", 0)
            self.assertEqual(complete.rc_filter_coverage.entries[0].status, "COMPLETE")
            self.assertAlmostEqual(
                complete.rc_filter_coverage.entries[0].calculated_corner_hz or 0,
                1591.55,
                delta=0.02,
            )

            write_netlist(capacitor_value="220nF")
            changed = await compare("REVIEW", 1)
            self.assertEqual(changed.rc_filter_coverage.entries[0].status, "OUT_OF_RANGE")
            self.assertTrue(
                any(item.rule_id == "filter.rc_corner_mismatch" for item in changed.findings)
            )

    async def _case_test_crystal_network_map_parity(self) -> None:
        """Compare source-bound crystal topology and load evidence through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="U1"><value>Synthetic MCU</value>'
            "<footprint>Synthetic:SOIC-8</footprint>"
            '<libsource lib="Synthetic" part="Oscillator"/></comp>'
            '<comp ref="Y1"><value>Synthetic 16 MHz crystal</value>'
            "<footprint>Synthetic:Crystal-3225</footprint>"
            '<libsource lib="Device" part="Crystal"/></comp>'
            '<comp ref="C1"><value>18pF</value><footprint>Synthetic:0603</footprint>'
            '<libsource lib="Device" part="C"/></comp>'
            '<comp ref="C2"><value>18pF</value><footprint>Synthetic:0603</footprint>'
            '<libsource lib="Device" part="C"/></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="Oscillator"><pins>'
            '<pin num="1" name="XTAL_IN" type="input"/>'
            '<pin num="2" name="XTAL_OUT" type="output"/>'
            "</pins></libpart>"
            '<libpart lib="Device" part="Crystal"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/>'
            "</pins></libpart>"
            '<libpart lib="Device" part="C"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="OSC_IN"><node ref="U1" pin="1"/>'
            '<node ref="Y1" pin="1"/><node ref="C1" pin="1"/></net>'
            '<net name="OSC_OUT"><node ref="U1" pin="2"/>'
            '<node ref="Y1" pin="2"/><node ref="C2" pin="1"/></net>'
            '<net name="GND"><node ref="C1" pin="2"/><node ref="C2" pin="2"/></net>'
            "</nets></export>",
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

        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        crystal_network_map=synthetic_crystal_network_map()
                    )
                }
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(expected_status: str, exit_code: int) -> DesignLintReport:
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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

            matched = await compare("PASS", 0)
            self.assertEqual(matched.crystal_network_coverage.status, "COMPLETE")
            self.assertEqual(matched.crystal_network_coverage.netlist_sha256, digest(netlist))
            entry = matched.crystal_network_coverage.entries[0]
            self.assertEqual(entry.status, "COMPLETE")
            self.assertEqual(entry.calculated_minimum_load_pf, 10.0)
            self.assertEqual(entry.calculated_maximum_load_pf, 12.0)

            netlist.write_text(
                netlist.read_text(encoding="utf-8").replace(
                    '<net name="OSC_IN"><node ref="U1" pin="1"/>'
                    '<node ref="Y1" pin="1"/><node ref="C1" pin="1"/>'
                    '</net><net name="OSC_OUT"><node ref="U1" pin="2"/>'
                    '<node ref="Y1" pin="2"/><node ref="C2" pin="1"/></net>',
                    '<net name="OSC_IN"><node ref="U1" pin="1"/>'
                    '<node ref="Y1" pin="1"/><node ref="C1" pin="1"/>'
                    '<node ref="C2" pin="1"/></net>'
                    '<net name="OSC_OUT"><node ref="U1" pin="2"/>'
                    '<node ref="Y1" pin="2"/></net>',
                ),
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
            mismatched = await compare("REVIEW", 1)
            self.assertEqual(mismatched.crystal_network_coverage.entries[0].status, "INCOMPLETE")
            self.assertTrue(
                any(
                    finding.rule_id == "oscillator.crystal_load_network_mismatch"
                    for finding in mismatched.findings
                )
            )


def test_regulator_feedback_map_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityAnalogCases, "_case_test_regulator_feedback_map_parity")


def test_rc_filter_map_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityAnalogCases, "_case_test_rc_filter_map_parity")


def test_crystal_network_map_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityAnalogCases, "_case_test_crystal_network_map_parity")
