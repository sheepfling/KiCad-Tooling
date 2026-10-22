"""Keep design-lint contracts and results in bounded theme-owned model modules."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    connector_coverage_models,
    connector_part_id_peer_models,
    connector_peer_pin_models,
    design_lint_policy_models,
    pcb_touch_pad_clearance_models,
    power_rail_models,
    rc_filter_models,
    regulator_feedback_models,
    return_net_models,
    schematic_geometry_models,
    signal_pair_models,
)
from kicad_tooling.hwrepo import models as compatibility_models
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]

MODEL_OWNERS = {
    "connector_coverage_models.py": (
        connector_coverage_models,
        (
            "ConnectorMappedPinEvidence",
            "ConnectorCoverageEntry",
            "ConnectorCoverageReport",
            "ConnectorInterfaceReview",
            "ConnectorInventoryReview",
        ),
    ),
    "connector_peer_pin_models.py": (
        connector_peer_pin_models,
        (
            "ConnectorPeerPinHeuristicCoverage",
            "SimilarConnectorPinGroup",
        ),
    ),
    "connector_part_id_peer_models.py": (
        connector_part_id_peer_models,
        ("ConnectorPartIdPeerPinCoverage",),
    ),
    "power_rail_models.py": (power_rail_models, ("NumberedPowerRailGroup",)),
    "design_lint_policy_models.py": (
        design_lint_policy_models,
        ("DesignLintPolicy",),
    ),
    "rc_filter_models.py": (
        rc_filter_models,
        (
            "RcFilterRequirement",
            "RcFilterMap",
            "RcFilterCoverageEntry",
            "RcFilterCoverageReport",
        ),
    ),
    "regulator_feedback_models.py": (
        regulator_feedback_models,
        (
            "RegulatorDividerResistorRequirement",
            "RegulatorFeedbackRequirement",
            "RegulatorFeedbackMap",
            "RegulatorFeedbackCoverageEntry",
            "RegulatorFeedbackCoverageReport",
        ),
    ),
    "return_net_models.py": (return_net_models, ("ReturnNetGroup",)),
    "schematic_geometry_models.py": (
        schematic_geometry_models,
        ("SchematicGeometrySourceBinding", "SchematicGeometryCoverage"),
    ),
    "signal_pair_models.py": (
        signal_pair_models,
        ("ComplementaryPinFunctionAlias", "ComplementaryPinFunctionAliasMap"),
    ),
}
NEW_THEME_MODELS = (
    "PcbTouchPadClearanceRequirement",
    "PcbTouchPadClearanceMap",
    "PcbTouchPadClearanceRequestSet",
    "PcbTouchPadClearanceObservation",
    "PcbTouchPadClearanceCoverageEntry",
    "PcbTouchPadClearanceCoverageReport",
)
OSCILLATOR_OUTPUT_PATH_MODELS = (
    "OscillatorOutputLoadRequirement",
    "OscillatorOutputSeriesResistorRequirement",
    "OscillatorOutputPathRequirement",
    "OscillatorOutputPathMap",
)
SCHEMATIC_GEOMETRY_RULE_TYPES = (
    "SchematicGeometryRuleId",
    "SchematicGeometryRuleCoverageStatus",
)
CONNECTOR_PEER_PIN_TYPES = ("ConnectorPinRole",)


def _top_level_definitions(path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _top_level_assignment_names(path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def test_lint_models_have_bounded_owners_and_compatible_exports() -> None:
    registry = HWREPO / "models.py"
    registry_classes = _top_level_definitions(registry)
    for filename, (owner_module, model_names) in MODEL_OWNERS.items():
        owner = HWREPO / filename
        assert line_count(owner) < IMPLEMENTATION_MAX_LINES
        assert set(model_names) <= _top_level_definitions(owner)
        assert not (set(model_names) & registry_classes)
        for name in model_names:
            assert getattr(compatibility_models, name) is getattr(owner_module, name)


def test_new_touch_clearance_models_stay_in_their_theme_owner() -> None:
    owner_path = HWREPO / "pcb_touch_pad_clearance_models.py"
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(NEW_THEME_MODELS) <= _top_level_definitions(owner_path)
    assert all(
        getattr(pcb_touch_pad_clearance_models, name).__module__
        == pcb_touch_pad_clearance_models.__name__
        for name in NEW_THEME_MODELS
    )
    assert not (set(NEW_THEME_MODELS) & _top_level_definitions(HWREPO / "models.py"))
    assert all(not hasattr(compatibility_models, name) for name in NEW_THEME_MODELS)


def test_oscillator_output_path_models_stay_in_their_theme_owner() -> None:
    from kicad_tooling.hwrepo import oscillator_output_path_models

    owner_path = HWREPO / "oscillator_output_path_models.py"
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(OSCILLATOR_OUTPUT_PATH_MODELS) <= _top_level_definitions(owner_path)
    assert not (set(OSCILLATOR_OUTPUT_PATH_MODELS) & _top_level_definitions(HWREPO / "models.py"))
    assert all(not hasattr(compatibility_models, name) for name in OSCILLATOR_OUTPUT_PATH_MODELS)
    assert all(
        getattr(oscillator_output_path_models, name).__module__
        == oscillator_output_path_models.__name__
        for name in OSCILLATOR_OUTPUT_PATH_MODELS
    )


def test_schematic_geometry_rule_types_have_theme_owner_and_compatible_exports() -> None:
    owner_path = HWREPO / "schematic_geometry_models.py"
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(SCHEMATIC_GEOMETRY_RULE_TYPES) <= _top_level_assignment_names(owner_path)
    for name in SCHEMATIC_GEOMETRY_RULE_TYPES:
        assert getattr(compatibility_models, name) is getattr(schematic_geometry_models, name)


def test_connector_peer_pin_role_has_theme_owner_and_compatible_export() -> None:
    owner_path = HWREPO / "connector_peer_pin_models.py"
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(CONNECTOR_PEER_PIN_TYPES) <= _top_level_assignment_names(owner_path)
    for name in CONNECTOR_PEER_PIN_TYPES:
        assert getattr(compatibility_models, name) is getattr(connector_peer_pin_models, name)
    assert (
        connector_peer_pin_models.ConnectorPartIdPeerPinCoverage
        is connector_part_id_peer_models.ConnectorPartIdPeerPinCoverage
    )


def test_internal_services_import_lint_models_from_their_theme_owners() -> None:
    moved_names = {name for _, names in MODEL_OWNERS.values() for name in names}
    moved_names.update(NEW_THEME_MODELS)
    moved_names.update(OSCILLATOR_OUTPUT_PATH_MODELS)
    moved_names.update(SCHEMATIC_GEOMETRY_RULE_TYPES)
    moved_names.update(CONNECTOR_PEER_PIN_TYPES)
    legacy_imports: list[str] = []
    for path in sorted(HWREPO.rglob("*.py")):
        if path == HWREPO / "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (node.module == "models" or node.module.endswith(".models"))
            ):
                legacy_imports.extend(
                    f"{path.relative_to(REPO_ROOT).as_posix()}:{alias.name}"
                    for alias in node.names
                    if alias.name in moved_names
                )

    assert not legacy_imports, (
        "Internal services must import lint models from their owner modules; "
        f"legacy imports: {sorted(legacy_imports)}"
    )


def test_design_lint_policy_imports_typed_maps_from_theme_owners() -> None:
    policy_path = HWREPO / "design_lint_policy_models.py"
    tree = ast.parse(policy_path.read_text(encoding="utf-8"), filename=policy_path.name)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        in {
            "pcb_touch_pad_clearance_models",
            "oscillator_output_path_models",
            "rc_filter_models",
            "regulator_feedback_models",
            "signal_pair_models",
        }
        for alias in node.names
    }

    assert {
        "PcbTouchPadClearanceMap",
        "OscillatorOutputPathMap",
        "RcFilterMap",
        "RegulatorFeedbackMap",
        "ComplementaryPinFunctionAliasMap",
    } <= imported
