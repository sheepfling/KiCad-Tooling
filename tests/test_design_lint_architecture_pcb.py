"""Keep PCB lint boundaries separated by geometry, routing, and native rules."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    pcb_return_path_capture,
    pcb_return_path_checks,
    pcb_return_paths,
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

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.architecture]

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
    "pcb_drc_rule_structure.py",
    "pcb_drc_rule_coverage.py",
    "pcb_drc_source_evidence.py",
    "pcb_drc_conditions.py",
    "pcb_drc_source_scan.py",
)
PCB_RETURN_PATH_MODULES = (
    "pcb_return_path_models.py",
    "pcb_return_path_checks.py",
    "pcb_return_path_capture.py",
)
PCB_SHARED_PAD_MODULES = ("pcb_pad_review.py", "pcb_pad_union_find.py")
PCB_ROUTE_SKEW_MODULES = (
    "design_lint_pcb_geometry_fast_paths.py",
    "pcb_native_route_models.py",
    "pcb_native_route_topology.py",
    "pcb_differential_pair_skew_models.py",
    "pcb_differential_pair_route_skew.py",
    "pcb_differential_pair_layer_transitions.py",
    "design_lint_pcb_differential_pair_skew_candidate_evidence.py",
    "design_lint_pcb_route_skew_policy.py",
    "design_lint_pcb_route_skew_report.py",
    "design_lint_pcb_route_skew_scan.py",
)
# Lower this baseline alongside each registry extraction; never raise it.


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
        pcb_return_paths.NativePcbConnectivityCapture
        is pcb_return_path_capture.NativePcbConnectivityCapture
    )
    assert (
        pcb_return_paths.NATIVE_PROBE_SOURCE_PARTS
        == pcb_return_path_capture.NATIVE_PROBE_SOURCE_PARTS
    )
    assert (
        pcb_return_paths.capture_native_pcb_connectivity
        is pcb_return_path_capture.capture_native_pcb_connectivity
    )
    assert (
        pcb_return_paths.capture_native_pcb_connectivity_result
        is pcb_return_path_capture.capture_native_pcb_connectivity_result
    )
    assert (
        pcb_return_paths.native_pcb_command_matches
        is pcb_return_path_capture.native_pcb_command_matches
    )
    assert pcb_return_paths.pcb_return_path_checks is pcb_return_path_checks.pcb_return_path_checks


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


def test_shared_pcb_pad_services_stay_small_and_are_reused() -> None:
    modules = [HWREPO / name for name in PCB_SHARED_PAD_MODULES]

    assert all(path.is_file() for path in modules)
    oversized = {path.name: _line_count(path) for path in modules if _line_count(path) >= 500}
    assert not oversized, f"Keep shared PCB pad services below 500 lines: {oversized}"

    consumers = (
        HWREPO / "pcb_decoupling.py",
        HWREPO / "pcb_protection_path.py",
        HWREPO / "pcb_return_path_checks.py",
    )
    parsed = {
        path.name: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in consumers
    }
    assert all(
        any(
            isinstance(node, ast.ImportFrom)
            and node.module == "pcb_pad_union_find"
            and any(alias.name == "PcbPadUnionFind" for alias in node.names)
            for node in ast.walk(tree)
        )
        for tree in parsed.values()
    )
    assert all(
        any(
            isinstance(node, ast.ImportFrom)
            and node.module == "pcb_pad_review"
            and any(alias.name == "pcb_pad_endpoint_issues" for alias in node.names)
            for node in ast.walk(tree)
        )
        for name, tree in parsed.items()
        if name != "pcb_return_path_checks.py"
    )
    assert not any(
        isinstance(node, ast.ClassDef) and node.name == "_PadUnion"
        for tree in parsed.values()
        for node in ast.walk(tree)
    )


def test_differential_pair_route_skew_owners_stay_reviewable_and_theme_owned() -> None:
    modules = [HWREPO / name for name in PCB_ROUTE_SKEW_MODULES]
    assert all(path.is_file() for path in modules)
    oversized = {path.name: _line_count(path) for path in modules if _line_count(path) >= 500}
    assert not oversized, f"Keep pair route-skew services in small modules: {oversized}"

    route_owner = HWREPO / "pcb_differential_pair_route_skew.py"
    route_tree = ast.parse(route_owner.read_text(encoding="utf-8"), filename=str(route_owner))
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "measure_differential_pair_route_skew"
        for node in route_tree.body
    )
    catalog = (HWREPO / "design-lint-rules.json").read_text(encoding="utf-8")
    assert (
        '"implementation_owner": '
        '"kicad_tooling/hwrepo/pcb_differential_pair_route_skew.py#'
        'measure_differential_pair_route_skew"'
    ) in catalog
    assert '"kicad_tooling/hwrepo/pcb_native_route_topology.py#resolve_native_pad_route"' in catalog
