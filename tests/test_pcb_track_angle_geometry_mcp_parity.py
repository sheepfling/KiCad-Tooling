"""CLI and MCP parity for mapped track-angle geometry review findings."""

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
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    PcbKeepoutCoverageReport,
    PcbProtectionPathCoverageReport,
    PcbReferencePlaneCoverageReport,
    PcbRfModuleAntennaCoverageReport,
    PcbSignalPathRuleCoverageReport,
    PcbSwitchingLoopCoverageReport,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
)
from kicad_tooling.hwrepo.pcb_decoupling_models import PcbDecouplingCoverageReport
from kicad_tooling.hwrepo.pcb_thermal_via_models import PcbThermalViaCoverageReport
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageReport,
)
from kicad_tooling.hwrepo.pcb_track_angle_models import (
    PcbTrackAngleMap,
    PcbTrackAngleRequirement,
)
from kicad_tooling.hwrepo.pcb_track_width_models import PcbTrackWidthCoverageReport
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import synthetic_design_lint_project

RULE_ID = "pcb.track_angle_geometry_review"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _track_angle_map() -> PcbTrackAngleMap:
    return PcbTrackAngleMap(
        basis="Synthetic reviewed route-angle requirement for CLI/MCP parity",
        requirements=(
            PcbTrackAngleRequirement(
                id="clock-output",
                basis="Synthetic signal-integrity review",
                net="CLOCK_OUT",
                rule_name="clock-angle",
                minimum_degrees=150,
            ),
        ),
    )


def _candidate() -> Candidate:
    return Candidate(
        rule_id=RULE_ID,
        subject="CLOCK_OUT F.Cu corner at 1000000,0 nm",
        message="Measured 135.000 degree corner is below the configured 150 degree minimum.",
        evidence={
            "net": ("CLOCK_OUT",),
            "requirement_id": ("clock-output",),
            "measured_angle_degrees": ("135.000",),
            "track_uuids": (
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
            ),
            "board_sha256": ("a" * 64,),
            "snapshot_sha256": ("b" * 64,),
            "probe_sha256": ("c" * 64,),
        },
    )


def test_mapped_track_angle_finding_matches_cli_and_mcp(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    angle_map = _track_angle_map()
    policy = DesignLintPolicy(
        pcb_track_angle_map=angle_map,
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Exercise an explicitly enabled synthetic geometry finding",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.track_angle_rule_coverage",
                mode="off",
                reason="Keep this parity fixture focused on measured PCB geometry",
            ),
        ),
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)

    def synthetic_geometry_scan(*_args, **_kwargs):
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
            PcbComponentInventoryCoverageReport(),
            PcbThermalViaCoverageReport(),
            (_candidate(),),
        )

    monkeypatch.setattr(
        design_lint_project_inspection,
        "scan_pcb_geometry",
        synthetic_geometry_scan,
    )
    # This fixture has no native DRC report; suppress unrelated source-bound DRC lanes.
    monkeypatch.setattr(
        design_lint_project_inspection,
        "collect_pcb_dru_candidates",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        design_lint_project_inspection,
        "collect_pcb_native_drc_candidates",
        lambda *_args, **_kwargs: (),
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
    assert cli_returncode == 1
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
    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    findings = tuple(item for item in mcp_report.findings if item.rule_id == RULE_ID)
    assert len(findings) == 1, mcp_report.model_dump_json(indent=2)
    (finding,) = findings
    assert finding.subject == "CLOCK_OUT F.Cu corner at 1000000,0 nm"
    assert finding.message == _candidate().message
