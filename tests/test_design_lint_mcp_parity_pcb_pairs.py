"""Design-lint CLI/MCP parity cases: design lint mcp parity pcb pairs."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
]

import json
from pathlib import Path

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
    PcbReferencePlaneMap,
    PcbReferencePlaneRequirement,
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

DIFFERENTIAL_PAIR_BOARD = (
    Path(__file__).parent / "fixtures/design_lint/differential-pair/control.kicad_pcb"
)


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
        board.write_text(DIFFERENTIAL_PAIR_BOARD.read_text(encoding="utf-8"), encoding="utf-8")
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
                        "$schema": "https://schemas.kicad.org/drc.v1.json",
                        "kicad_version": config.kicad_version,
                        "source": board.name,
                        "coordinate_units": "mm",
                        "included_severities": ["error", "warning", "exclusion"],
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
                ("unmapped", "COMPLETE", (), "review"),
                ("missing", "INCOMPLETE", (), "review"),
                ("ignored", "INCOMPLETE", ("skew_out_of_range",), "review"),
                ("disabled", "DISABLED", (), "off"),
                ("plane-map-control", "COMPLETE", (), "review"),
                ("pair-plane-rule-off", "COMPLETE", (), "review"),
                ("route-skew-rule-off", "COMPLETE", (), "review"),
            ):
                with self.subTest(scenario=scenario):
                    if scenario == "missing":
                        rules.unlink(missing_ok=True)
                    else:
                        native_rules = synthetic_differential_pair_rules()
                        if scenario == "unmapped":
                            native_rules = (
                                '\n(rule "unmapped-motor-pair-width" (severity warning) '
                                "(condition \"A.inDiffPair('MOTOR_')\") "
                                "(constraint track_width (min 0.2mm)))\n"
                            ) + native_rules
                        rules.write_text(native_rules, encoding="utf-8")
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
                    overrides = []
                    if mode == "off":
                        overrides.append(
                            DesignLintRuleOverride(
                                rule_id="pcb.differential_pair_rule_coverage",
                                mode="off",
                                reason="Synthetic parity case explicitly disables this audit",
                            )
                        )
                    if scenario == "plane-map-control":
                        overrides.append(
                            DesignLintRuleOverride(
                                rule_id="pcb.reference_plane_coverage",
                                mode="off",
                                reason="Synthetic case tests map-scope review without geometry",
                            )
                        )
                    if scenario == "pair-plane-rule-off":
                        overrides.append(
                            DesignLintRuleOverride(
                                rule_id="pcb.differential_pair_reference_plane_scope_missing",
                                mode="off",
                                reason="Synthetic project intentionally disables this review",
                            )
                        )
                    if scenario == "route-skew-rule-off":
                        overrides.append(
                            DesignLintRuleOverride(
                                rule_id="pcb.differential_pair_route_skew_scope_missing",
                                mode="off",
                                reason="Synthetic project intentionally disables this review",
                            )
                        )
                    plane_map = (
                        PcbReferencePlaneMap(
                            basis="Synthetic pair reference-plane scope control",
                            requirements=tuple(
                                PcbReferencePlaneRequirement(
                                    id=f"usb-pair-{net.casefold()}",
                                    basis=f"Synthetic reviewed plane scope for {net}",
                                    signal_net=net,
                                    signal_layers=("F.Cu",),
                                    reference_net="GND",
                                    minimum_track_length_um=1,
                                    minimum_referenced_fraction=0.9,
                                )
                                for net in ("USB_D_P", "USB_D_N")
                            ),
                        )
                        if scenario == "plane-map-control"
                        else None
                    )
                    write_model(
                        contract_path,
                        current_contract.model_copy(
                            update={
                                "design_lint": DesignLintPolicy(
                                    pcb_differential_pair_rule_map=synthetic_differential_pair_map(),
                                    pcb_reference_plane_map=plane_map,
                                    rules=tuple(overrides),
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
                    self.assertEqual(
                        coverage.status,
                        expected,
                        (scenario, coverage.issue, mcp_report.issues),
                    )
                    self.assertEqual(process.returncode, 0 if mcp_report.status == "PASS" else 1)
                    if scenario == "ignored":
                        pair = coverage.entries[0]
                        skew = next(item for item in pair.constraints if item.constraint == "skew")
                        self.assertEqual(skew.status, "IGNORED")
                    if scenario == "disabled":
                        self.assertIsNotNone(coverage.map_sha256)
                    else:
                        self.assertIsNotNone(coverage.native_drc_sha256)
                    unmapped = tuple(
                        item
                        for item in mcp_report.findings
                        if item.rule_id == "pcb.differential_pair_unmapped_native_rule"
                    )
                    if scenario == "unmapped":
                        self.assertEqual(len(unmapped), 1)
                        self.assertEqual(
                            unmapped[0].evidence["pair_selector"],
                            ("MOTOR_",),
                        )
                    else:
                        self.assertFalse(unmapped)
                    missing_plane_scope = tuple(
                        item
                        for item in mcp_report.findings
                        if item.rule_id == "pcb.differential_pair_reference_plane_scope_missing"
                    )
                    if scenario == "plane-map-control":
                        self.assertFalse(missing_plane_scope)
                    elif scenario == "pair-plane-rule-off":
                        self.assertEqual(len(missing_plane_scope), 1)
                        self.assertEqual(missing_plane_scope[0].mode, "off")
                        self.assertEqual(missing_plane_scope[0].disposition, "RULE_OFF")
                    else:
                        self.assertEqual(len(missing_plane_scope), 1)
                        self.assertEqual(
                            missing_plane_scope[0].evidence["missing_reference_plane_nets"],
                            ("USB_D_P", "USB_D_N"),
                        )
                    missing_skew_scope = tuple(
                        item
                        for item in mcp_report.findings
                        if item.rule_id == "pcb.differential_pair_route_skew_scope_missing"
                    )
                    if scenario == "route-skew-rule-off":
                        self.assertEqual(len(missing_skew_scope), 1)
                        self.assertEqual(missing_skew_scope[0].mode, "off")
                        self.assertEqual(missing_skew_scope[0].disposition, "RULE_OFF")
                    else:
                        self.assertEqual(len(missing_skew_scope), 1)
                        self.assertEqual(
                            missing_skew_scope[0].evidence["positive_net"], ("USB_D_P",)
                        )
                        self.assertEqual(
                            missing_skew_scope[0].evidence["negative_net"], ("USB_D_N",)
                        )


@pytest.mark.design_lint_rule(rule_id="pcb.differential_pair_rule_coverage")
@pytest.mark.design_lint_rule(rule_id="pcb.differential_pair_unmapped_native_rule")
@pytest.mark.design_lint_rule(rule_id="pcb.differential_pair_reference_plane_scope_missing")
@pytest.mark.design_lint_rule(rule_id="pcb.differential_pair_route_skew_scope_missing")
def test_pcb_differential_pair_rule_coverage_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityPcbPairsCases, "_case_test_pcb_differential_pair_rule_coverage_parity"
    )
