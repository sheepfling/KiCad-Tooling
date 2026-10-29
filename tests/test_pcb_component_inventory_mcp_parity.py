"""CLI/MCP parity for source-bound PCB component inventory findings."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling import design_lint as design_lint_cli
from kicad_tooling.hwrepo import design_lint_project_inspection
from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintRuleOverride,
    PcbKeepoutCoverageReport,
    PcbProtectionPathCoverageReport,
    ProjectConfig,
)
from kicad_tooling.hwrepo.pcb_board_only_footprint_models import (
    PcbBoardOnlyFootprint,
    PcbBoardOnlyFootprintCoverage,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbComponentValueMismatch,
    PcbFootprintIdentityMismatch,
    PcbMissingFootprintPlacement,
    PcbPopulationMismatch,
    PcbVariantPopulationCoverage,
    PcbVariantPopulationEvidence,
)
from kicad_tooling.hwrepo.pcb_decoupling_models import PcbDecouplingCoverageReport
from kicad_tooling.hwrepo.pcb_drc_models import PcbSignalPathRuleCoverageReport
from kicad_tooling.hwrepo.pcb_pad_net_models import PcbSchematicBoardPadNetMismatch
from kicad_tooling.hwrepo.pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from kicad_tooling.hwrepo.pcb_required_fitted_reference_models import (
    PcbRequiredFittedReference,
    PcbRequiredFittedReferenceCoverage,
    PcbRequiredFittedReferenceMap,
    PcbRequiredFittedReferenceMismatch,
    PcbRequiredFittedReferenceVariant,
)
from kicad_tooling.hwrepo.pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from kicad_tooling.hwrepo.pcb_switching_loop_models import PcbSwitchingLoopCoverageReport
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageReport,
)
from kicad_tooling.hwrepo.pcb_track_width_models import PcbTrackWidthCoverageReport
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.parity_lint]
BOARD_ONLY_RULE = "pcb.board_only_footprint"
REQUIRED_FITTED_RULE = "pcb.required_fitted_reference"
VARIANT = "Synthetic Assembly A"
SYNTHETIC_IMAGE = "registry.invalid/kicad:10.0.5@sha256:" + "a" * 64


@pytest.mark.design_lint_rule(rule_id=BOARD_ONLY_RULE)
@pytest.mark.design_lint_rule(rule_id=REQUIRED_FITTED_RULE)
def test_component_inventory_findings_match_cli_and_mcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    required_map = PcbRequiredFittedReferenceMap(
        basis="synthetic parity assembly list",
        requirements=(
            PcbRequiredFittedReference(
                reference="U1",
                footprint="Package_QFP:TQFP-48",
                basis="required for synthetic parity check",
            ),
        ),
        variants=(
            PcbRequiredFittedReferenceVariant(
                variant=VARIANT,
                requirements=(
                    PcbRequiredFittedReference(
                        reference="U6",
                        footprint="Package_QFP:TQFP-48",
                        basis="required in the synthetic named assembly",
                    ),
                ),
            ),
        ),
    )
    root, native = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=BOARD_ONLY_RULE,
                    mode="review",
                    reason="exercise cross-surface candidate parity",
                ),
                DesignLintRuleOverride(
                    rule_id=REQUIRED_FITTED_RULE,
                    mode="review",
                    reason="exercise required fitted-reference parity",
                ),
            ),
            pcb_required_fitted_reference_map=required_map,
        ),
    )

    def synthetic_geometry_scan(
        root: Path,
        config: ProjectConfig,
        coach: ContractCoachReport,
        policy: DesignLintPolicy,
        native_summary: Path,
    ):
        del root, policy, native_summary
        return (
            PcbDecouplingCoverageReport(),
            PcbProtectionPathCoverageReport(),
            PcbTrackWidthCoverageReport(),
            PcbReferencePlaneCoverageReport(),
            PcbSwitchingLoopCoverageReport(),
            PcbSignalPathRuleCoverageReport(),
            PcbKeepoutCoverageReport(),
            PcbRfModuleAntennaCoverageReport(),
            PcbTouchPadClearanceCoverageReport(),
            PcbComponentInventoryCoverageReport(
                status="COMPLETE",
                mode="review",
                netlist_sha256=coach.netlist_sha256,
                board_path=Path(config.project).with_suffix(".kicad_pcb").as_posix(),
                board_sha256="b" * 64,
                snapshot_path="build/design-lint/synthetic-inventory/snapshot.json",
                snapshot_sha256="c" * 64,
                snapshot_schema="13",
                kicad_version=config.kicad_version,
                image=config.image,
                probe_sha256="d" * 64,
                missing_placements=(
                    PcbMissingFootprintPlacement(
                        reference="U2",
                        assigned_footprint="Package_SO:SOIC-8",
                    ),
                ),
                footprint_mismatches=(
                    PcbFootprintIdentityMismatch(
                        reference="U3",
                        assigned_footprint="Package_SO:SOIC-8",
                        placed_footprint="Package_TSSOP:TSSOP-8",
                    ),
                ),
                population_mismatches=(
                    PcbPopulationMismatch(
                        reference="U1",
                        schematic_dnp=False,
                        board_dnp=True,
                    ),
                ),
                variant_population=PcbVariantPopulationCoverage(
                    status="COMPLETE",
                    project_path="projects/synthetic/controller.kicad_pro",
                    project_sha256="1" * 64,
                    schematic_path="projects/synthetic/controller.kicad_sch",
                    schematic_sha256="2" * 64,
                    board_path="projects/synthetic/controller.kicad_pcb",
                    board_sha256="b" * 64,
                    kicad_version=config.kicad_version,
                    image=config.image,
                    board_variant_probe_path="build/design-lint/variant/probe.py",
                    board_variant_probe_sha256="3" * 64,
                    board_variant_request_path="build/design-lint/variant/request.json",
                    board_variant_request_sha256="4" * 64,
                    board_variant_command_path="build/design-lint/variant/probe.command.json",
                    board_variant_command_sha256="5" * 64,
                    evidence=(
                        PcbVariantPopulationEvidence(
                            variant=VARIANT,
                            netlist_path="build/design-lint/variant/netlist.xml",
                            netlist_sha256="6" * 64,
                            netlist_command_path="build/design-lint/variant/netlist.command.json",
                            netlist_command_sha256="7" * 64,
                            board_all_positions_path="build/design-lint/variant/all.csv",
                            board_all_positions_sha256="8" * 64,
                            board_all_command_path="build/design-lint/variant/all.command.json",
                            board_all_command_sha256="9" * 64,
                            board_fitted_positions_path="build/design-lint/variant/fitted.csv",
                            board_fitted_positions_sha256="a" * 64,
                            board_fitted_command_path="build/design-lint/variant/fitted.command.json",
                            board_fitted_command_sha256="f" * 64,
                        ),
                    ),
                ),
                value_comparison_status="COMPLETE",
                value_mismatches=(
                    PcbComponentValueMismatch(
                        reference="R4",
                        schematic_value="10k",
                        board_value="100k",
                    ),
                ),
                pad_net_comparison_status="COMPLETE",
                pad_net_mismatches=(
                    PcbSchematicBoardPadNetMismatch(
                        reference="U5",
                        pin="4",
                        mismatch="net_assignment_differs",
                        schematic_net="SYNTHETIC_RETURN",
                        board_net="SYNTHETIC_RETURN_2",
                    ),
                ),
                board_only_footprint_coverage=PcbBoardOnlyFootprintCoverage(
                    status="COMPLETE",
                    mode="review",
                    footprints=(
                        PcbBoardOnlyFootprint(
                            reference="H_MOUNT1",
                            footprint="MountingHole:NPTH",
                        ),
                    ),
                ),
                required_fitted_reference_coverage=PcbRequiredFittedReferenceCoverage(
                    status="COMPLETE",
                    mode="review",
                    map_sha256="e" * 64,
                    requirement_count=2,
                    mismatches=(
                        PcbRequiredFittedReferenceMismatch(
                            reference="U1",
                            basis="synthetic required fitted component",
                            expected_footprint="Package_QFP:TQFP-48",
                            schematic_footprint="Package_QFP:TQFP-48",
                            board_footprint="Package_QFP:TQFP-48",
                            schematic_dnp=False,
                            board_dnp=True,
                            violations=("board_footprint_dnp",),
                        ),
                        PcbRequiredFittedReferenceMismatch(
                            reference="U6",
                            variant=VARIANT,
                            basis="required in the synthetic named assembly",
                            expected_footprint="Package_QFP:TQFP-48",
                            schematic_footprint="Package_QFP:TQFP-48",
                            board_footprint="Package_QFP:TQFP-48",
                            schematic_dnp=False,
                            board_dnp=True,
                            violations=("board_footprint_dnp",),
                        ),
                    ),
                ),
            ),
        )

    monkeypatch.setattr(
        design_lint_project_inspection,
        "scan_pcb_geometry",
        synthetic_geometry_scan,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kicad-team-design-lint",
            "--root",
            str(root),
            "--project",
            "controller",
            "--native-summary",
            native.relative_to(root).as_posix(),
            "--format",
            "json",
        ],
    )

    cli_returncode = design_lint_cli.main()
    cli_report = parse_model_text(capsys.readouterr().out, DesignLintReport)

    async def inspect_mcp() -> DesignLintReport:
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(root).as_posix(),
                },
            )
            assert not result.is_error, result.content
            assert result.structured_content is not None
            return DesignLintReport.model_validate_json(json.dumps(result.structured_content))

    mcp_report = asyncio.run(inspect_mcp())

    assert cli_returncode == 1
    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    findings = tuple(
        item for item in mcp_report.findings if item.rule_id == "pcb.schematic_component_inventory"
    )
    assert tuple(item.subject for item in findings) == (
        "U2: schematic footprint absent from PCB",
        "U3: schematic and PCB footprint identities differ",
    )
    assert findings[0].evidence["snapshot_schema"] == ("13",)
    assert findings[1].evidence["assigned_footprint"] == ("Package_SO:SOIC-8",)
    assert findings[1].evidence["placed_footprint"] == ("Package_TSSOP:TSSOP-8",)
    (population_finding,) = tuple(
        item for item in mcp_report.findings if item.rule_id == "pcb.schematic_pcb_dnp_mismatch"
    )
    assert population_finding.subject == "U1: schematic and PCB DNP states differ"
    assert population_finding.evidence["schematic_dnp"] == ("false",)
    assert population_finding.evidence["board_dnp"] == ("true",)
    (value_finding,) = tuple(
        item for item in mcp_report.findings if item.rule_id == "pcb.schematic_pcb_value_mismatch"
    )
    assert value_finding.subject == "R4: schematic and PCB value fields differ"
    assert value_finding.evidence["schematic_value"] == ("10k",)
    assert value_finding.evidence["board_value"] == ("100k",)
    (pad_net_finding,) = tuple(
        item for item in mcp_report.findings if item.rule_id == "pcb.schematic_pcb_pad_net_mismatch"
    )
    assert pad_net_finding.subject == ("U5.4: schematic and PCB net assignments differ")
    assert pad_net_finding.evidence["schematic_net"] == ("SYNTHETIC_RETURN",)
    assert pad_net_finding.evidence["board_net"] == ("SYNTHETIC_RETURN_2",)
    (board_only_finding,) = tuple(
        item for item in mcp_report.findings if item.rule_id == BOARD_ONLY_RULE
    )
    assert board_only_finding.subject == ("H_MOUNT1: PCB footprint has no schematic counterpart")
    assert board_only_finding.evidence["footprint"] == ("MountingHole:NPTH",)
    (required_finding,) = tuple(
        item
        for item in mcp_report.findings
        if item.rule_id == REQUIRED_FITTED_RULE and not item.evidence.get("variant")
    )
    assert required_finding.subject == "U1: required fitted component does not match source"
    assert required_finding.evidence["violations"] == ("board_footprint_dnp",)
    (variant_required_finding,) = tuple(
        item
        for item in mcp_report.findings
        if item.rule_id == REQUIRED_FITTED_RULE
        and item.evidence.get("variant") == (VARIANT,)
    )
    assert variant_required_finding.subject == (
        f"U6 in variant '{VARIANT}': required fitted component does not match source"
    )
    assert variant_required_finding.evidence["variant_evidence"] == (
        f"tool=10.0.5@{SYNTHETIC_IMAGE}",
        "project=projects/synthetic/controller.kicad_pro@" + "1" * 64,
        "schematic=projects/synthetic/controller.kicad_sch@" + "2" * 64,
        "board=projects/synthetic/controller.kicad_pcb@" + "b" * 64,
        "variant_probe=build/design-lint/variant/probe.py@" + "3" * 64,
        "variant_request=build/design-lint/variant/request.json@" + "4" * 64,
        "variant_probe_command=build/design-lint/variant/probe.command.json@" + "5" * 64,
        f"{VARIANT}:netlist=build/design-lint/variant/netlist.xml@" + "6" * 64,
        f"{VARIANT}:netlist_command=build/design-lint/variant/netlist.command.json@" + "7" * 64,
        f"{VARIANT}:board_all=build/design-lint/variant/all.csv@" + "8" * 64,
        f"{VARIANT}:board_all_command=build/design-lint/variant/all.command.json@" + "9" * 64,
        f"{VARIANT}:board_fitted=build/design-lint/variant/fitted.csv@" + "a" * 64,
        f"{VARIANT}:board_fitted_command=build/design-lint/variant/fitted.command.json@" + "f" * 64,
    )
