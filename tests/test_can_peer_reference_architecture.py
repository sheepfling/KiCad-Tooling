"""Keep CAN reference review models and analysis in protocol-owned modules."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import can_peer_reference_models
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

CAN_REFERENCE_MODELS = frozenset(
    {
        "CanPeerReferenceBusCoverage",
        "CanPeerReferenceCoverageReport",
    }
)
CAN_REFERENCE_MODULES = (
    "can_peer_reference_models.py",
    "can_peer_reference_scan.py",
    "can_peer_reference_coverage.py",
    "design_lint_can_candidates.py",
    "peer_reference_assignments.py",
)


def test_can_reference_coverage_models_have_a_protocol_owner() -> None:
    owner = HWREPO / "can_peer_reference_models.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    definitions = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}

    assert CAN_REFERENCE_MODELS <= definitions
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert all(not hasattr(shared_models, name) for name in CAN_REFERENCE_MODELS)
    assert can_peer_reference_models.CanPeerReferenceCoverageReport.__module__.endswith(
        "can_peer_reference_models"
    )


def test_can_reference_services_import_models_from_the_theme_owner() -> None:
    expected_by_service = {
        "can_peer_reference_coverage.py": CAN_REFERENCE_MODELS,
        "design_lint_evaluation_types.py": {"CanPeerReferenceCoverageReport"},
        "design_lint_peer_evaluation.py": {"CanPeerReferenceCoverageReport"},
        "design_lint_report_models.py": {"CanPeerReferenceCoverageReport"},
    }
    for filename, expected_names in expected_by_service.items():
        source = HWREPO / filename
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=filename)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module == "can_peer_reference_models"
            for alias in node.names
        }
        assert expected_names <= imports

    misplaced: list[str] = []
    for source in sorted(HWREPO.glob("*.py")):
        if source.name == "models.py":
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=source.name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 1 or node.module != "models":
                continue
            misplaced.extend(
                f"{source.name}:{alias.name}"
                for alias in node.names
                if alias.name in CAN_REFERENCE_MODELS
            )
    assert not misplaced, f"CAN reference services must import their theme owner: {misplaced}"


def test_can_reference_protocol_modules_stay_focused() -> None:
    modules = [HWREPO / name for name in CAN_REFERENCE_MODULES]
    assert all(path.is_file() for path in modules)
    oversized = {
        path.name: line_count(path)
        for path in modules
        if line_count(path) >= IMPLEMENTATION_MAX_LINES
    }
    assert not oversized, f"Keep CAN peer-reference modules below 500 lines: {oversized}"

    for scan_name in (
        "i2c_peer_reference_scan.py",
        "spi_peer_reference_scan.py",
        "can_peer_reference_scan.py",
    ):
        tree = ast.parse((HWREPO / scan_name).read_text(encoding="utf-8"), filename=scan_name)
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module == "peer_reference_assignments"
            for node in tree.body
        ), f"{scan_name} must reuse shared return-pin evidence"
