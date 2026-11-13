"""CLI and MCP expose the same source-bound track-width scope prompt."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    PcbTrackWidthMap,
    PcbTrackWidthRequirement,
)
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt
from tests.synthetic_design_lint_project import run_design_lint_cli, synthetic_design_lint_project

RULE_ID = "pcb.track_width_unmapped_native_rule"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_unmapped_track_width_scope_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    board = (
        Path(__file__).parents[1]
        / "kicad_tooling/hwrepo/fixtures/pcb-decoupling-placement.kicad_pcb"
    )
    rules = (
        "(version 1)\n"
        '(rule "vdd-width" (severity error) '
        "(condition \"A.NetName == 'VDD'\") (constraint track_width (min 0.25mm)))\n"
        '(rule "data-width" (severity error) '
        "(condition \"A.NetName == 'DATA'\") (constraint track_width (min 0.25mm)))\n"
    )
    policy = parity_design_lint_policy(
        DesignLintPolicy(
            pcb_track_width_map=PcbTrackWidthMap(
                basis="Synthetic exact-net geometry scope",
                requirements=(
                    PcbTrackWidthRequirement(
                        id="vdd-route",
                        basis="Synthetic authored review threshold",
                        net="VDD",
                        minimum_width_um=250,
                    ),
                ),
            )
        )
    )
    root, native = synthetic_design_lint_project(
        tmp_path,
        policy,
        custom_rules_source=rules,
        board_source=board.read_text(encoding="utf-8"),
    )
    install_source_bound_drc_receipt(root, native)

    shim = tmp_path / "docker-shim"
    shim.mkdir()
    docker = shim / "docker"
    docker.write_text(
        (
            Path(__file__).parent / "fixtures/design_lint/mcp-parity/pcb-native-snapshot-shim.py"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join((str(shim), environment["PATH"]))
    with patch.dict(os.environ, {"PATH": environment["PATH"]}):
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode == 1, process.stderr + process.stdout
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

    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    assert mcp_report.status == "REVIEW", mcp_report.issues
    (finding,) = tuple(item for item in mcp_report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review" and finding.disposition == "OPEN"
    assert finding.evidence["net"] == ("DATA",)
    assert finding.evidence["source_sha256"] == (
        mcp_report.source_hashes["projects/controller/kicad/controller.kicad_dru"],
    )
