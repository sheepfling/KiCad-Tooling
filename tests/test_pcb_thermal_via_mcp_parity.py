"""CLI/MCP parity for project-authored PCB thermal-pad via coverage."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling import design_lint as design_lint_cli
from kicad_tooling.hwrepo import design_lint_project_inspection
from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import map_sha256
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
)
from kicad_tooling.hwrepo.pcb_decoupling_models import PcbDecouplingCoverageReport
from kicad_tooling.hwrepo.pcb_drc_models import PcbSignalPathRuleCoverageReport
from kicad_tooling.hwrepo.pcb_keepout_models import PcbKeepoutCoverageReport
from kicad_tooling.hwrepo.pcb_protection_path_models import PcbProtectionPathCoverageReport
from kicad_tooling.hwrepo.pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from kicad_tooling.hwrepo.pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from kicad_tooling.hwrepo.pcb_switching_loop_models import PcbSwitchingLoopCoverageReport
from kicad_tooling.hwrepo.pcb_thermal_via_models import PcbThermalViaCoverageReport
from kicad_tooling.hwrepo.pcb_thermal_vias import pcb_thermal_via_entries
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageReport,
)
from kicad_tooling.hwrepo.pcb_track_width_models import PcbTrackWidthCoverageReport
from tests.mcp_parity_support import semantic_design_lint_report
from tests.pcb_thermal_vias_support import mapping, requirement, snapshot
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.parity_lint]


def _coverage(
    root, config, coach, authored, *, connected_count: int
) -> PcbThermalViaCoverageReport:
    board_relative = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    board_sha256 = digest(root / board_relative)
    span = authored.requirements[0].required_layer_spans[0]
    native = snapshot(
        tuple(
            (index * 20_000, 0, span.start_layer, span.end_layer, True)
            for index in range(1, connected_count + 1)
        )
    ).model_copy(
        update={
            "board_sha256": board_sha256,
            "kicad_version": config.kicad_version,
            "image": config.image,
        }
    )
    entries = pcb_thermal_via_entries(authored, native)
    status = "COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE"
    snapshot_sha256 = hashlib.sha256(native.model_dump_json().encode("utf-8")).hexdigest()
    return PcbThermalViaCoverageReport(
        status=status,
        mode="review",
        map_sha256=map_sha256(authored),
        board_path=board_relative,
        board_sha256=board_sha256,
        snapshot_path="build/design-lint/synthetic-thermal-via-snapshot.json",
        snapshot_sha256=snapshot_sha256,
        probe_sha256=native.probe_sha256,
        kicad_version=native.kicad_version,
        image=native.image,
        netlist_sha256=coach.netlist_sha256,
        entries=entries,
    )


def _disable_unrelated_inventory(policy: DesignLintPolicy) -> DesignLintPolicy:
    overrides = {item.rule_id: item for item in policy.rules}
    for rule_id in (
        "pcb.schematic_component_inventory",
        "pcb.schematic_pcb_dnp_mismatch",
        "pcb.schematic_pcb_value_mismatch",
    ):
        overrides[rule_id] = DesignLintRuleOverride(
            rule_id=rule_id,
            mode="off",
            reason="Synthetic parity fixture isolates thermal-via coverage",
        )
    return policy.model_copy(update={"rules": tuple(overrides.values())})


def _install_geometry_scan(monkeypatch, *, connected_count: int) -> None:
    def scan(root, config, coach, policy, native_summary):
        authored = policy.pcb_thermal_via_map
        assert authored is not None
        thermal = _coverage(root, config, coach, authored, connected_count=connected_count)
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
            thermal,
            (),
        )

    monkeypatch.setattr(design_lint_project_inspection, "scan_pcb_geometry", scan)


def _read_mcp_report(root: Path, native: Path) -> DesignLintReport:
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

    return asyncio.run(inspect_mcp())


def test_disabled_thermal_via_coverage_matches_cli_and_mcp(tmp_path: Path) -> None:
    authored = mapping()
    policy = _disable_unrelated_inventory(
        DesignLintPolicy(
            pcb_thermal_via_map=authored,
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.thermal_via_coverage",
                    mode="off",
                    reason="Synthetic parity fixture disables via review",
                ),
            ),
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
    cli_report = parse_model_text(process.stdout, DesignLintReport)

    mcp_report = _read_mcp_report(root, native)

    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    assert mcp_report.pcb_thermal_via_coverage.status == "DISABLED"
    assert mcp_report.pcb_thermal_via_coverage.map_sha256 == map_sha256(authored)


@pytest.mark.design_lint_rule(rule_id="pcb.thermal_via_coverage")
@pytest.mark.parametrize(
    ("minimum", "connected_count", "expected_status"),
    ((3, 2, "INCOMPLETE"), (2, 2, "COMPLETE")),
    ids=("missing-via-fault", "exact-count-control"),
)
def test_enabled_thermal_via_fault_and_control_match_cli_and_mcp(
    tmp_path: Path,
    monkeypatch,
    capsys,
    minimum: int,
    connected_count: int,
    expected_status: str,
) -> None:
    authored = mapping(requirement(minimum=minimum))
    policy = _disable_unrelated_inventory(DesignLintPolicy(pcb_thermal_via_map=authored))
    root, native = synthetic_design_lint_project(tmp_path, policy)
    _install_geometry_scan(monkeypatch, connected_count=connected_count)
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
    exit_code = design_lint_cli.main()
    cli_report = parse_model_text(capsys.readouterr().out, DesignLintReport)

    mcp_report = _read_mcp_report(root, native)

    # The synthetic native summary is deliberately FAIL, so its overall CLI
    # exit remains 1 even when this rule's complete control emits no finding.
    assert exit_code in {0, 1}
    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    assert mcp_report.pcb_thermal_via_coverage.status == expected_status
    findings = tuple(
        item for item in mcp_report.findings if item.rule_id == "pcb.thermal_via_coverage"
    )
    assert len(findings) == (1 if expected_status == "INCOMPLETE" else 0)
