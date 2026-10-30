"""One authored ground domain against retained, hash-bound netlist evidence."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.grounding_view import _pins, build_grounding_view
from kicad_tooling.hwrepo.grounding_view_models import GroundingViewReport
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import NetlistContract
from tests.electrical_simulation_support import install_fixture
from tests.electrical_view_support import saved_electrical_view
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.support import reference_root

pytestmark = pytest.mark.template_checkout


def saved_analysis(root: Path, *, observed: bool = True) -> Path:
    contract = install_fixture(root)
    netlist = (
        NetlistContract(
            components={},
            nets={"PILOT_B": ("R1.2", "R3.1"), "PILOT_B_EXTRA": ("R1.2",), "OTHER": ("R2.2",)},
            unconnected_nets={"NC": ("R2.2",)},
        )
        if observed
        else None
    )
    return saved_electrical_view(root, contract, netlist)


def test_pin_view_keeps_distinct_nets_and_uncertainty() -> None:
    observed = NetlistContract(
        components={},
        nets={"GND": ("J1.1", "J1.3"), "GND_2": ("J1.1",), "OTHER": ("J1.2",)},
        unconnected_nets={"NC": ("J1.2",)},
    )
    rows = _pins("GND", ("J1.1", "J1.2", "J1.4"), observed)
    assert [(row.pin, row.status) for row in rows] == [
        ("J1.1", "AMBIGUOUS"),
        ("J1.2", "UNCONNECTED"),
        ("J1.4", "MISSING"),
        ("J1.3", "UNDECLARED"),
    ]
    assert rows[0].observed_nets == ("GND", "GND_2")
    assert all(row.expected_net != "GND_2" for row in rows)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    shutil.copytree(reference_root(), root, ignore=shutil.ignore_patterns(".git", "build"))
    return root


def test_retained_observation_and_missing_evidence(repository: Path) -> None:
    report_path = saved_analysis(repository)
    view = build_grounding_view(
        repository, report_path, "PILOT_B", Path("build/grounding-view/observed")
    )
    assert view.observation_status == "RETAINED"
    assert view.source_status == "CURRENT"
    assert [(row.pin, row.status) for row in view.pins] == [
        ("R1.2", "AMBIGUOUS"),
        ("R2.2", "UNCONNECTED"),
        ("R3.1", "UNDECLARED"),
    ]
    assert (
        read_model(Path(view.output_directory) / "grounding-view.json", GroundingViewReport) == view
    )
    assert "physical continuity" in (Path(view.output_directory) / "index.html").read_text(
        encoding="utf-8"
    )
    pcb = repository / "examples/projects/controller/kicad/controller.kicad_pcb"
    pcb.write_bytes(pcb.read_bytes() + b"\n")
    stale = build_grounding_view(repository, report_path, "PILOT_B")
    assert stale.source_status == "STALE"
    (report_path.parent / "netlist-evidence.json").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed or is missing"):
        build_grounding_view(repository, report_path, "PILOT_B")


def test_unreviewed_evidence_stays_unreviewed(repository: Path) -> None:
    report_path = saved_analysis(repository, observed=False)
    view = build_grounding_view(repository, report_path, "PILOT_B")
    assert view.observation_status == "UNREVIEWED"
    assert [row.status for row in view.pins] == ["UNREVIEWED", "UNREVIEWED"]
    with pytest.raises(ValueError, match="exact authored"):
        build_grounding_view(repository, report_path, "PILOT")


class _GroundingParity(McpParityHarness):
    async def _case_test_cli_mcp_grounding_view_parity(self) -> None:
        report_path = saved_analysis(self.root)
        cli = await self.cli(
            "kicad_tooling.grounding_view",
            GroundingViewReport,
            "--receipt",
            str(report_path),
            "--net",
            "PILOT_B",
            "--output",
            "build/grounding-view/cli",
        )
        args = {
            "receipt": report_path.relative_to(self.root).as_posix(),
            "net": "PILOT_B",
            "view_id": "mcp",
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue((await client.call_tool("export_grounding_view", args)).is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "export_grounding_view", GroundingViewReport, args)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_cli_mcp_grounding_view_parity() -> None:
    run_mcp_parity(_GroundingParity, "_case_test_cli_mcp_grounding_view_parity")
