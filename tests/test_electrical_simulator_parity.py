"""CLI/MCP parity for an external fixed simulator and version mismatch."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ElectricalAnalysisReport
from tests.contract_coach_support import fake_executable
from tests.electrical_parity_support import (
    ElectricalParityHarness,
    parity_harness,  # noqa: F401
)
from tests.electrical_simulation_support import PROJECT
from tests.test_source_parity import source_bytes

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


async def _run_external_fixed_simulator_success_and_wrong_version_match_cli(
    parity: ElectricalParityHarness,
) -> None:
    parity.configured(simulation=True)
    before = source_bytes(parity.root)
    binary = parity.root.parent / "external-bin"
    binary.mkdir()
    waveform = (
        "Title: synthetic\nFlags: real\nNo. Variables: 2\nNo. Points: 4\n"
        "Variables:\n0 time time\n1 v(out) voltage\nValues:\n"
        "0 0\n0\n1 0.001\n4.9\n2 0.004\n4.95\n3 0.005\n5\n"
    )
    executable = fake_executable(
        binary / "ngspice",
        (
            "from pathlib import Path\nimport sys\n"
            "if sys.argv[1:] == ['--version']:\n    print('ngspice-47')\n"
            "else:\n"
            f"    Path('waveforms.raw').write_text({waveform!r})\n"
            "    print('Synthetic simulator progress')\n"
            "    print('check0 = 4.95' if Path.cwd().name == 'startup' else "
            "'check0 = 0.05\\ncheck1 = 0.25\\ncheck2 = 4.95')\n"
        ),
    )
    assert not executable.is_relative_to(parity.root)
    with patch.dict(os.environ, {"PATH": str(binary) + os.pathsep + os.environ.get("PATH", "")}):
        async with Client(
            create_server(parity.mcp_root, allow_checks=True), mode="legacy"
        ) as client:
            for view, version, status in (
                ("simulation", "47", "PASS"),
                ("wrong-version", "46", "FAIL"),
            ):
                if version == "46":
                    fake_executable(binary / "ngspice", "print('ngspice-46')\n")
                process = await parity.cli(
                    "kicad_tooling.electrical",
                    "--project",
                    PROJECT,
                    "--output",
                    f"build/electrical/{view}",
                )
                assert process.returncode == (0 if status == "PASS" else 1), (
                    process.stderr + process.stdout
                )
                cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
                result = await client.call_tool(
                    "analyze_electrical", {"project_id": PROJECT, "view_id": view}
                )
                assert not result.is_error, result.content
                mcp_report = ElectricalAnalysisReport.model_validate_json(
                    json.dumps(result.structured_content)
                )
                assert cli_report.checks == mcp_report.checks
                assert cli_report.input_sha256 == mcp_report.input_sha256
                for report in (cli_report, mcp_report):
                    assert report.status == status
                    assert not report.build_authorized
                    if status == "PASS":
                        assert "Synthetic simulator progress" in report.commands["startup"].stdout
                        assert set(report.commands) == {"version", "startup", "steady-state"}
                    else:
                        assert any(row.status == "NOT_RUN" for row in report.checks)
                        assert (
                            Path(report.run_directory) / "ngspice-version.command.json"
                        ).is_file()
    assert source_bytes(parity.root) == before
    assert source_bytes(parity.mcp_root) == before


def test_external_fixed_simulator_success_and_wrong_version_match_cli(
    parity: ElectricalParityHarness,
) -> None:
    asyncio.run(_run_external_fixed_simulator_success_and_wrong_version_match_cli(parity))
