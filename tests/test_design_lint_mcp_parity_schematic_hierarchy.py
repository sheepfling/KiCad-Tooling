"""Design-lint CLI/MCP parity cases: design lint mcp parity schematic hierarchy."""

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


class _DesignLintMcpParitySchematicHierarchyCases(McpParityHarness):
    async def _case_test_reused_child_sheet_geometry_source_binding_cli_mcp_parity(self) -> None:
        """Bind repeated child findings to each KiCad hierarchy instance."""
        fixture_root = Path(__file__).parent / "fixtures/design_lint/repeated-sheet"
        schematic = self.island / "kicad/controller.kicad_sch"
        channel = self.island / "kicad/repeated-channel.kicad_sch"
        schematic.write_text(
            (fixture_root / "repeated-sheet-root.kicad_sch")
            .read_text(encoding="utf-8")
            .replace("repeated-sheet-root", "controller"),
            encoding="utf-8",
        )
        channel_text = (
            (fixture_root / "repeated-channel.kicad_sch")
            .read_text(encoding="utf-8")
            .replace("repeated-sheet-root", "controller")
        )
        channel_text = channel_text.replace(
            "  (sheet_instances",
            "  (wire (pts (xy 76.2 80.01) (xy 101.6 80.01)) "
            "(stroke (width 0) (type default)) "
            '(uuid "c0000000-0000-4000-8000-000000000013"))\n'
            "  (sheet_instances",
            1,
        )
        channel.write_text(
            channel_text,
            encoding="utf-8",
        )

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "toolchain_id": "kicad-10.0.6",
                    "required_inputs": tuple(
                        sorted(
                            {
                                *manifest.required_inputs,
                                channel.relative_to(self.island).as_posix(),
                            }
                        )
                    ),
                }
            ),
        )
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
                                rule_id="schematic.wire_end_on_pin_line",
                                mode="review",
                                reason="Synthetic repeated-sheet fixture checks per-instance pin mapping",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.unmarked_t_junction",
                                mode="review",
                                reason="Synthetic repeated-sheet parity fixture opts in to review",
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
                '<nets><net name="unconnected-(R1-Pad2)"><node ref="R1" pin="2"/>'
                '</net><net name="unconnected-(R2-Pad2)"><node ref="R2" pin="2"/>'
                "</net></nets>",
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
        coverage = mcp.schematic_geometry
        self.assertEqual(coverage.status, "COMPLETE", mcp.model_dump_json(indent=2))
        self.assertEqual(coverage.source_sha256, digest(schematic))
        self.assertNotEqual(coverage.source_tree_sha256, coverage.source_sha256)
        self.assertEqual(coverage.finding_count, 6)
        self.assertEqual(len(coverage.source_bindings), 3)
        self.assertEqual(
            {binding.sheet_path for binding in coverage.source_bindings},
            {(), ("InstanceA",), ("InstanceB",)},
        )
        findings = [
            item for item in mcp.findings if item.rule_id == "schematic.unmarked_t_junction"
        ]
        self.assertEqual(len(findings), 2)
        self.assertEqual(len({item.fingerprint for item in findings}), 2)
        self.assertEqual(
            {item.evidence["schematic"][0] for item in findings},
            {channel.relative_to(self.root).as_posix()},
        )
        self.assertEqual(
            {item.evidence["sheet_instance_path"][0] for item in findings},
            {
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000002",
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000003",
            },
        )
        self.assertEqual(
            {item.evidence["schematic_sha256"][0] for item in findings},
            {digest(channel)},
        )
        pin_line_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.wire_end_on_pin_line"
        ]
        self.assertEqual(len(pin_line_findings), 2)
        self.assertEqual(
            {item.evidence["pin"][0] for item in pin_line_findings},
            {"R1.2", "R2.2"},
        )
        self.assertEqual(
            {item.evidence["sheet_instance_path"][0] for item in pin_line_findings},
            {item.evidence["sheet_instance_path"][0] for item in findings},
        )


def test_reused_child_sheet_geometry_source_binding_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParitySchematicHierarchyCases,
        "_case_test_reused_child_sheet_geometry_source_binding_cli_mcp_parity",
    )
