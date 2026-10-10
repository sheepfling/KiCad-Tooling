"""Keep hosted design-lint fixture orchestration theme-scoped."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import (
    HOSTED_CI_COORDINATOR_MAX_LINES,
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    TESTS,
    THEME_SUITE_MAX_LINES,
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = pytest.mark.design_lint


def test_hosted_lint_suites_stay_theme_sized() -> None:
    modules = sorted(TESTS.glob("test_ci_hosted*.py"))
    oversized = {
        path.name: _line_count(path)
        for path in modules
        if _line_count(path) >= THEME_SUITE_MAX_LINES
    }

    assert not oversized, (
        f"Keep hosted fixture test suites separated by theme below 500 lines; oversized={oversized}"
    )


HOSTED_PCB_REFERENCE_PLANE_MODULE = "ci_hosted_pcb_reference_planes.py"
HOSTED_PCB_ACCESS_MODULE = "ci_hosted_pcb_access.py"
HOSTED_PCB_GEOMETRY_MODULES = (
    "ci_hosted_pcb_fixture_support.py",
    "ci_hosted_pcb_geometry_fixtures.py",
    "ci_hosted_pcb_decoupling_fixture.py",
    "ci_hosted_pcb_protection_fixture.py",
    "ci_hosted_pcb_track_width_fixture.py",
)
HOSTED_USB_DATA_PATH_MODULE = "ci_hosted_usb_data_paths.py"
HOSTED_USB_REQUIREMENTS_MODULE = "ci_hosted_usb_requirements.py"
HOSTED_POWER_PATH_MODULES = (
    "ci_hosted_power_paths.py",
    "ci_hosted_power_path_native_evidence.py",
    "ci_hosted_power_path_requirements.py",
)
HOSTED_COMPONENT_RATING_MODULES = (
    "ci_hosted_component_rating_context.py",
    "ci_hosted_component_rating_lane.py",
    "ci_hosted_component_voltage_rating_fixture.py",
    "ci_hosted_component_power_rating_fixture.py",
    "ci_hosted_connector_contact_rating_fixture.py",
    "ci_hosted_mosfet_stress_fixture.py",
)


def test_pcb_reference_plane_hosted_lanes_stay_theme_scoped() -> None:
    module = REPO_ROOT / "kicad_tooling" / HOSTED_PCB_REFERENCE_PLANE_MODULE
    catalog_text = (HWREPO / "design-lint-rules.json").read_text(encoding="utf-8")

    assert _line_count(module) < IMPLEMENTATION_MAX_LINES
    assert "kicad_tooling/ci_hosted.py#pcb_reference_plane_" not in catalog_text
    assert (
        "kicad_tooling/ci_hosted_pcb_reference_planes.py#pcb_reference_plane_via_fixture_lane"
        in catalog_text
    )
    assert (
        "kicad_tooling/ci_hosted_pcb_reference_planes.py#"
        "pcb_reference_plane_narrow_void_fixture_lane"
    ) in catalog_text


def test_pcb_access_hosted_lane_stays_theme_scoped() -> None:
    module = REPO_ROOT / "kicad_tooling" / HOSTED_PCB_ACCESS_MODULE
    coordinator_text = (REPO_ROOT / "kicad_tooling" / "ci_hosted.py").read_text(encoding="utf-8")

    assert _line_count(module) < IMPLEMENTATION_MAX_LINES
    assert "def pcb_access_fixture_lane(" not in coordinator_text
    assert "from .ci_hosted_pcb_access import pcb_access_fixture_lane" in coordinator_text


def test_pcb_geometry_hosted_fixtures_stay_split_by_lint_theme() -> None:
    modules = tuple(REPO_ROOT / "kicad_tooling" / name for name in HOSTED_PCB_GEOMETRY_MODULES)
    coordinator = REPO_ROOT / "kicad_tooling" / "ci_hosted.py"
    theme_coordinator = REPO_ROOT / "kicad_tooling" / "ci_hosted_pcb_geometry_fixtures.py"
    coordinator_text = coordinator.read_text(encoding="utf-8")
    theme_text = theme_coordinator.read_text(encoding="utf-8")
    catalog_text = (HWREPO / "design-lint-rules.json").read_text(encoding="utf-8")

    assert all(_line_count(module) < IMPLEMENTATION_MAX_LINES for module in modules)
    assert "def pcb_decoupling_fixture_lane(" not in coordinator_text
    assert (
        "from .ci_hosted_pcb_geometry_fixtures import pcb_decoupling_fixture_lane"
        in coordinator_text
    )
    for module, lane in (
        ("ci_hosted_pcb_decoupling_fixture", "decoupling_placement_fixture_lane"),
        ("ci_hosted_pcb_protection_fixture", "protection_path_fixture_lane"),
        ("ci_hosted_pcb_track_width_fixture", "track_width_fixture_lane"),
    ):
        assert f"from .{module} import {lane}" in theme_text
    assert "lane(root, project=project, image=image, log=log)" in theme_text
    for implementation in (
        "ci_hosted_pcb_decoupling_fixture.py#decoupling_placement_fixture_lane",
        "ci_hosted_pcb_protection_fixture.py#protection_path_fixture_lane",
        "ci_hosted_pcb_track_width_fixture.py#track_width_fixture_lane",
    ):
        assert f"kicad_tooling/{implementation}" in catalog_text


def test_hosted_fixture_lanes_stay_theme_scoped() -> None:
    modules = (
        REPO_ROOT / "kicad_tooling" / HOSTED_USB_DATA_PATH_MODULE,
        REPO_ROOT / "kicad_tooling" / HOSTED_USB_REQUIREMENTS_MODULE,
        *(REPO_ROOT / "kicad_tooling" / name for name in HOSTED_POWER_PATH_MODULES),
    )
    coordinator_text = (REPO_ROOT / "kicad_tooling" / "ci_hosted.py").read_text(encoding="utf-8")

    assert all(_line_count(module) < IMPLEMENTATION_MAX_LINES for module in modules)
    assert "from .ci_hosted_usb_data_paths import usb_data_path_fixture_lane" in coordinator_text
    assert "from .ci_hosted_power_paths import power_path_fixture_lane" in coordinator_text
    assert "def usb_data_path_fixture_lane(" not in coordinator_text
    assert "def power_path_fixture_lane(" not in coordinator_text


def test_component_rating_hosted_fixture_is_split_by_theme() -> None:
    modules = tuple(REPO_ROOT / "kicad_tooling" / name for name in HOSTED_COMPONENT_RATING_MODULES)
    coordinator = REPO_ROOT / "kicad_tooling" / "ci_hosted.py"
    lane = REPO_ROOT / "kicad_tooling" / "ci_hosted_component_rating_lane.py"
    coordinator_text = coordinator.read_text(encoding="utf-8")
    lane_text = lane.read_text(encoding="utf-8")

    assert all(_line_count(module) < IMPLEMENTATION_MAX_LINES for module in modules)
    assert "def component_rating_fixtures_lane(" not in coordinator_text
    assert (
        "from .ci_hosted_component_rating_lane import component_rating_fixtures_lane"
        in coordinator_text
    )
    for function in (
        "verify_component_voltage_rating_fixture",
        "verify_component_power_rating_fixture",
        "verify_connector_contact_rating_fixture",
        "verify_mosfet_stress_fixture",
    ):
        assert f"{function}(context, log)" in lane_text


def test_hosted_ci_coordinator_contains_only_small_fixture_adapters() -> None:
    coordinator = REPO_ROOT / "kicad_tooling" / "ci_hosted.py"
    source = coordinator.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=coordinator.name)
    oversized_adapters = {
        node.name: node.end_lineno - node.lineno + 1
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.endswith("_fixture_lane")
        and node.end_lineno - node.lineno + 1 >= 100
    }

    assert _line_count(coordinator) < HOSTED_CI_COORDINATOR_MAX_LINES, (
        "Keep ci_hosted.py a bounded CI coordinator; move fixture behavior into theme modules"
    )
    assert not oversized_adapters, (
        f"Keep ci_hosted.py fixture entry points as small adapters: {oversized_adapters}"
    )
