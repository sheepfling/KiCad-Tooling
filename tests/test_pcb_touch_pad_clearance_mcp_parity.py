"""CLI/MCP parity for configured touch-pad reference-copper clearance lint."""

from __future__ import annotations

import asyncio
import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling import design_lint as design_lint_cli
from kicad_tooling.hwrepo import design_lint_project_inspection
from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import map_sha256
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    PcbDecouplingCoverageReport,
    PcbKeepoutCoverageReport,
    PcbProtectionPathCoverageReport,
    PcbReferencePlaneCoverageReport,
    PcbRfModuleAntennaCoverageReport,
    PcbSignalPathRuleCoverageReport,
    PcbSwitchingLoopCoverageReport,
    PcbTrackWidthCoverageReport,
    ValidationSummary,
)
from kicad_tooling.hwrepo.pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
)
from kicad_tooling.hwrepo.pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageEntry,
    PcbTouchPadClearanceCoverageReport,
    PcbTouchPadClearanceMap,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.pcb_touch_pad_clearance_support import (
    FOOTPRINT,
    clearance_map,
    request_hash,
)
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.parity_lint]


def _install_source_matched_netlist(summary_path: Path) -> None:
    """Bind a synthetic connector netlist to the project receipt."""
    netlist_path = summary_path.parent / "netlist.xml"
    netlist_path.write_text(
        "<export><components>"
        f'<comp ref="J1"><value>Synthetic connector</value><footprint>{FOOTPRINT}</footprint>'
        '<fields></fields><libsource lib="Connector_Generic" part="Conn_01x01"/>'
        '<units><unit name="A"><pins><pin num="1"/></pins></unit></units></comp>'
        "</components><libparts>"
        '<libpart lib="Connector_Generic" part="Conn_01x01"><pins>'
        '<pin num="1" name="SIGNAL" type="passive"/></pins></libpart>'
        '</libparts><nets><net name="SIGNAL"><node ref="J1" pin="1"/></net>'
        "</nets></export>",
        encoding="utf-8",
    )
    summary = read_model(summary_path, ValidationSummary)
    artifacts = dict(summary.artifacts_sha256)
    artifacts["netlist.xml"] = digest(netlist_path)
    write_model(summary_path, summary.model_copy(update={"artifacts_sha256": artifacts}))


def _touch_coverage(
    root: Path,
    config,
    coach,
    authored: PcbTouchPadClearanceMap,
    *,
    measured_clearance_nm: int,
    mode: str,
) -> PcbTouchPadClearanceCoverageReport:
    if mode == "off":
        return PcbTouchPadClearanceCoverageReport(
            status="DISABLED",
            mode="off",
            map_sha256=map_sha256(authored),
        )
    if coach.netlist_sha256 is None:
        raise AssertionError("Synthetic parity project should have a source-bound netlist")
    board_relative = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    board_path = root / board_relative
    requirement = authored.requirements[0]
    entry = PcbTouchPadClearanceCoverageEntry(
        requirement_id=requirement.id,
        basis=authored.basis,
        pad=requirement.pad,
        expected_pad_net=requirement.expected_pad_net,
        schematic_pad_net=requirement.expected_pad_net,
        observed_pad_net=requirement.expected_pad_net,
        reference_net=requirement.reference_net,
        layer=requirement.layer,
        minimum_clearance_nm=requirement.minimum_clearance_nm,
        measured_clearance_nm=measured_clearance_nm,
        closest_zone_uuid="12345678-1234-5678-1234-567812345678",
        status="COMPLETE",
    )
    return PcbTouchPadClearanceCoverageReport(
        status="COMPLETE",
        mode=mode,
        map_sha256=map_sha256(authored),
        board_path=board_relative,
        board_sha256=digest(board_path),
        snapshot_path="build/design-lint/synthetic-touch-clearance.json",
        snapshot_sha256=sha256(b"synthetic source-bound geometry").hexdigest(),
        probe_sha256=sha256(b"synthetic exact native probe").hexdigest(),
        request_sha256=request_hash(requirement.minimum_clearance_nm),
        kicad_version=config.kicad_version,
        image=config.image,
        netlist_sha256=coach.netlist_sha256,
        requirement_count=len(authored.requirements),
        entries=(entry,),
    )


def _install_geometry_scan(monkeypatch, *, measured_clearance_nm: int) -> None:
    def scan(root, config, coach, policy, native_summary):
        authored = policy.pcb_touch_pad_clearance_map
        assert authored is not None
        override = next(
            (item for item in policy.rules if item.rule_id == "pcb.touch_pad_reference_clearance"),
            None,
        )
        mode = "review" if override is None else override.mode
        return (
            PcbDecouplingCoverageReport(),
            PcbProtectionPathCoverageReport(),
            PcbTrackWidthCoverageReport(),
            PcbReferencePlaneCoverageReport(),
            PcbSwitchingLoopCoverageReport(),
            PcbSignalPathRuleCoverageReport(),
            PcbKeepoutCoverageReport(),
            PcbRfModuleAntennaCoverageReport(),
            _touch_coverage(
                root,
                config,
                coach,
                authored,
                measured_clearance_nm=measured_clearance_nm,
                mode=mode,
            ),
            PcbComponentInventoryCoverageReport(),
        )

    monkeypatch.setattr(design_lint_project_inspection, "scan_pcb_geometry", scan)


@pytest.mark.parametrize(
    ("measured_clearance_nm", "expected_finding_count"),
    ((250_000, 1), (500_000, 0)),
    ids=("below-minimum", "at-minimum-control"),
)
def test_enabled_touch_clearance_fault_and_control_match_cli_and_mcp(
    tmp_path: Path,
    monkeypatch,
    capsys,
    measured_clearance_nm: int,
    expected_finding_count: int,
) -> None:
    authored = clearance_map(minimum_clearance_nm=500_000)
    policy = DesignLintPolicy(pcb_touch_pad_clearance_map=authored)
    root, native = synthetic_design_lint_project(tmp_path, policy)
    _install_source_matched_netlist(native)
    _install_geometry_scan(monkeypatch, measured_clearance_nm=measured_clearance_nm)
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

    design_lint_cli.main()
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
    assert mcp_report.pcb_touch_pad_clearance_coverage.status == "COMPLETE"
    findings = tuple(
        item for item in mcp_report.findings if item.rule_id == "pcb.touch_pad_reference_clearance"
    )
    assert len(findings) == expected_finding_count


def test_disabled_touch_clearance_coverage_matches_cli_and_mcp(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    authored = clearance_map()
    policy = DesignLintPolicy(
        pcb_touch_pad_clearance_map=authored,
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.touch_pad_reference_clearance",
                mode="off",
                reason="Synthetic parity fixture disables the configured geometry review",
            ),
        ),
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    _install_source_matched_netlist(native)
    _install_geometry_scan(monkeypatch, measured_clearance_nm=100_000)
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
    design_lint_cli.main()
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
    assert mcp_report.pcb_touch_pad_clearance_coverage.status == "DISABLED"
    assert not any(
        item.rule_id == "pcb.touch_pad_reference_clearance" for item in mcp_report.findings
    )
