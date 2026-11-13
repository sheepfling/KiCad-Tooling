"""Build source-bound CLI and MCP reports for omitted path-rule scope tests."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintPolicy,
    DesignLintReport,
    NetlistContract,
)
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)


def signal_path_surface_reports(
    tmp_path: Path,
    *,
    requirements: DesignLintPolicy,
    rules_source: str,
    nets: dict[str, tuple[str, ...]],
) -> tuple[DesignLintReport, DesignLintReport]:
    """Return CLI and MCP reports over one identical tooling-owned project."""
    board = (
        Path(__file__).parents[1]
        / "kicad_tooling/hwrepo/fixtures/pcb-decoupling-placement.kicad_pcb"
    )
    policy = parity_design_lint_policy(requirements)
    root, native = synthetic_design_lint_project(
        tmp_path,
        policy,
        custom_rules_source=rules_source,
        board_source=board.read_text(encoding="utf-8"),
    )
    references = ("J1", "D1", "R1")
    install_synthetic_netlist(
        native,
        contract_netlist_xml(
            NetlistContract(
                components={
                    reference: ComponentContract(value="Synthetic", footprint="Synthetic:Part")
                    for reference in references
                },
                nets=nets,
                component_symbols={reference: "Synthetic:Part" for reference in references},
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
    return cli_report, mcp_report


def assert_signal_path_cli_mcp_parity(
    cli_report: DesignLintReport, mcp_report: DesignLintReport
) -> None:
    """Compare report semantics, ignoring only a fresh per-run command receipt hash."""
    cli_semantic = semantic_design_lint_report(cli_report)
    mcp_semantic = semantic_design_lint_report(mcp_report)
    for report in (cli_semantic, mcp_semantic):
        signal_path_report = report["pcb_signal_path_rules"]
        assert isinstance(signal_path_report, dict)
        signal_path_report["pcb_command_sha256"] = "<per-run-command-receipt>"
    assert cli_semantic == mcp_semantic
