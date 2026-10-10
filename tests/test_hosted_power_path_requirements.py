"""Focused checks for the authored maps used by native power-path fixtures."""

from __future__ import annotations

import pytest

from kicad_tooling.ci_hosted_power_path_requirements import power_path_requirement_map

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]


def test_native_power_path_fixture_map_requires_the_series_component() -> None:
    path_map = power_path_requirement_map()

    assert path_map.basis == "Synthetic reviewed source-to-load requirement"
    assert len(path_map.paths) == 1
    path = path_map.paths[0]
    assert (path.start.net, path.end.net) == ("VIN", "VLOAD")
    assert tuple(element.reference for element in path.elements) == ("FB1",)
