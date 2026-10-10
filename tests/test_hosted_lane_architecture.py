"""Track legacy hosted lane decomposition without allowing new god functions."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.design_lint

REPO_ROOT = Path(__file__).resolve().parents[1]
COORDINATOR = REPO_ROOT / "kicad_tooling" / "ci_hosted.py"
CONNECTOR_RETURN_COORDINATOR = REPO_ROOT / "kicad_tooling" / "ci_hosted_connector_return_lane.py"
CONNECTOR_RETURN_MODULES = REPO_ROOT / "kicad_tooling"
DIGITAL_PEER_COORDINATOR = REPO_ROOT / "kicad_tooling" / "ci_hosted_digital_peer_lane.py"
DIGITAL_PEER_MODULES = REPO_ROOT / "kicad_tooling"
SWITCHING_LOOP_COORDINATOR = REPO_ROOT / "kicad_tooling" / "ci_hosted_pcb_switching_loop_lane.py"
SWITCHING_LOOP_MODULES = REPO_ROOT / "kicad_tooling"
PCB_RETURN_COORDINATOR = REPO_ROOT / "kicad_tooling" / "ci_hosted_pcb_return_lane.py"
PCB_RETURN_MODULES = REPO_ROOT / "kicad_tooling"
LARGER_THEME_LANES = {
    "usb_c_port_fixture_lane": "ci_hosted_usb_c_ports.py",
    "ic_rail_capacitor_fixture_lane": "ci_hosted_ic_rail_capacitors.py",
    "power_sequence_fixture_lane": "ci_hosted_power_sequences.py",
    "open_drain_bias_fixture_lane": "ci_hosted_open_drain_bias.py",
}
LEGACY_CEILINGS = Path(__file__).with_name("hosted_lane_line_ceilings.json")
FUNCTION_LIMIT = 500


def _lane_lengths() -> dict[str, int]:
    tree = ast.parse(COORDINATOR.read_text(encoding="utf-8"))
    return {
        node.name: node.end_lineno - node.lineno + 1
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.endswith("_lane")
    }


def test_oversized_hosted_lanes_are_legacy_and_must_shrink() -> None:
    ceilings = json.loads(LEGACY_CEILINGS.read_text(encoding="utf-8"))
    current = _lane_lengths()
    oversized = {name: length for name, length in current.items() if length >= FUNCTION_LIMIT}

    assert set(oversized) == set(ceilings), (
        "Keep new hosted lanes below 500 lines, and remove a legacy ceiling when its lane is split; "
        f"untracked={sorted(set(oversized) - set(ceilings))}, "
        f"stale={sorted(set(ceilings) - set(oversized))}"
    )
    growth = {
        name: {"current": oversized[name], "ceiling": ceilings[name]}
        for name in ceilings
        if oversized[name] > ceilings[name]
    }
    assert not growth, f"Shrink oversized hosted lanes; do not grow them: {growth}"


def test_hosted_theme_modules_and_functions_stay_below_review_limit() -> None:
    modules = sorted((REPO_ROOT / "kicad_tooling").glob("ci_hosted_*.py"))
    oversized_modules = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in modules
        if len(path.read_text(encoding="utf-8").splitlines()) >= FUNCTION_LIMIT
    }
    oversized_functions = {}
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        oversized_functions.update(
            {
                f"{path.name}:{node.name}": node.end_lineno - node.lineno + 1
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.end_lineno - node.lineno + 1 >= FUNCTION_LIMIT
            }
        )

    assert not oversized_modules, f"Split hosted theme modules: {oversized_modules}"
    assert not oversized_functions, f"Split hosted theme functions: {oversized_functions}"


def test_connector_return_fixture_lane_is_split_by_theme() -> None:
    coordinator = ast.parse(CONNECTOR_RETURN_COORDINATOR.read_text(encoding="utf-8"))
    lane = next(
        node
        for node in coordinator.body
        if isinstance(node, ast.FunctionDef) and node.name == "connector_return_lint_fixture_lane"
    )
    lane_lines = lane.end_lineno - lane.lineno + 1
    modules = sorted(CONNECTOR_RETURN_MODULES.glob("ci_hosted_connector_return_*.py"))
    oversized_modules = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in modules
        if len(path.read_text(encoding="utf-8").splitlines()) >= FUNCTION_LIMIT
    }

    assert lane_lines < 100, f"Keep the fixture lane as a coordinator: {lane_lines} lines"
    assert len(modules) == 14, "Keep connector return fixture work in named theme modules"
    assert not oversized_modules, (
        f"Split connector return modules by responsibility: {oversized_modules}"
    )
    assert "connector_return_lint_fixture_lane" not in _lane_lengths()


def test_digital_peer_fixture_lane_is_split_by_interface_theme() -> None:
    coordinator = ast.parse(DIGITAL_PEER_COORDINATOR.read_text(encoding="utf-8"))
    lane = next(
        node
        for node in coordinator.body
        if isinstance(node, ast.FunctionDef) and node.name == "digital_peer_fixture_lane"
    )
    lane_lines = lane.end_lineno - lane.lineno + 1
    modules = sorted(DIGITAL_PEER_MODULES.glob("ci_hosted_digital_peer_*.py"))
    oversized_modules = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in modules
        if len(path.read_text(encoding="utf-8").splitlines()) >= FUNCTION_LIMIT
    }

    assert lane_lines < 100, f"Keep the digital peer lane as a coordinator: {lane_lines} lines"
    assert len(modules) == 9, "Keep digital peer fixtures in named interface theme modules"
    assert not oversized_modules, (
        f"Split digital peer modules by responsibility: {oversized_modules}"
    )
    compatibility_entry = _lane_lengths()["digital_peer_fixture_lane"]
    assert compatibility_entry < 100, "Keep the ci_hosted compatibility entry point small"


def test_switching_loop_fixture_lane_separates_setup_and_geometry() -> None:
    coordinator = ast.parse(SWITCHING_LOOP_COORDINATOR.read_text(encoding="utf-8"))
    lane = next(
        node
        for node in coordinator.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_switching_loop_fixture_lane"
    )
    lane_lines = lane.end_lineno - lane.lineno + 1
    modules = sorted(SWITCHING_LOOP_MODULES.glob("ci_hosted_pcb_switching_loop_*.py"))
    oversized_modules = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in modules
        if len(path.read_text(encoding="utf-8").splitlines()) >= FUNCTION_LIMIT
    }

    assert lane_lines < 50, f"Keep the switching-loop lane as a coordinator: {lane_lines} lines"
    assert len(modules) == 3, "Separate switching-loop setup, checks, and coordination"
    assert not oversized_modules, f"Keep switching-loop modules reviewable: {oversized_modules}"
    compatibility_entry = _lane_lengths()["pcb_switching_loop_fixture_lane"]
    assert compatibility_entry < 100, "Keep the ci_hosted compatibility entry point small"


def test_pcb_return_fixture_lane_separates_native_evidence_themes() -> None:
    coordinator = ast.parse(PCB_RETURN_COORDINATOR.read_text(encoding="utf-8"))
    lane = next(
        node
        for node in coordinator.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_pcb_return_fixture_lane"
    )
    lane_lines = lane.end_lineno - lane.lineno + 1
    modules = sorted(PCB_RETURN_MODULES.glob("ci_hosted_pcb_return_*.py"))
    oversized_modules = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in modules
        if len(path.read_text(encoding="utf-8").splitlines()) >= FUNCTION_LIMIT
    }

    assert lane_lines < 50, f"Keep the PCB return lane as a coordinator: {lane_lines} lines"
    assert len(modules) == 4, "Separate PCB return setup, case evaluation, and evidence themes"
    assert not oversized_modules, f"Keep PCB return modules reviewable: {oversized_modules}"
    compatibility_entry = _lane_lengths()["pcb_return_fixture_lane"]
    assert compatibility_entry < 100, "Keep the ci_hosted compatibility entry point small"


@pytest.mark.parametrize(("lane_name", "module_name"), LARGER_THEME_LANES.items())
def test_large_hosted_fixture_lanes_live_in_bounded_theme_modules(
    lane_name: str, module_name: str
) -> None:
    module_path = REPO_ROOT / "kicad_tooling" / module_name
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    lane = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == lane_name
    )
    module_lines = len(module_path.read_text(encoding="utf-8").splitlines())
    lane_lines = lane.end_lineno - lane.lineno + 1

    assert module_lines < FUNCTION_LIMIT, f"Keep {module_name} bounded: {module_lines} lines"
    assert lane_lines < FUNCTION_LIMIT, f"Keep {lane_name} bounded: {lane_lines} lines"
    assert _lane_lengths()[lane_name] < 100, "Keep the ci_hosted entry point small"
