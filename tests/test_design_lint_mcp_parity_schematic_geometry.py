"""Design-lint CLI/MCP parity cases: design lint mcp parity schematic geometry."""

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


class _DesignLintMcpParitySchematicGeometryCases(McpParityHarness):
    async def _case_test_schematic_geometry_opt_in_parity(self) -> None:
        """Exercise source-bound geometry through installed CLI and MCP adapters."""
        schematic = self.island / "kicad/controller.kicad_sch"
        schematic_source = (
            (
                Path(__file__).parent
                / "fixtures/design_lint/t-junction/near-miss-crossing-and-t-junction.kicad_sch"
            )
            .read_text(encoding="utf-8")
            .replace("near-miss-pin-line", "controller")
        )
        text_nodes = (
            '  (text "PARITY_A" (at 25.4 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "d1000000-0000-4000-8000-000000000001"))\n'
            '  (text "PARITY_B" (at 25.4 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "d1000000-0000-4000-8000-000000000002"))\n'
            '  (text "LONG_LABEL_ALPHA" (at 150 25.4 0) '
            "(effects (font (size 1.27 1.27)) (justify right)) "
            '(uuid "d1000000-0000-4000-8000-000000000003"))\n'
            '  (text "LONG_LABEL_BETA" (at 153.6 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "d1000000-0000-4000-8000-000000000004"))\n'
            '  (text "WIRE_NOTE" (at 127 127 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "d1000000-0000-4000-8000-000000000005"))\n'
            '  (text "BODY_NOTE" (at 76.2 78.0 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "d1000000-0000-4000-8000-000000000006"))\n'
        )
        body_wire = (
            "  (wire (pts (xy 71.12 76.2) (xy 81.28 76.2)) "
            "(stroke (width 0) (type default)) "
            '(uuid "f1000000-0000-4000-8000-000000000001"))\n'
        )
        schematic_source = schematic_source.replace(
            "  (sheet_instances", f"{body_wire}{text_nodes}  (sheet_instances", 1
        )
        schematic.write_text(schematic_source, encoding="utf-8")

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
                                rule_id="schematic.wire_end_on_pin_line",
                                mode="review",
                                reason="Synthetic parity fixture opts in to pin-line localization",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.unmarked_wire_crossing",
                                mode="review",
                                reason="Synthetic parity fixture opts in to crossing review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.unmarked_t_junction",
                                mode="review",
                                reason="Synthetic parity fixture opts in to T-junction review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.coincident_text_anchors",
                                mode="review",
                                reason="Synthetic parity fixture opts in to graphical text review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.free_text_overlap",
                                mode="review",
                                reason="Synthetic parity fixture opts in to rendered text-envelope review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.free_text_over_wire",
                                mode="review",
                                reason="Synthetic parity fixture opts in to free-text wire-envelope review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_through_symbol_body",
                                mode="review",
                                reason="Synthetic parity fixture opts in to symbol-body wire review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.free_text_over_symbol_body",
                                mode="review",
                                reason="Synthetic parity fixture opts in to text-body review",
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
            mcp.schematic_geometry.source_path, schematic.relative_to(self.root).as_posix()
        )
        self.assertEqual(mcp.schematic_geometry.source_sha256, digest(schematic))
        self.assertEqual(mcp.schematic_geometry.netlist_sha256, digest(netlist))
        self.assertEqual(mcp.schematic_geometry.kicad_version, "10.0.6")
        self.assertEqual(mcp.schematic_geometry.finding_count, 9)
        geometry_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.wire_end_on_pin_line"
        ]
        self.assertEqual(len(geometry_findings), 1)
        self.assertEqual(geometry_findings[0].evidence["pin"], ("R1.1",))
        crossing_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.unmarked_wire_crossing"
        ]
        self.assertEqual(len(crossing_findings), 1)
        self.assertEqual(crossing_findings[0].evidence["crossing_mm"], ("127.000000,127.000000",))
        t_junction_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.unmarked_t_junction"
        ]
        self.assertEqual(len(t_junction_findings), 1)
        self.assertEqual(t_junction_findings[0].evidence["junction_mm"], ("177.800000,177.800000",))
        text_anchor_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.coincident_text_anchors"
        ]
        self.assertEqual(len(text_anchor_findings), 1)
        self.assertEqual(
            text_anchor_findings[0].evidence["first_text_uuid"],
            ("d1000000-0000-4000-8000-000000000001",),
        )
        text_overlap_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.free_text_overlap"
        ]
        self.assertEqual(len(text_overlap_findings), 1)
        self.assertEqual(
            text_overlap_findings[0].evidence["first_text_uuid"],
            ("d1000000-0000-4000-8000-000000000003",),
        )
        text_wire_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.free_text_over_wire"
        ]
        self.assertEqual(len(text_wire_findings), 2)
        self.assertEqual(
            {item.evidence["text_uuid"] for item in text_wire_findings},
            {("d1000000-0000-4000-8000-000000000005",)},
        )
        self.assertTrue(all("overlap_segment_mm" in item.evidence for item in text_wire_findings))
        body_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.wire_through_symbol_body"
        ]
        self.assertEqual(len(body_findings), 1)
        self.assertEqual(body_findings[0].evidence["reference"], ("R1",))
        self.assertEqual(
            body_findings[0].evidence["wire_uuid"], ("f1000000-0000-4000-8000-000000000001",)
        )
        self.assertIn("body_box_mm", body_findings[0].evidence)
        text_body_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.free_text_over_symbol_body"
        ]
        self.assertEqual(len(text_body_findings), 1)
        self.assertEqual(
            text_body_findings[0].evidence["text_uuid"],
            ("d1000000-0000-4000-8000-000000000006",),
        )
        self.assertEqual(text_body_findings[0].evidence["reference"], ("R1",))
        self.assertIn("overlap_area_mm2", text_body_findings[0].evidence)

        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_end_on_pin_line",
                                mode="off",
                                reason="Synthetic parity fixture checks explicit opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.unmarked_wire_crossing",
                                mode="off",
                                reason="Synthetic parity fixture checks crossing opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.unmarked_t_junction",
                                mode="off",
                                reason="Synthetic parity fixture checks T-junction opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.coincident_text_anchors",
                                mode="off",
                                reason="Synthetic parity fixture checks graphical text opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.free_text_over_wire",
                                mode="off",
                                reason="Synthetic parity fixture checks wire-envelope opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_through_symbol_body",
                                mode="off",
                                reason="Synthetic parity fixture checks symbol-body opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.free_text_over_symbol_body",
                                mode="off",
                                reason="Synthetic parity fixture checks text-body opt-out",
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
        self.assertFalse(
            any(item.rule_id == "schematic.wire_end_on_pin_line" for item in disabled_mcp.findings)
        )
        self.assertFalse(
            any(
                item.rule_id == "schematic.unmarked_wire_crossing" for item in disabled_mcp.findings
            )
        )
        self.assertFalse(
            any(item.rule_id == "schematic.unmarked_t_junction" for item in disabled_mcp.findings)
        )
        self.assertFalse(
            any(
                item.rule_id == "schematic.coincident_text_anchors"
                for item in disabled_mcp.findings
            )
        )
        self.assertFalse(
            any(item.rule_id == "schematic.free_text_over_wire" for item in disabled_mcp.findings)
        )
        self.assertFalse(
            any(
                item.rule_id == "schematic.wire_through_symbol_body"
                for item in disabled_mcp.findings
            )
        )
        self.assertFalse(
            any(
                item.rule_id == "schematic.free_text_over_symbol_body"
                for item in disabled_mcp.findings
            )
        )


def test_schematic_geometry_opt_in_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParitySchematicGeometryCases, "_case_test_schematic_geometry_opt_in_parity"
    )
