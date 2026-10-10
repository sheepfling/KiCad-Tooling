"""Pytest CLI/MCP parity for the project-mapped RF antenna coverage service."""

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
from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    PcbKeepoutCoverageReport,
    PcbProtectionPathCoverageReport,
    PcbReferencePlaneCoverageReport,
    PcbRfModuleAntennaCoverageReport,
    PcbRfModuleAntennaMap,
    PcbSignalPathRuleCoverageReport,
    PcbSwitchingLoopCoverageReport,
    ValidationSummary,
)
from kicad_tooling.hwrepo.pcb_decoupling_models import PcbDecouplingCoverageReport
from kicad_tooling.hwrepo.pcb_rf_antenna import pcb_rf_module_antenna_entries
from kicad_tooling.hwrepo.pcb_track_width_models import PcbTrackWidthCoverageReport
from tests.pcb_rf_antenna_support import FOOTPRINT, SYMBOL, requirement
from tests.pcb_rf_antenna_support import snapshot as antenna_snapshot
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)


def _install_source_matched_rf_netlist(summary_path: Path) -> None:
    """Bind a tooling-owned synthetic module export into the fixture receipt."""
    library, part = SYMBOL.split(":", 1)
    netlist_path = summary_path.parent / "netlist.xml"
    netlist_path.write_text(
        "<export><components>"
        '<comp ref="U1"><value>Synthetic radio</value>'
        f"<footprint>{FOOTPRINT}</footprint>"
        '<fields><field name="PART_ID">RADIO-1</field></fields>'
        f'<libsource lib="{library}" part="{part}"/>'
        '<units><unit name="A"><pins><pin num="1"/></pins></unit></units>'
        "</comp></components><libparts>"
        f'<libpart lib="{library}" part="{part}"><pins>'
        '<pin num="1" name="RF_FEED" type="passive"/></pins></libpart>'
        '</libparts><nets><net name="RF_IN"><node ref="U1" pin="1"/></net>'
        "</nets></export>",
        encoding="utf-8",
    )
    summary = read_model(summary_path, ValidationSummary)
    artifacts = dict(summary.artifacts_sha256)
    artifacts["netlist.xml"] = digest(netlist_path)
    write_model(summary_path, summary.model_copy(update={"artifacts_sha256": artifacts}))


def test_disabled_rf_antenna_coverage_matches_cli_and_mcp(tmp_path: Path) -> None:
    rf_map = PcbRfModuleAntennaMap(
        basis="Synthetic RF module coverage disabled for parity control",
        requirements=(requirement(),),
    )
    policy = DesignLintPolicy(
        pcb_rf_module_antenna_map=rf_map,
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.rf_module_antenna_keepout_coverage",
                mode="off",
                reason="Synthetic parity fixture disables RF antenna review",
            ),
        ),
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
    cli_report = parse_model_text(process.stdout, DesignLintReport)

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
    assert cli_report == mcp_report
    assert mcp_report.pcb_rf_module_antenna_coverage.status == "DISABLED"
    assert (
        mcp_report.pcb_rf_module_antenna_coverage.map_sha256
        == hashlib.sha256(rf_map.model_dump_json().encode("utf-8")).hexdigest()
    )


@pytest.mark.parametrize(
    ("board_feed_net", "expected_coverage_status"),
    (("RF_OUT", "INCOMPLETE"), ("RF_IN", "COMPLETE")),
)
def test_enabled_rf_antenna_fault_and_control_match_cli_and_mcp(
    tmp_path: Path,
    monkeypatch,
    capsys,
    board_feed_net: str,
    expected_coverage_status: str,
) -> None:
    rf_map = PcbRfModuleAntennaMap(
        basis="Synthetic RF module CLI/MCP fault parity",
        requirements=(requirement(),),
    )
    policy = DesignLintPolicy(pcb_rf_module_antenna_map=rf_map)
    root, native = synthetic_design_lint_project(tmp_path, policy)
    _install_source_matched_rf_netlist(native)

    def synthetic_geometry_scan(root, config, coach, authored, native_summary):
        board_relative = Path(config.project).with_suffix(".kicad_pcb").as_posix()
        board_path = root / board_relative
        board_sha256 = hashlib.sha256(board_path.read_bytes()).hexdigest()
        observed = antenna_snapshot(pad_net=board_feed_net).model_copy(
            update={
                "board_sha256": board_sha256,
                "kicad_version": config.kicad_version,
                "image": config.image,
            }
        )
        assert coach.observed is not None
        entries = pcb_rf_module_antenna_entries(
            authored.pcb_rf_module_antenna_map,
            coach.observed,
            observed,
        )
        map_sha256 = hashlib.sha256(
            authored.pcb_rf_module_antenna_map.model_dump_json().encode("utf-8")
        ).hexdigest()
        snapshot_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
        coverage = PcbRfModuleAntennaCoverageReport(
            status=expected_coverage_status,
            mode="review",
            map_sha256=map_sha256,
            board_path=board_relative,
            board_sha256=board_sha256,
            snapshot_path="build/design-lint/synthetic-pcb.json",
            snapshot_sha256=snapshot_sha256,
            probe_sha256=observed.probe_sha256,
            kicad_version=observed.kicad_version,
            image=observed.image,
            netlist_sha256=coach.netlist_sha256,
            entries=entries,
        )
        return (
            PcbDecouplingCoverageReport(),
            PcbProtectionPathCoverageReport(),
            PcbTrackWidthCoverageReport(),
            PcbReferencePlaneCoverageReport(),
            PcbSwitchingLoopCoverageReport(),
            PcbSignalPathRuleCoverageReport(),
            PcbKeepoutCoverageReport(),
            coverage,
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
    assert cli_returncode == 1

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
    assert cli_report == mcp_report
    assert mcp_report.pcb_rf_module_antenna_coverage.status == expected_coverage_status
    findings = tuple(
        item
        for item in mcp_report.findings
        if item.rule_id == "pcb.rf_module_antenna_keepout_coverage"
    )
    if expected_coverage_status == "INCOMPLETE":
        (finding,) = findings
        assert finding.subject == "U1: onboard_antenna antenna requirement"
        assert cli_returncode == 1
    else:
        assert findings == ()
