"""Authored power rail diagram, native membership, and CLI/MCP parity."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical_analysis_contract_models import ElectricalAnalysisContract
from kicad_tooling.hwrepo.electrical_simulation_models import PowerAnalysis
from kicad_tooling.hwrepo.electrical_view_evidence import load_electrical_view_evidence
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.netlist_membership import net_pin_membership
from kicad_tooling.hwrepo.power_tree_view import build_power_tree_view
from kicad_tooling.hwrepo.power_tree_view_models import PowerTreeViewReport
from tests.electrical_power_connectivity_support import (
    power_connectivity_netlist,
    power_connectivity_requirement,
)
from tests.electrical_simulation_support import ISLAND, install_fixture
from tests.electrical_view_support import saved_electrical_view
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.support import reference_root

pytestmark = pytest.mark.template_checkout


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    shutil.copytree(reference_root(), root, ignore=shutil.ignore_patterns(".git", "build"))
    return root


def authored_contract(
    root: Path,
    *,
    budget_failure: bool = False,
    source_selection: Literal["all", "any"] = "all",
) -> ElectricalAnalysisContract:
    contract = install_fixture(root)
    power = contract.power
    if budget_failure:
        assert isinstance(power, PowerAnalysis)
        rail = power.rails[0].model_copy(
            update={
                "continuous_limit_a": 0.01,
                "peak_limit_a": 1.0,
                "peak_duration_limit_s": 0.0005,
            }
        )
        power = power.model_copy(update={"rails": (rail,)})
    updated = contract.model_copy(
        update={
            "power": power,
            "power_connectivity": power_connectivity_requirement(source_selection=source_selection),
        }
    )
    project_contract = root / ISLAND / "tests/electrical.json"
    write_model(project_contract, updated)
    return read_model(project_contract, ElectricalAnalysisContract)


def test_authored_rail_and_budget_join_exact_native_membership(repository: Path) -> None:
    contract = authored_contract(repository)
    observed = power_connectivity_netlist()
    receipt = saved_electrical_view(repository, contract, observed)
    view = build_power_tree_view(repository, receipt, "supply", Path("build/power-tree-view/valid"))
    assert view.observation_status == "RETAINED"
    assert view.source_status == "CURRENT"
    assert view.analysis_status == "PASS"
    assert view.net == "VIN_IN"
    assert [item.check_status for item in (*view.source_groups, *view.loads)] == ["PASS", "PASS"]
    assert view.source_groups[0].selection == "all"
    assert view.source_groups[0].endpoints[0].observed_symbol == "Synthetic:PowerInput"
    assert view.source_groups[0].endpoints[0].observed_dnp is False
    assert view.budget is not None
    assert (view.budget.steady_status, view.budget.startup_status) == ("PASS", "PASS")
    assert view.budget.steady_demand_a == 0.05
    assert view.analysis_source_sha256
    assert not view.undeclared_pins
    path = Path(view.output_directory)
    assert read_model(path / "power-tree-view.json", PowerTreeViewReport) == view
    assert digest(path / "index.html") == view.artifacts_sha256["index.html"]
    html = (path / "index.html").read_text(encoding="utf-8")
    assert "Sources" in html and "Loads" in html
    assert "simultaneous-load budget, not measured current" in html
    assert "https://" not in html and "http://" not in html


def test_pin_reference_case_matches_canonical_power_check() -> None:
    observed = power_connectivity_netlist()
    observed = observed.model_copy(
        update={"nets": {**observed.nets, "VIN_IN": (*observed.nets["VIN_IN"], "X1.1", "x1.1")}}
    )
    rows = net_pin_membership("VIN_IN", ("j40.1",), observed)
    assert rows[0].status == "MATCH"
    assert all(item.pin.casefold() != "j40.1" for item in rows[1:])
    assert sum(item.pin.casefold() == "x1.1" for item in rows if item.status == "UNDECLARED") == 1


def test_faults_keep_wrong_ambiguous_unconnected_and_extra_pins(repository: Path) -> None:
    contract = authored_contract(repository, budget_failure=True)
    observed = power_connectivity_netlist(fault="source-wrong-net")
    nets = dict(observed.nets)
    nets["VIN_IN"] = (*nets["VIN_IN"], "X1.1")
    nets["VIN_IN_EXTRA"] = ("J41.1",)
    nets["VIN_IN"] = tuple(pin for pin in nets["VIN_IN"] if pin != "U41.1")
    observed = observed.model_copy(update={"nets": nets, "unconnected_nets": {"NC": ("U41.1",)}})
    receipt = saved_electrical_view(repository, contract, observed)
    view = build_power_tree_view(repository, receipt, "supply")
    sources = view.source_groups[0]
    assert sources.check_status == "FAIL"
    assert [(endpoint.reference, endpoint.pins[0].status) for endpoint in sources.endpoints] == [
        ("J40", "DIFFERENT"),
        ("J41", "AMBIGUOUS"),
    ]
    assert view.loads[0].check_status == "FAIL"
    assert view.loads[0].endpoints[1].pins[0].status == "UNCONNECTED"
    assert [(pin.pin, pin.status) for pin in view.undeclared_pins] == [("X1.1", "UNDECLARED")]
    assert view.budget is not None
    assert (
        view.budget.steady_status,
        view.budget.startup_status,
        view.budget.duration_status,
    ) == ("FAIL", "FAIL", "FAIL")
    (receipt.parent / "netlist.xml").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed or is missing"):
        build_power_tree_view(repository, receipt, "supply")


def test_alternative_source_can_pass_with_unmatched_option(repository: Path) -> None:
    contract = authored_contract(repository, source_selection="any")
    observed = power_connectivity_netlist(fault="source-wrong-net")
    receipt = saved_electrical_view(repository, contract, observed)
    view = build_power_tree_view(repository, receipt, "supply")
    assert view.source_groups[0].check_status == "PASS"
    assert [item.pins[0].status for item in view.source_groups[0].endpoints] == [
        "DIFFERENT",
        "MATCH",
    ]


def test_alternative_source_keeps_dnp_identity_visible(repository: Path) -> None:
    contract = authored_contract(repository, source_selection="any")
    receipt = saved_electrical_view(
        repository, contract, power_connectivity_netlist(fault="source-dnp")
    )
    view = build_power_tree_view(repository, receipt, "supply")
    assert view.source_groups[0].check_status == "PASS"
    assert [item.observed_dnp for item in view.source_groups[0].endpoints] == [True, False]
    assert all(item.observed_component == "RETAINED" for item in view.source_groups[0].endpoints)


def test_saved_native_observation_does_not_claim_changed_source(repository: Path) -> None:
    contract = authored_contract(repository)
    receipt = saved_electrical_view(repository, contract, power_connectivity_netlist())
    pcb = repository / ISLAND / "kicad/controller.kicad_pcb"
    pcb.write_bytes(pcb.read_bytes() + b"\n")
    view = build_power_tree_view(repository, receipt, "supply")
    assert view.source_status == "STALE"
    assert view.observation_status == "RETAINED"
    assert "STALE" in (Path(view.output_directory) / "index.html").read_text(encoding="utf-8")


def test_changed_source_during_view_creation_is_rejected(repository: Path) -> None:
    contract = authored_contract(repository)
    receipt = saved_electrical_view(repository, contract, power_connectivity_netlist())
    selected = load_electrical_view_evidence(repository, receipt)
    assert selected.source_status == "CURRENT"
    pcb = repository / ISLAND / "kicad/controller.kicad_pcb"
    pcb.write_bytes(pcb.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="source changed during view creation"):
        selected.verify()


def test_missing_authored_map_is_rejected(repository: Path) -> None:
    contract = install_fixture(repository)
    receipt = saved_electrical_view(repository, contract, None)
    with pytest.raises(ValueError, match="authored power-connectivity"):
        build_power_tree_view(repository, receipt, "supply")


def test_unreviewed_observation_and_exact_rail_selection(repository: Path) -> None:
    contract = authored_contract(repository)
    receipt = saved_electrical_view(repository, contract, None)
    view = build_power_tree_view(repository, receipt, "supply")
    assert view.observation_status == "UNREVIEWED"
    assert all(item.check_status == "UNREVIEWED" for item in (*view.source_groups, *view.loads))
    assert all(
        pin.status == "UNREVIEWED"
        for item in (*view.source_groups, *view.loads)
        for endpoint in item.endpoints
        for pin in endpoint.pins
    )
    assert all(
        endpoint.observed_component == "UNREVIEWED"
        for item in (*view.source_groups, *view.loads)
        for endpoint in item.endpoints
    )
    with pytest.raises(ValueError, match="exact authored power rail"):
        build_power_tree_view(repository, receipt, "SUPPLY")


class _PowerTreeParity(McpParityHarness):
    async def _case_test_cli_mcp_power_tree_view_parity(self) -> None:
        contract = authored_contract(self.root)
        receipt = saved_electrical_view(self.root, contract, power_connectivity_netlist())
        cli = await self.cli(
            "kicad_tooling.power_tree_view",
            PowerTreeViewReport,
            "--receipt",
            str(receipt),
            "--rail",
            "supply",
            "--output",
            "build/power-tree-view/cli",
        )
        args = {
            "receipt": receipt.relative_to(self.root).as_posix(),
            "rail": "supply",
            "view_id": "mcp",
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue((await client.call_tool("export_power_tree_view", args)).is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "export_power_tree_view", PowerTreeViewReport, args)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


@pytest.mark.slow
def test_cli_mcp_power_tree_view_parity() -> None:
    run_mcp_parity(_PowerTreeParity, "_case_test_cli_mcp_power_tree_view_parity")
