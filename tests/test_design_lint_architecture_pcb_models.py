"""Guard PCB model ownership and compatibility boundaries by theme."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import (
    models as shared_models,
)
from kicad_tooling.hwrepo import (
    pcb_board_only_footprint_models,
    pcb_component_inventory_models,
    pcb_component_population,
    pcb_component_values,
    pcb_decoupling_models,
    pcb_drc_models,
    pcb_pad_net_comparison,
    pcb_pad_net_models,
    pcb_reference_plane_models,
    pcb_return_path_models,
    pcb_rf_antenna_models,
    pcb_switching_loop_models,
    pcb_track_width_models,
    pcb_variant_population_capture,
)
from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.architecture]

PCB_RETURN_PATH_MODEL_NAMES = (
    "PcbReturnEndpointRequirement",
    "PcbReturnBondRequirement",
    "PcbReturnDomainRequirement",
    "PcbReturnPathsAnalysis",
)

PCB_RF_ANTENNA_MODEL_NAMES = (
    "PcbRfAntennaPolygon",
    "PcbRfAntennaKeepout",
    "PcbRfModuleAntennaRequirement",
    "PcbRfModuleAntennaMap",
    "PcbRfModuleAntennaCoverageEntry",
    "PcbRfModuleAntennaCoverageReport",
)

PCB_DRC_MODEL_NAMES = (
    "PcbDrcMinMaxRequirement",
    "PcbDrcMaximumRequirement",
    "PcbDrcPadSelectorPattern",
    "PcbSignalPathRequirement",
    "PcbSignalPathBundleRequirement",
    "PcbSignalPathRuleMap",
    "PcbDifferentialPairRuleRequirement",
    "PcbDifferentialPairRuleMap",
    "PcbDrcConstraintName",
    "PcbDrcConstraintCoverageStatus",
    "PcbDrcConstraintCoverage",
    "PcbDifferentialPairRuleCoverageEntry",
    "PcbDifferentialPairRuleCoverageReport",
    "PcbSignalPathRuleCoverageEntry",
    "PcbSignalPathRuleCoverageReport",
)

PCB_DECOUPLING_MODEL_NAMES = (
    "PcbDecouplingCandidateObservation",
    "PcbDecouplingCoverageEntry",
    "PcbDecouplingCoverageReport",
)

PCB_TRACK_WIDTH_MODEL_NAMES = (
    "PcbTrackWidthRequirement",
    "PcbTrackWidthMap",
    "PcbTrackWidthMeasurement",
    "PcbTrackWidthCoverageEntry",
    "PcbTrackWidthCoverageReport",
)

PCB_REFERENCE_PLANE_MODEL_NAMES = (
    "PcbReferencePlaneRequirement",
    "PcbReferencePlaneMap",
    "PcbReferencePlaneTrackMeasurement",
    "PcbReferencePlaneCoverageEntry",
    "PcbReferencePlaneCoverageReport",
)

PCB_SWITCHING_LOOP_MODEL_NAMES = (
    "PcbSwitchingLoopPad",
    "PcbSwitchingLoopEdge",
    "PcbSwitchingLoopRequirement",
    "PcbSwitchingLoopMap",
    "PcbSwitchingLoopRouteEdgeCoverage",
    "PcbSwitchingLoopCoverageEntry",
    "PcbSwitchingLoopCoverageReport",
)

SHARED_MODEL_PRIMITIVE_NAMES = (
    "StrictModel",
    "Identifier",
    "ResistorReference",
    "Stm32PortPin",
    "Stm32SymbolPin",
    "Reference",
    "Digest",
    "NativePcbUuid",
    "GitCommit",
    "RepositoryPath",
    "NonEmptyText",
    "NetName",
    "UsbDataPortGroup",
    "TemplateVersion",
    "PositiveCount",
    "NonNegativeCount",
    "PositiveMeasure",
    "CapacitancePf",
    "NonNegativeCapacitancePf",
)

SHARED_MODEL_REGISTRY_MAX_LINES = 5_593


def _top_level_definitions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    defined_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            defined_names.add(node.name)
        elif isinstance(node, ast.Assign):
            defined_names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_names.add(node.target.id)
    return defined_names


def _legacy_shared_model_imports(names: tuple[str, ...]) -> list[str]:
    legacy_imports: list[str] = []
    for path in sorted((REPO_ROOT / "kicad_tooling").rglob("*.py")):
        if path == HWREPO / "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (node.module == "models" or node.module.endswith(".models"))
                and any(alias.name in names for alias in node.names)
            ):
                legacy_imports.append(path.relative_to(REPO_ROOT).as_posix())
    return sorted(set(legacy_imports))


def test_pcb_drc_models_have_a_theme_owner_and_compatibility_exports() -> None:
    owner = HWREPO / "pcb_drc_models.py"
    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert set(PCB_DRC_MODEL_NAMES) <= _top_level_definitions(owner)
    for name in PCB_DRC_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(pcb_drc_models, name)


def test_internal_pcb_drc_services_import_models_from_the_theme_owner() -> None:
    legacy_imports = _legacy_shared_model_imports(PCB_DRC_MODEL_NAMES)
    assert not legacy_imports, (
        "Internal PCB DRC services should import models from pcb_drc_models; "
        f"legacy imports: {legacy_imports}"
    )


def test_pcb_decoupling_models_have_a_theme_owner_and_compatibility_exports() -> None:
    owner = HWREPO / "pcb_decoupling_models.py"

    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert set(PCB_DECOUPLING_MODEL_NAMES) <= _top_level_definitions(owner)
    for name in PCB_DECOUPLING_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(pcb_decoupling_models, name)


def test_internal_pcb_decoupling_services_import_models_from_the_theme_owner() -> None:
    legacy_imports = _legacy_shared_model_imports(PCB_DECOUPLING_MODEL_NAMES)

    assert not legacy_imports, (
        "Internal PCB decoupling services should import models from pcb_decoupling_models; "
        f"legacy imports: {legacy_imports}"
    )


def test_pcb_track_width_models_have_a_theme_owner_and_compatibility_exports() -> None:
    owner = HWREPO / "pcb_track_width_models.py"

    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert set(PCB_TRACK_WIDTH_MODEL_NAMES) <= _top_level_definitions(owner)
    for name in PCB_TRACK_WIDTH_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(pcb_track_width_models, name)


def test_internal_pcb_track_width_services_import_models_from_the_theme_owner() -> None:
    legacy_imports = _legacy_shared_model_imports(PCB_TRACK_WIDTH_MODEL_NAMES)

    assert not legacy_imports, (
        "Internal PCB track-width services should import models from pcb_track_width_models; "
        f"legacy imports: {legacy_imports}"
    )


def test_pcb_reference_plane_models_have_a_theme_owner_and_compatibility_exports() -> None:
    owner = HWREPO / "pcb_reference_plane_models.py"

    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert set(PCB_REFERENCE_PLANE_MODEL_NAMES) <= _top_level_definitions(owner)
    for name in PCB_REFERENCE_PLANE_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(pcb_reference_plane_models, name)


def test_internal_pcb_reference_plane_services_import_models_from_the_theme_owner() -> None:
    legacy_imports = _legacy_shared_model_imports(PCB_REFERENCE_PLANE_MODEL_NAMES)

    assert not legacy_imports, (
        "Internal PCB reference-plane services should import models from "
        f"pcb_reference_plane_models; legacy imports: {legacy_imports}"
    )


def test_pcb_switching_loop_models_have_a_theme_owner_and_compatibility_exports() -> None:
    owner = HWREPO / "pcb_switching_loop_models.py"

    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert set(PCB_SWITCHING_LOOP_MODEL_NAMES) <= _top_level_definitions(owner)
    for name in PCB_SWITCHING_LOOP_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(pcb_switching_loop_models, name)


def test_internal_pcb_switching_loop_services_import_models_from_the_theme_owner() -> None:
    legacy_imports = _legacy_shared_model_imports(PCB_SWITCHING_LOOP_MODEL_NAMES)

    assert not legacy_imports, (
        "Internal PCB switching-loop services should import models from "
        f"pcb_switching_loop_models; legacy imports: {legacy_imports}"
    )


def test_pcb_return_path_models_have_a_theme_owner_and_compatibility_exports() -> None:
    owner = HWREPO / "pcb_return_path_models.py"
    registry = HWREPO / "models.py"
    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert set(PCB_RETURN_PATH_MODEL_NAMES) <= _top_level_definitions(owner)
    registry_tree = ast.parse(registry.read_text(encoding="utf-8"), filename=registry.name)
    registry_definitions = {
        node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)
    }
    assert not (set(PCB_RETURN_PATH_MODEL_NAMES) & registry_definitions)
    for name in PCB_RETURN_PATH_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(pcb_return_path_models, name)


def test_internal_pcb_return_services_import_models_from_the_theme_owner() -> None:
    moved_names = set(PCB_RETURN_PATH_MODEL_NAMES)
    registry = HWREPO / "models.py"
    legacy_imports: list[str] = []
    for path in sorted((REPO_ROOT / "kicad_tooling").rglob("*.py")):
        if path == registry:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.rsplit(".", 1)[-1] == "models"
                and any(alias.name in moved_names for alias in node.names)
            ):
                legacy_imports.append(path.relative_to(REPO_ROOT).as_posix())
    assert not legacy_imports, (
        "Internal PCB services should import return-path models from their theme owner; "
        f"legacy imports: {sorted(set(legacy_imports))}"
    )


def test_rf_antenna_models_have_a_theme_owner_and_compatibility_exports() -> None:
    owner = HWREPO / "pcb_rf_antenna_models.py"
    primitives = HWREPO / "model_primitives.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    defined_models = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert _line_count(primitives) < IMPLEMENTATION_MAX_LINES
    assert set(PCB_RF_ANTENNA_MODEL_NAMES) <= defined_models
    for name in PCB_RF_ANTENNA_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(pcb_rf_antenna_models, name)


def test_pcb_population_review_keeps_its_model_and_predicate_in_the_pcb_theme() -> None:
    model = pcb_component_inventory_models.PcbPopulationMismatch
    evidence_model = pcb_component_inventory_models.PcbVariantPopulationEvidence
    coverage_model = pcb_component_inventory_models.PcbVariantPopulationCoverage
    owner = pcb_component_population

    assert model.__module__.endswith("pcb_component_inventory_models")
    assert not hasattr(shared_models, "PcbPopulationMismatch")
    assert evidence_model.__module__.endswith("pcb_component_inventory_models")
    assert coverage_model.__module__.endswith("pcb_component_inventory_models")
    assert not hasattr(shared_models, "PcbVariantPopulationEvidence")
    assert not hasattr(shared_models, "PcbVariantPopulationCoverage")
    assert _line_count(HWREPO / "pcb_component_population.py") < IMPLEMENTATION_MAX_LINES
    assert _line_count(HWREPO / "pcb_variant_population_capture.py") < IMPLEMENTATION_MAX_LINES
    assert _line_count(HWREPO / "design_lint_pcb_component_inventory_scan.py") < (
        IMPLEMENTATION_MAX_LINES
    )
    assert _line_count(HWREPO / "pcb_variant_probe.py.in") < IMPLEMENTATION_MAX_LINES
    assert _line_count(REPO_ROOT / "kicad_tooling/ci_hosted_pcb_variant_population_fixture.py") < (
        IMPLEMENTATION_MAX_LINES
    )
    assert callable(owner.compare_schematic_pcb_population)
    assert callable(owner.compare_variant_population_source)
    assert callable(pcb_variant_population_capture.capture_variant_population)
    assert callable(pcb_variant_population_capture.run_variant_native_command)

    catalog = (HWREPO / "design-lint-rules.json").read_text(encoding="utf-8")
    assert (
        '"implementation_owner": "kicad_tooling/hwrepo/pcb_component_population.py#'
        'compare_schematic_pcb_population"'
    ) in catalog
    assert "compare_variant_population_source" in catalog
    assert "capture_variant_population" in catalog


def test_pcb_value_review_keeps_its_predicate_in_a_focused_pcb_module() -> None:
    model = pcb_component_inventory_models.PcbComponentValueMismatch
    owner = pcb_component_values

    assert model.__module__.endswith("pcb_component_inventory_models")
    assert not hasattr(shared_models, "PcbComponentValueMismatch")
    assert _line_count(HWREPO / "pcb_component_values.py") < IMPLEMENTATION_MAX_LINES
    assert callable(owner.compare_schematic_pcb_values)

    catalog = (HWREPO / "design-lint-rules.json").read_text(encoding="utf-8")
    assert (
        '"implementation_owner": "kicad_tooling/hwrepo/pcb_component_values.py#'
        'compare_schematic_pcb_values"'
    ) in catalog


def test_pcb_pad_net_review_keeps_its_predicate_and_model_in_thematic_modules() -> None:
    model = pcb_pad_net_models.PcbSchematicBoardPadNetMismatch
    owner = pcb_pad_net_comparison

    assert model.__module__.endswith("pcb_pad_net_models")
    assert not hasattr(shared_models, "PcbSchematicBoardPadNetMismatch")
    assert _line_count(HWREPO / "pcb_pad_net_models.py") < IMPLEMENTATION_MAX_LINES
    assert _line_count(HWREPO / "pcb_pad_net_comparison.py") < IMPLEMENTATION_MAX_LINES
    assert callable(owner.compare_schematic_pcb_pad_nets)

    catalog = (HWREPO / "design-lint-rules.json").read_text(encoding="utf-8")
    assert (
        '"implementation_owner": "kicad_tooling/hwrepo/pcb_pad_net_comparison.py#'
        'compare_schematic_pcb_pad_nets"'
    ) in catalog


def test_internal_pcb_pad_net_services_import_models_from_the_theme_owner() -> None:
    legacy_imports: list[str] = []
    for path in sorted(HWREPO.glob("*.py")):
        if path.name == "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.level == 1
                and node.module == "models"
                and any(alias.name == "PcbSchematicBoardPadNetMismatch" for alias in node.names)
            ):
                legacy_imports.append(path.name)
    assert not legacy_imports, (
        "Internal PCB services should import pad net models from their theme owner; "
        f"legacy imports: {sorted(set(legacy_imports))}"
    )


def test_pcb_services_import_rf_models_from_the_theme_owner() -> None:
    legacy_imports: list[str] = []
    for path in sorted(HWREPO.glob("*.py")):
        if path.name == "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.level == 1
                and node.module == "models"
                and any(alias.name in PCB_RF_ANTENNA_MODEL_NAMES for alias in node.names)
            ):
                legacy_imports.append(path.name)
    assert not legacy_imports, (
        "Internal PCB services should import RF antenna models from their theme owner; "
        f"legacy imports: {sorted(set(legacy_imports))}"
    )


def test_shared_model_registry_is_shrink_only() -> None:
    registry = HWREPO / "models.py"

    assert _line_count(registry) <= SHARED_MODEL_REGISTRY_MAX_LINES


def test_shared_model_primitives_have_one_definition_owner() -> None:
    def defined_names(path: Path) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                names.update(target.id for target in node.targets if isinstance(target, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
        return names

    owner = HWREPO / "model_primitives.py"
    registry = HWREPO / "models.py"
    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert set(SHARED_MODEL_PRIMITIVE_NAMES) <= defined_names(owner)
    assert not (set(SHARED_MODEL_PRIMITIVE_NAMES) & defined_names(registry))


def test_board_only_footprint_models_have_a_theme_owner() -> None:
    names = ("PcbBoardOnlyFootprint", "PcbBoardOnlyFootprintCoverage")
    owner = HWREPO / "pcb_board_only_footprint_models.py"

    assert all(
        getattr(pcb_board_only_footprint_models, name).__module__.endswith(
            "pcb_board_only_footprint_models"
        )
        for name in names
    )
    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert all(not hasattr(shared_models, name) for name in names)
