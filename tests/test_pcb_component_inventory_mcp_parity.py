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
    DesignLintPolicy,
    PcbKeepoutCoverageReport,
    PcbProtectionPathCoverageReport,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbFootprintIdentityMismatch,
    PcbMissingFootprintPlacement,
)
from kicad_tooling.hwrepo.pcb_decoupling_models import PcbDecouplingCoverageReport
from kicad_tooling.hwrepo.pcb_drc_models import PcbSignalPathRuleCoverageReport
from kicad_tooling.hwrepo.pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from kicad_tooling.hwrepo.pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from kicad_tooling.hwrepo.pcb_switching_loop_models import PcbSwitchingLoopCoverageReport
from kicad_tooling.hwrepo.pcb_track_width_models import PcbTrackWidthCoverageReport
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.parity_lint]


def test_component_inventory_findings_match_cli_and_mcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, native = synthetic_design_lint_project(tmp_path, DesignLintPolicy())

    def synthetic_geometry_scan(root, config, coach, policy, native_summary):
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
            PcbComponentInventoryCoverageReport(
                status="COMPLETE",
                mode="review",
                netlist_sha256=coach.netlist_sha256,
                board_path=Path(config.project).with_suffix(".kicad_pcb").as_posix(),
                board_sha256="b" * 64,
                snapshot_path="build/design-lint/synthetic-inventory/snapshot.json",
                snapshot_sha256="c" * 64,
                snapshot_schema="12",
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
    assert cli_report == mcp_report
    findings = tuple(
        item for item in mcp_report.findings if item.rule_id == "pcb.schematic_component_inventory"
    )
    assert tuple(item.subject for item in findings) == (
        "U2: schematic footprint absent from PCB",
        "U3: schematic and PCB footprint identities differ",
    )
    assert findings[0].evidence["snapshot_schema"] == ("12",)
    assert findings[1].evidence["assigned_footprint"] == ("Package_SO:SOIC-8",)
    assert findings[1].evidence["placed_footprint"] == ("Package_TSSOP:TSSOP-8",)
