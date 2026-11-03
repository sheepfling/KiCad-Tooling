"""Exact net membership and bounded neighboring terminals stay source-bound."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.connectivity_view import (
    MAX_SELECTED_PINS,
    _neighborhoods,
    build_connectivity_view,
)
from kicad_tooling.hwrepo.connectivity_view_models import ConnectivityViewReport
from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from tests.electrical_simulation_support import install_fixture
from tests.electrical_view_support import saved_electrical_view
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.support import reference_root

pytestmark = pytest.mark.template_checkout


def _saved(root: Path, *, observed: bool = True) -> Path:
    contract = install_fixture(root)
    netlist = (
        NetlistContract(
            components={
                ref: ComponentContract(value="1k", footprint="Resistor_SMD:R_0603_1608Metric")
                for ref in ("R1", "R2", "R3")
            },
            nets={
                "PILOT_B": ("R1.2", "R3.1"),
                "PILOT_B_EXTRA": ("R1.2",),
                "OTHER": ("R1.1", "R3.2"),
                "ISOLATED": ("J1.1",),
            },
            unconnected_nets={"NC": ("R2.2", "R3.3")},
            dnp_components=("R3",),
            component_symbols={"R1": "Device:R", "R2": "Device:R", "R3": "Device:R"},
        )
        if observed
        else None
    )
    return saved_electrical_view(root, contract, netlist)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    shutil.copytree(reference_root(), root, ignore=shutil.ignore_patterns(".git", "build"))
    return root


def test_exact_net_has_authored_dispositions_and_one_component_hop(repository: Path) -> None:
    receipt = _saved(repository)
    report = build_connectivity_view(
        repository, receipt, "PILOT_B", Path("build/connectivity-view/observed")
    )
    assert report.authored_roles == ("GROUND_DOMAIN:PILOT_B",)
    assert report.source_status == "CURRENT"
    assert [(item.pin, item.status) for item in report.pins] == [
        ("R1.2", "AMBIGUOUS"),
        ("R2.2", "UNCONNECTED"),
        ("R3.1", "UNDECLARED"),
    ]
    assert [item.reference for item in report.components] == ["R1", "R3"]
    assert {item.net for item in report.components[0].other_nets} == {"OTHER"}
    assert {item.net for item in report.components[1].other_nets} == {None, "OTHER"}
    assert report.components[1].dnp
    assert (
        read_model(Path(report.output_directory) / "connectivity-view.json", ConnectivityViewReport)
        == report
    )
    page = (Path(report.output_directory) / "index.html").read_text(encoding="utf-8")
    assert "does not establish an internal conductive path" in page
    assert "ISOLATED" not in page


def test_unreviewed_and_historical_source_are_labeled(repository: Path) -> None:
    receipt = _saved(repository, observed=False)
    unreviewed = build_connectivity_view(repository, receipt, "PILOT_B")
    assert unreviewed.observation_status == "UNREVIEWED"
    assert not unreviewed.components
    assert all(item.status == "UNREVIEWED" for item in unreviewed.pins)
    with pytest.raises(ValueError, match="no exact authored or retained observation"):
        build_connectivity_view(repository, receipt, "PILOT_B_EXTRA")


def test_distinct_label_stale_source_and_changed_native_evidence(repository: Path) -> None:
    receipt = _saved(repository)
    selected = build_connectivity_view(repository, receipt, "PILOT_B_EXTRA")
    assert selected.authored_roles == ()
    assert selected.components[0].reference == "R1"
    pcb = repository / "examples/projects/controller/kicad/controller.kicad_pcb"
    pcb.write_bytes(pcb.read_bytes() + b"\n")
    assert build_connectivity_view(repository, receipt, "PILOT_B").source_status == "STALE"
    (receipt.parent / "netlist.xml").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed or is missing"):
        build_connectivity_view(repository, receipt, "PILOT_B")


def test_large_observed_net_is_bounded() -> None:
    observed = NetlistContract(
        components={},
        nets={"BUS": tuple(f"J{index}.1" for index in range(MAX_SELECTED_PINS + 1))},
    )
    with pytest.raises(ValueError, match="too many observed pins"):
        _neighborhoods("BUS", observed)


class _ConnectivityParity(McpParityHarness):
    async def _case_test_cli_mcp_connectivity_view_parity(self) -> None:
        receipt = _saved(self.root).relative_to(self.root).as_posix()
        cli = await self.cli(
            "kicad_tooling.connectivity_view",
            ConnectivityViewReport,
            "--receipt",
            receipt,
            "--net",
            "PILOT_B",
            "--output",
            "build/connectivity-view/cli",
        )
        arguments = {"receipt": receipt, "net": "PILOT_B", "view_id": "mcp"}
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue(
                (await client.call_tool("export_connectivity_view", arguments)).is_error
            )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "export_connectivity_view", ConnectivityViewReport, arguments
            )
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_cli_mcp_connectivity_view_parity() -> None:
    run_mcp_parity(_ConnectivityParity, "_case_test_cli_mcp_connectivity_view_parity")
