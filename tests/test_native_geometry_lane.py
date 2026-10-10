"""Native geometry lane command construction tests."""

from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess

from kicad_tooling.hwrepo import native_geometry_lane


def test_lane_runs_every_split_suite_through_pytest(tmp_path: Path, monkeypatch) -> None:
    checkout = tmp_path / "checkout"
    module_path = checkout / "kicad_tooling/hwrepo/native_geometry_lane.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    tests = checkout / "tests"
    tests.mkdir()
    expected_files = (
        "test_schematic_geometry_hierarchy.py",
        "test_schematic_geometry_native_pin_connectivity.py",
        "test_schematic_geometry_native_symbol_body.py",
        "test_schematic_geometry_native_text.py",
        "test_schematic_geometry_native_wire_body.py",
        "test_schematic_geometry_native_wire_topology.py",
        "test_schematic_geometry_pin_proximity.py",
        "test_schematic_geometry_symbol_body.py",
        "test_schematic_geometry_text.py",
        "test_schematic_geometry_wire_topology.py",
    )
    for name in expected_files:
        (tests / name).touch()
    monkeypatch.setattr(native_geometry_lane, "__file__", str(module_path))

    stages: list[tuple[str, tuple[str, ...], dict[str, str] | None]] = []

    def record_stage(name, command, output, *, cwd, environment=None):
        stages.append((name, tuple(command), environment))
        return CompletedProcess(command, 0, stdout="", stderr="")

    output = tmp_path / "output"
    output.mkdir()
    native_geometry_lane.run(checkout, output, record_stage)

    test_stages = [
        entry for entry in stages if entry[0].startswith("native-schematic-geometry-tests-")
    ]
    assert len(test_stages) == 2
    expected_paths = tuple(str(checkout / "tests" / name) for name in expected_files)
    for _name, command, _environment in test_stages:
        assert command[3:6] == ("-m", "pytest", "-q")
        assert command[6:] == expected_paths

    receipt_path = checkout / "build/ci/native-schematic-geometry/lanes.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert [lane["test_files"] for lane in receipt["lanes"]] == [
        [f"tests/{name}" for name in expected_files],
        [f"tests/{name}" for name in expected_files],
    ]
