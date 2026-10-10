"""Keep PCB lint boundaries separated by geometry, routing, and native rules."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo import (
    pcb_decoupling_models,
    pcb_drc_models,
    pcb_reference_plane_models,
    pcb_return_path_capture,
    pcb_return_path_checks,
    pcb_return_paths,
    pcb_rf_antenna_models,
    pcb_switching_loop_models,
    pcb_track_width_models,
)
from tests.lint_architecture_support import (
    FACADE_MAX_LINES,
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = pytest.mark.design_lint

PCB_SWITCHING_LOOP_MODULES = (
    "pcb_switching_loop_geometry.py",
    "pcb_switching_loop_return_plane.py",
    "pcb_switching_loop_route_topology.py",
    "pcb_switching_loop_route_coverage.py",
    "pcb_switching_loop_review.py",
)


PCB_DRC_COVERAGE_MODULES = (
    "pcb_drc_models.py",
    "pcb_drc_rule_parser.py",
    "pcb_drc_rule_coverage.py",
    "pcb_drc_source_evidence.py",
    "pcb_drc_source_scan.py",
)
PCB_RETURN_PATH_MODULES = (
    "pcb_return_path_checks.py",
    "pcb_return_path_capture.py",
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
# Lower this baseline alongside each registry extraction; never raise it.
SHARED_MODEL_REGISTRY_MAX_LINES = 8_732


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


def test_pcb_switching_loop_review_stays_split_by_responsibility() -> None:
    facade = HWREPO / "pcb_switching_loops.py"
    modules = [HWREPO / name for name in PCB_SWITCHING_LOOP_MODULES]

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all(path.is_file() for path in modules)
    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        "Keep loop geometry, return-plane evidence, route topology, and review assembly in "
        f"reviewable modules below 500 lines; oversized modules: {oversized}"
    )


def test_pcb_switching_loop_rule_refs_point_to_the_owning_modules() -> None:
    catalog = HWREPO / "design-lint-rules.json"
    text = catalog.read_text(encoding="utf-8")

    assert "kicad_tooling/hwrepo/pcb_switching_loops.py#" not in text
    assert "kicad_tooling/hwrepo/pcb_switching_loop_review.py#pcb_switching_loop_entries" in text
    assert (
        "kicad_tooling/hwrepo/pcb_switching_loop_route_topology.py#resolve_switching_loop_trace_edge"
        in text
    )


def test_pcb_drc_coverage_stays_split_by_responsibility() -> None:
    facade = HWREPO / "pcb_drc_coverage.py"
    modules = [HWREPO / name for name in PCB_DRC_COVERAGE_MODULES]

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all(path.is_file() for path in modules)
    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        "Keep DRC parsing, rule comparison, source evidence, and scan coordination in "
        f"reviewable modules below 500 lines; oversized modules: {oversized}"
    )


def test_pcb_drc_rule_refs_point_to_the_owning_modules() -> None:
    catalog = HWREPO / "design-lint-rules.json"
    text = catalog.read_text(encoding="utf-8")

    assert "kicad_tooling/hwrepo/pcb_drc_coverage.py#" not in text
    assert "kicad_tooling/hwrepo/pcb_drc_rule_coverage.py#compare_native_rules" in text
    assert "kicad_tooling/hwrepo/pcb_drc_rule_coverage.py#compare_native_signal_path_rules" in text


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


def test_pcb_return_paths_stay_split_between_checks_and_native_capture() -> None:
    facade = HWREPO / "pcb_return_paths.py"
    modules = [HWREPO / name for name in PCB_RETURN_PATH_MODULES]

    assert _line_count(facade) < FACADE_MAX_LINES
    assert all(path.is_file() for path in modules)
    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        "Keep PCB return requirement evaluation separate from native evidence capture, "
        f"with both owners below 500 lines; oversized modules: {oversized}"
    )


def test_pcb_return_path_facade_reexports_the_thematic_owners() -> None:
    assert (
        pcb_return_paths.NATIVE_PROBE_SOURCE_PARTS
        == pcb_return_path_capture.NATIVE_PROBE_SOURCE_PARTS
    )
    assert (
        pcb_return_paths.capture_native_pcb_connectivity
        is pcb_return_path_capture.capture_native_pcb_connectivity
    )
    assert (
        pcb_return_paths.native_pcb_command_matches
        is pcb_return_path_capture.native_pcb_command_matches
    )
    assert pcb_return_paths.pcb_return_path_checks is pcb_return_path_checks.pcb_return_path_checks


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


def test_internal_pcb_return_path_services_import_from_their_owners() -> None:
    facade = HWREPO / "pcb_return_paths.py"
    legacy_imports: list[str] = []
    for module in sorted((REPO_ROOT / "kicad_tooling").rglob("*.py")):
        if module == facade:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        if any(
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.endswith("pcb_return_paths")
            for node in ast.walk(tree)
        ):
            legacy_imports.append(module.relative_to(REPO_ROOT).as_posix())

    assert not legacy_imports, (
        "Internal PCB services should import from pcb_return_path_checks or "
        f"pcb_return_path_capture, not the compatibility facade: {legacy_imports}"
    )
