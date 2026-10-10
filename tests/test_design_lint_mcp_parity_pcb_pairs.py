"""Design-lint CLI/MCP parity cases: design lint mcp parity pcb pairs."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

import json

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    parse_model_text,
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from kicad_tooling.validate import hashes
from tests import test_parts_workflow as native_fixture
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)
from tests.test_pcb_drc_coverage import pair_map as synthetic_differential_pair_map
from tests.test_pcb_drc_coverage import rules_text as synthetic_differential_pair_rules


class _DesignLintMcpParityPcbPairsCases(McpParityHarness):
    async def _case_test_pcb_differential_pair_rule_coverage_parity(self) -> None:
        native = self.native_evidence()
        config = load_config(self.root, self.island / "project.json")
        board = self.root / config.project.replace(".kicad_pro", ".kicad_pcb")
        rules = self.root / config.project.replace(".kicad_pro", ".kicad_dru")
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        pcb_differential_pair_rule_map=synthetic_differential_pair_map()
                    )
                }
            ),
        )
        board.write_text("(kicad_pcb (version 20250114))", encoding="utf-8")
        (native.parent / "netlist.xml").write_text(
            "<export><components>"
            '<comp ref="R1"><value>1k</value><footprint>Synthetic:R</footprint>'
            '<libsource lib="Device" part="R"/></comp>'
            "</components><nets>"
            '<net name="USB_D_P"/><net name="USB_D_N"/>'
            "</nets></export>",
            encoding="utf-8",
        )

        def refresh_receipt(ignored: tuple[str, ...] = ()) -> None:
            current = hashes(self.root, config.source_roots)
            drc_path = native.parent / "drc.json"
            drc_path.write_text(
                json.dumps(
                    {
                        "kicad_version": config.kicad_version,
                        "source": board.name,
                        "ignored_checks": [{"key": key} for key in ignored],
                        "violations": [],
                        "unconnected_items": [],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            write_model(
                native.parent / "drc.command.json",
                native_fixture.command().model_copy(
                    update={
                        "argv": (
                            "synthetic-kicad-cli",
                            "pcb",
                            "drc",
                            "--format",
                            "json",
                            "--severity-all",
                            "--exit-code-violations",
                            "--output",
                            str(drc_path),
                            str(board),
                        )
                    }
                ),
            )
            summary = read_model(native, ValidationSummary)
            checks = dict(summary.checks)
            checks["source_scope"] = CheckEvidence(status="PASS", source_hashes=current)
            checks["source_unchanged"] = CheckEvidence(status="PASS", source_hashes=current)
            checks["drc"] = CheckEvidence(status="PASS", returncode=0)
            artifacts = {
                **summary.artifacts_sha256,
                "netlist.xml": digest(native.parent / "netlist.xml"),
                "netlist.command.json": digest(native.parent / "netlist.command.json"),
                "drc.json": digest(drc_path),
                "drc.command.json": digest(native.parent / "drc.command.json"),
            }
            write_model(
                native,
                summary.model_copy(
                    update={
                        "checks": checks,
                        "artifacts_sha256": artifacts,
                    }
                ),
            )

        async with Client(create_server(self.root), mode="legacy") as client:
            for scenario, expected, ignored, mode in (
                ("exact", "COMPLETE", (), "review"),
                ("missing", "INCOMPLETE", (), "review"),
                ("ignored", "INCOMPLETE", ("skew_out_of_range",), "review"),
                ("disabled", "DISABLED", (), "off"),
            ):
                with self.subTest(scenario=scenario):
                    if scenario == "missing":
                        rules.unlink(missing_ok=True)
                    else:
                        rules.write_text(synthetic_differential_pair_rules(), encoding="utf-8")
                    manifest_path = self.island / "project.json"
                    manifest = read_model(manifest_path, ProjectManifest)
                    required_inputs = set(manifest.required_inputs)
                    rules_relative = rules.relative_to(self.island).as_posix()
                    if rules.exists():
                        required_inputs.add(rules_relative)
                    else:
                        required_inputs.discard(rules_relative)
                    write_model(
                        manifest_path,
                        manifest.model_copy(
                            update={"required_inputs": tuple(sorted(required_inputs))}
                        ),
                    )
                    current_contract = read_model(contract_path, ProjectTestContract)
                    write_model(
                        contract_path,
                        current_contract.model_copy(
                            update={
                                "design_lint": DesignLintPolicy(
                                    pcb_differential_pair_rule_map=synthetic_differential_pair_map(),
                                    rules=(
                                        DesignLintRuleOverride(
                                            rule_id="pcb.differential_pair_rule_coverage",
                                            mode="off",
                                            reason="Synthetic parity case explicitly disables this audit",
                                        ),
                                    )
                                    if mode == "off"
                                    else (),
                                )
                            }
                        ),
                    )
                    refresh_receipt(ignored)
                    process = await self.cli_process(
                        "kicad_tooling.design_lint",
                        "--project",
                        "controller",
                        "--native-summary",
                        str(native),
                    )
                    self.assertIn(process.returncode, {0, 1}, process.stderr + process.stdout)
                    cli_report = parse_model_text(process.stdout, DesignLintReport)
                    mcp_report = await self.call(
                        client,
                        "inspect_design_lint",
                        DesignLintReport,
                        {
                            "project_id": "controller",
                            "native_summary": native.relative_to(self.root).as_posix(),
                        },
                    )
                    self.assertEqual(cli_report, mcp_report)
                    coverage = mcp_report.pcb_differential_pair_rules
                    self.assertEqual(coverage.status, expected, (coverage.issue, mcp_report.issues))
                    self.assertEqual(process.returncode, 0 if mcp_report.status == "PASS" else 1)
                    if scenario == "ignored":
                        pair = coverage.entries[0]
                        skew = next(item for item in pair.constraints if item.constraint == "skew")
                        self.assertEqual(skew.status, "IGNORED")
                    if scenario == "disabled":
                        self.assertIsNotNone(coverage.map_sha256)
                    else:
                        self.assertIsNotNone(coverage.native_drc_sha256)


def test_pcb_differential_pair_rule_coverage_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityPcbPairsCases, "_case_test_pcb_differential_pair_rule_coverage_parity"
    )
