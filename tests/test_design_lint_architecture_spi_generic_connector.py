"""Keep the generic SPI connector triad rule in focused theme modules."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]

RULE_ID = "bus.spi_generic_connector_triad_review"
MODULES = (
    "connector_contact_evidence.py",
    "spi_generic_connector_models.py",
    "spi_generic_connector_candidates.py",
    "design_lint_spi_generic_connector_candidates.py",
    "design_lint_spi_generic_connector_candidate_evidence.py",
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_predicate_has_a_protocol_owned_implementation() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/spi_generic_connector_candidates.py#generic_spi_connector_triads"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/connector_contact_evidence.py#collect_other_connector_contacts"
        in rule.implementation_refs
    )
    assert (
        "kicad_tooling/hwrepo/connector_contact_evidence.py#format_other_connector_contacts"
        in rule.implementation_refs
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_spi_generic_connector_modules_stay_below_review_limit() -> None:
    counts = {
        name: len((HWREPO / name).read_text(encoding="utf-8").splitlines()) for name in MODULES
    }

    assert all(count < 500 for count in counts.values()), counts


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bus_candidate_dispatcher_delegates_without_constructing_findings() -> None:
    facade = HWREPO / "design_lint_bus_candidates.py"
    tree = ast.parse(facade.read_text(encoding="utf-8"), filename=facade.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bus_candidates"
    )
    calls = {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "spi_protocol_bus_candidates" in calls
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
        for node in ast.walk(function)
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_protocol_bus_service_delegates_to_generic_connector_rule() -> None:
    module = HWREPO / "design_lint_spi_bus_candidates.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "generic_spi_connector_triad_review_candidates" in calls


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_each_rule_predicate_imports_shared_spi_role_recognition() -> None:
    module = HWREPO / "spi_generic_connector_candidates.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
    imports = {
        (node.module, alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert ("spi_participants", "spi_signal_role_and_channel") in imports
    assert ("spi_role_assignments", "spi_role_assignment_groups") in imports


def test_local_spi_connector_rule_files_exist() -> None:
    assert all((HWREPO / name).is_file() for name in MODULES)
    assert (Path(__file__).parent / "design_lint_fixtures/spi_generic_connector_triad.py").is_file()
