"""CLI and MCP share exact native length-rule omission prompts."""

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
    ComponentContract,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
    PcbDrcMinMaxRequirement,
    PcbSignalPathRequirement,
    PcbSignalPathRuleMap,
)
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "pcb.signal_path_unmapped_native_rule"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_unmapped_exact_length_scope_matches_cli_and_mcp(tmp_path: Path) -> None:
    board = (
        Path(__file__).parents[1]
        / "kicad_tooling/hwrepo/fixtures/pcb-decoupling-placement.kicad_pcb"
    )
    rules = (
        "(version 1)\n"
        '(rule "mapped-data-length" (severity error) '
        "(condition \"A.NetName == 'DATA'\") (constraint length (max 25mm)))\n"
        '(rule "unmapped-extra-length" (severity error) '
        "(condition \"A.NetName == 'EXTRA'\") (constraint length (max 25mm)))\n"
    )
    requirements = PcbSignalPathRuleMap(
        basis="Synthetic reviewed route scope",
        paths=(
            PcbSignalPathRequirement(
                id="data-path",
                basis="Synthetic exact endpoint route",
                net="DATA",
                from_pad="J1.1",
                to_pad="D1.1",
                length=PcbDrcMinMaxRequirement(max_nm=25_000_000),
            ),
        ),
    )
    policy = parity_design_lint_policy(DesignLintPolicy(pcb_signal_path_rule_map=requirements))
    root, native = synthetic_design_lint_project(
        tmp_path,
        policy,
        custom_rules_source=rules,
        board_source=board.read_text(encoding="utf-8"),
    )
    install_synthetic_netlist(
        native,
        contract_netlist_xml(
            NetlistContract(
                components={
                    reference: ComponentContract(value="Synthetic", footprint="Synthetic:Part")
                    for reference in ("J1", "D1", "R1")
                },
                nets={"DATA": ("J1.1", "D1.1"), "EXTRA": ("R1.1",)},
                component_symbols={reference: "Synthetic:Part" for reference in ("J1", "D1", "R1")},
                component_pin_numbers={
                    "J1": ("1", "2"),
                    "D1": ("1", "2"),
                    "R1": ("1",),
                },
            )
        ),
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

    cli_semantic = semantic_design_lint_report(cli_report)
    mcp_semantic = semantic_design_lint_report(mcp_report)
    for report in (cli_semantic, mcp_semantic):
        signal_path_report = report["pcb_signal_path_rules"]
        assert isinstance(signal_path_report, dict)
        # The native command receipt includes a fresh capture timestamp per run.
        signal_path_report["pcb_command_sha256"] = "<per-run-command-receipt>"
    assert cli_semantic == mcp_semantic
    assert mcp_report.status == "REVIEW", mcp_report.issues
    (finding,) = tuple(item for item in mcp_report.findings if item.rule_id == RULE_ID)
    assert finding.subject == "unmapped-extra-length: EXTRA is absent from signal-path coverage"
    assert finding.mode == "review" and finding.disposition == "OPEN"
    assert finding.evidence["net"] == ("EXTRA",)
    assert finding.evidence["source_sha256"] == (
        mcp_report.source_hashes["projects/controller/kicad/controller.kicad_dru"],
    )
    assert finding.evidence["source_netlist_sha256"] == (mcp_report.netlist_sha256,)
