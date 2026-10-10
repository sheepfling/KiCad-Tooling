"""Design-lint CLI/MCP parity cases: design lint mcp parity schematic connectivity."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

from pathlib import Path

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ProjectManifest,
    ProjectTestContract,
    ToolchainsCatalog,
    ValidationSummary,
)
from tests import test_parts_workflow as native_fixture
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _DesignLintMcpParitySchematicConnectivityCases(McpParityHarness):
    async def _case_test_schematic_pin_tip_on_wire_interior_cli_mcp_parity(self) -> None:
        schematic = self.island / "kicad/controller.kicad_sch"
        schematic.write_bytes(
            (
                Path(__file__).parent
                / "fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch"
            ).read_bytes()
        )

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.6"}))
        toolchains_path = self.root / "catalog/toolchains.json"
        toolchains = read_model(toolchains_path, ToolchainsCatalog)
        toolchain_10_0_6 = toolchains.toolchains[0].model_copy(
            update={
                "id": "kicad-10.0.6",
                "kicad_version": "10.0.6",
                "image": f"registry.invalid/kicad:10.0.6@sha256:{'a' * 64}",
            }
        )
        write_model(
            toolchains_path,
            toolchains.model_copy(
                update={"toolchains": (*toolchains.toolchains, toolchain_10_0_6)}
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.pin_tip_on_wire_interior",
                                mode="review",
                                reason="Synthetic parity fixture opts in to wire-interior review",
                            ),
                        )
                    )
                }
            ),
        )

        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            native_fixture.NETLIST.replace(
                "<nets/>",
                '<nets><net name="unconnected-(R1-Pad1)"><node ref="R1" pin="1"/></net></nets>',
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
        self.assertEqual(mcp.status, "REVIEW", mcp.model_dump_json(indent=2))
        self.assertEqual(
            mcp.schematic_geometry.status,
            "COMPLETE",
            mcp.schematic_geometry.model_dump_json(indent=2),
        )
        self.assertEqual(mcp.schematic_geometry.mode, "review")
        self.assertEqual(
            mcp.schematic_geometry.rule_modes["schematic.pin_tip_on_wire_interior"],
            "review",
        )
        self.assertEqual(mcp.schematic_geometry.finding_count, 1)
        findings = [
            item for item in mcp.findings if item.rule_id == "schematic.pin_tip_on_wire_interior"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence["pin"], ("R1.1",))
        self.assertEqual(findings[0].evidence["wire_segment_start_mm"], ("50.800000,71.120000",))
        self.assertEqual(findings[0].evidence["wire_segment_end_mm"], ("101.600000,71.120000",))

    async def _case_test_schematic_label_near_wire_endpoint_cli_mcp_parity(self) -> None:
        schematic = self.island / "kicad/controller.kicad_sch"
        schematic.write_bytes(
            (
                Path(__file__).parent / "fixtures/design_lint/label-near-wire-endpoint.kicad_sch"
            ).read_bytes()
        )

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.6"}))
        toolchains_path = self.root / "catalog/toolchains.json"
        toolchains = read_model(toolchains_path, ToolchainsCatalog)
        toolchain_10_0_6 = toolchains.toolchains[0].model_copy(
            update={
                "id": "kicad-10.0.6",
                "kicad_version": "10.0.6",
                "image": f"registry.invalid/kicad:10.0.6@sha256:{'a' * 64}",
            }
        )
        write_model(
            toolchains_path,
            toolchains.model_copy(
                update={"toolchains": (*toolchains.toolchains, toolchain_10_0_6)}
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.label_near_wire_endpoint",
                                mode="review",
                                reason="Synthetic parity fixture opts in to label localization",
                            ),
                        )
                    )
                }
            ),
        )

        native = self.native_evidence()
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
        self.assertEqual(mcp.status, "REVIEW", mcp.model_dump_json(indent=2))
        self.assertEqual(
            mcp.schematic_geometry.status,
            "COMPLETE",
            mcp.schematic_geometry.model_dump_json(indent=2),
        )
        self.assertEqual(mcp.schematic_geometry.mode, "review")
        self.assertEqual(
            mcp.schematic_geometry.rule_modes["schematic.label_near_wire_endpoint"], "review"
        )
        findings = [
            item for item in mcp.findings if item.rule_id == "schematic.label_near_wire_endpoint"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].evidence["label_uuid"], ("b0000000-0000-4000-8000-000000000006",)
        )
        self.assertEqual(
            findings[0].evidence["near_wire_endpoints"],
            ("b0000000-0000-4000-8000-000000000005@101.600000,71.120000 (0.500000 mm)",),
        )

    async def _case_test_schematic_wire_endpoint_near_pin_tip_cli_mcp_parity(self) -> None:
        schematic = self.island / "kicad/controller.kicad_sch"
        schematic.write_bytes(
            (
                Path(__file__).parent / "fixtures/design_lint/wire-end-near-pin-tip.kicad_sch"
            ).read_bytes()
        )
        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.6"}))
        toolchains_path = self.root / "catalog/toolchains.json"
        toolchains = read_model(toolchains_path, ToolchainsCatalog)
        toolchain_10_0_6 = toolchains.toolchains[0].model_copy(
            update={
                "id": "kicad-10.0.6",
                "kicad_version": "10.0.6",
                "image": f"registry.invalid/kicad:10.0.6@sha256:{'a' * 64}",
            }
        )
        write_model(
            toolchains_path,
            toolchains.model_copy(
                update={"toolchains": (*toolchains.toolchains, toolchain_10_0_6)}
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_endpoint_near_pin_tip",
                                mode="review",
                                reason="Synthetic parity fixture opts in to wire near-miss review",
                            ),
                        )
                    )
                }
            ),
        )

        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            native_fixture.NETLIST.replace(
                "<nets/>",
                '<nets><net name="unconnected-(R1-Pad1)"><node ref="R1" pin="1"/></net></nets>',
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
        self.assertEqual(mcp.status, "REVIEW", mcp.model_dump_json(indent=2))
        self.assertEqual(mcp.schematic_geometry.status, "COMPLETE")
        self.assertEqual(mcp.schematic_geometry.mode, "review")
        self.assertEqual(
            mcp.schematic_geometry.rule_modes["schematic.wire_endpoint_near_pin_tip"],
            "review",
        )
        self.assertEqual(mcp.schematic_geometry.finding_count, 1)
        findings = [
            item for item in mcp.findings if item.rule_id == "schematic.wire_endpoint_near_pin_tip"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence["pin"], ("R1.1",))
        self.assertEqual(findings[0].evidence["wire_endpoint_mm"], ("76.200000,70.620000",))
        self.assertEqual(findings[0].evidence["distance_to_pin_tip_mm"], ("0.500000",))

        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_endpoint_near_pin_tip",
                                mode="off",
                                reason="Synthetic parity fixture checks explicit opt-out",
                            ),
                        )
                    )
                }
            ),
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            disabled_cli = await self.cli(
                "kicad_tooling.design_lint",
                DesignLintReport,
                "--project",
                "controller",
                "--native-summary",
                str(native),
                expected_exit=0,
            )
            disabled_mcp = await self.call(
                client,
                "inspect_design_lint",
                DesignLintReport,
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(self.root).as_posix(),
                },
            )
        self.assertEqual(disabled_cli, disabled_mcp)
        self.assertEqual(disabled_mcp.status, "PASS")
        self.assertEqual(disabled_mcp.schematic_geometry.status, "DISABLED")
        self.assertNotIn(
            "schematic.wire_endpoint_near_pin_tip",
            {item.rule_id for item in disabled_mcp.findings},
        )


def test_schematic_pin_tip_on_wire_interior_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParitySchematicConnectivityCases,
        "_case_test_schematic_pin_tip_on_wire_interior_cli_mcp_parity",
    )


def test_schematic_label_near_wire_endpoint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParitySchematicConnectivityCases,
        "_case_test_schematic_label_near_wire_endpoint_cli_mcp_parity",
    )


def test_schematic_wire_endpoint_near_pin_tip_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParitySchematicConnectivityCases,
        "_case_test_schematic_wire_endpoint_near_pin_tip_cli_mcp_parity",
    )
