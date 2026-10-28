"""Keep the mapped RS-485 reference review in focused interface-owned modules."""

from __future__ import annotations

import ast
import json

import pytest

from kicad_tooling.hwrepo import models, rs485_peer_reference_models
from tests.lint_architecture_support import (
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

HWREPO = REPO_ROOT / "kicad_tooling/hwrepo"
MODEL_NAMES = frozenset({"Rs485PeerReferencePairCoverage", "Rs485PeerReferenceCoverageReport"})
MODULES = (
    "kicad_tooling/hwrepo/rs485_peer_reference_types.py",
    "kicad_tooling/hwrepo/rs485_peer_reference_models.py",
    "kicad_tooling/hwrepo/rs485_peer_reference_scan.py",
    "kicad_tooling/hwrepo/rs485_peer_reference_coverage.py",
    "kicad_tooling/hwrepo/design_lint_rs485_candidates.py",
    "kicad_tooling/ci_hosted_rs485_peer_reference.py",
    "tests/rs485_peer_reference_support.py",
    "tests/test_rs485_peer_reference_review.py",
    "tests/test_rs485_peer_reference_architecture.py",
    "tests/test_design_lint_mcp_parity_rs485_reference.py",
    "tests/test_rs485_peer_reference_native_fixture_lane.py",
)


def test_coverage_models_have_a_protocol_owner() -> None:
    owner = HWREPO / "rs485_peer_reference_models.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    definitions = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}

    assert MODEL_NAMES <= definitions
    assert not any(hasattr(models, name) for name in MODEL_NAMES)
    assert rs485_peer_reference_models.Rs485PeerReferenceCoverageReport.__module__.endswith(
        "rs485_peer_reference_models"
    )


def test_protocol_and_regression_modules_stay_below_review_limit() -> None:
    sizes = {name: line_count(REPO_ROOT / name) for name in MODULES}
    oversized = {name: size for name, size in sizes.items() if size >= IMPLEMENTATION_MAX_LINES}

    assert not oversized, f"Split RS-485 modules before they become god files: {oversized}"


def test_catalog_owns_the_predicate_in_the_rs485_scan_module() -> None:
    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    rule = next(
        item for item in catalog["rules"] if item["rule_id"] == "bus.rs485_peer_reference_review"
    )
    owner = "kicad_tooling/hwrepo/rs485_peer_reference_scan.py#scan_rs485_peer_references"
    source = (REPO_ROOT / "kicad_tooling/hwrepo/rs485_peer_reference_scan.py").read_text(
        encoding="utf-8"
    )

    assert rule["status"] == "active"
    assert rule["theme"] == "interfaces"
    assert rule["implementation_owner"] == owner
    assert owner in rule["implementation_refs"]
    assert "def scan_rs485_peer_references(" in source


def test_coverage_services_import_models_from_the_theme_owner() -> None:
    for filename, expected in (
        ("rs485_peer_reference_coverage.py", MODEL_NAMES),
        ("design_lint_evaluation_types.py", {"Rs485PeerReferenceCoverageReport"}),
        ("design_lint_report_models.py", {"Rs485PeerReferenceCoverageReport"}),
    ):
        path = HWREPO / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=filename)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module == "rs485_peer_reference_models"
            for alias in node.names
        }
        assert expected <= imported, f"{filename} must import the protocol-owned models"


def test_parity_and_native_regressions_keep_focused_markers() -> None:
    expected = {
        "test_rs485_peer_reference_review.py": {"design_lint", "interface_lint"},
        "test_design_lint_mcp_parity_rs485_reference.py": {
            "design_lint",
            "interface_lint",
            "parity_lint",
            "slow",
        },
        "test_rs485_peer_reference_native_fixture_lane.py": {
            "design_lint",
            "interface_lint",
            "native_kicad",
            "slow",
        },
    }
    for filename, markers in expected.items():
        source = (REPO_ROOT / "tests" / filename).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=filename)
        module_markers = {
            node.attr
            for statement in tree.body
            if isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "pytestmark"
                for target in statement.targets
            )
            for node in ast.walk(statement.value)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "pytest"
            and node.value.attr == "mark"
        }
        assert markers <= module_markers, (
            f"{filename} lost focused markers: {markers - module_markers}"
        )
