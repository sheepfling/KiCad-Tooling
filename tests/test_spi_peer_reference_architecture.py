"""Architecture boundaries for the SPI shared-clock reference lint."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, spi_peer_reference_models

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

ROOT = Path(__file__).resolve().parents[1]
HWREPO = ROOT / "kicad_tooling" / "hwrepo"
EXPECTED_MODELS = {"SpiClockPeerCoverage", "SpiPeerReferenceCoverageReport"}


def test_spi_peer_reference_models_stay_in_their_theme_owner() -> None:
    owner = HWREPO / "spi_peer_reference_models.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    definitions = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}

    assert EXPECTED_MODELS <= definitions
    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert all(not hasattr(models, name) for name in EXPECTED_MODELS)
    assert spi_peer_reference_models.SpiPeerReferenceCoverageReport.__module__.endswith(
        "spi_peer_reference_models"
    )
    coverage_tree = ast.parse(
        (HWREPO / "spi_peer_reference_coverage.py").read_text(encoding="utf-8")
    )
    imported = {
        alias.name
        for node in ast.walk(coverage_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "spi_peer_reference_models"
        for alias in node.names
    }
    assert imported == {"SpiClockPeerCoverage", "SpiPeerReferenceCoverageReport"}


def test_spi_peer_reference_owner_and_protocol_modules_stay_focused() -> None:
    modules = (
        "spi_peer_reference_models.py",
        "spi_peer_reference_scan.py",
        "spi_peer_reference_coverage.py",
        "design_lint_spi_candidates.py",
    )
    sizes = {
        name: len((HWREPO / name).read_text(encoding="utf-8").splitlines()) for name in modules
    }

    assert all(size < 500 for size in sizes.values()), sizes

    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(
        item for item in catalog["rules"] if item["rule_id"] == "bus.spi_peer_reference_review"
    )
    owner = "kicad_tooling/hwrepo/spi_peer_reference_scan.py#scan_spi_peer_references"
    assert rule["status"] == "active"
    assert rule["theme"] == "interfaces"
    assert rule["implementation_owner"] == owner
    assert owner in rule["implementation_refs"]


def test_bus_candidate_coordinator_delegates_spi_in_stable_order() -> None:
    coordinator = HWREPO / "design_lint_bus_candidates.py"
    tree = ast.parse(coordinator.read_text(encoding="utf-8"), filename=coordinator.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bus_candidates"
    )
    calls = sorted(
        (node.lineno, node.func.id)
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )
    names = [name for _, name in calls]
    assert (
        names.index("i2c_peer_reference_candidates")
        < names.index("spi_peer_reference_candidates")
        < names.index("spi_bias_candidates")
    )
    assert not any(name == "Candidate" for name in names)
