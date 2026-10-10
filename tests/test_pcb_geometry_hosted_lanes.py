"""Focused checks for hosted PCB geometry lane coordination and toolchain guards."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling import ci_hosted_pcb_geometry_fixtures as fixture_lanes
from kicad_tooling.ci_hosted_pcb_decoupling_fixture import decoupling_placement_fixture_lane
from kicad_tooling.ci_hosted_pcb_fixture_support import HostedPcbFixtureFailure
from kicad_tooling.ci_hosted_pcb_protection_fixture import protection_path_fixture_lane
from kicad_tooling.ci_hosted_pcb_track_width_fixture import track_width_fixture_lane
from kicad_tooling.hwrepo import electrical

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize(
    "lane",
    (
        decoupling_placement_fixture_lane,
        protection_path_fixture_lane,
        track_width_fixture_lane,
    ),
    ids=("decoupling", "protection-path", "track-width"),
)
def test_theme_lane_refuses_an_uncovered_kicad_version_before_receipt_setup(
    lane: Callable[..., None], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = SimpleNamespace(image="sha256:fixture", kicad_version="10.0.6")
    monkeypatch.setattr(electrical, "selected_config", lambda root, project: config)
    log = SimpleNamespace(directory=tmp_path)

    with pytest.raises(ValueError, match="native fixtures do not cover KiCad 10.0.6"):
        lane(tmp_path, project="synthetic-project", image="sha256:fixture", log=log)

    assert tuple(tmp_path.iterdir()) == ()


def test_fixture_coordinator_runs_each_theme_and_reraises_the_first_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []

    def decoupling(root: Path, *, project: str, image: str, log: object) -> None:
        calls.append("decoupling")
        raise HostedPcbFixtureFailure("decoupling fixture failure")

    def protection(root: Path, *, project: str, image: str, log: object) -> None:
        calls.append("protection")

    def track_width(root: Path, *, project: str, image: str, log: object) -> None:
        calls.append("track-width")

    monkeypatch.setattr(fixture_lanes, "decoupling_placement_fixture_lane", decoupling)
    monkeypatch.setattr(fixture_lanes, "protection_path_fixture_lane", protection)
    monkeypatch.setattr(fixture_lanes, "track_width_fixture_lane", track_width)

    with pytest.raises(HostedPcbFixtureFailure, match="decoupling fixture failure"):
        fixture_lanes.pcb_decoupling_fixture_lane(
            tmp_path,
            project="synthetic-project",
            image="sha256:fixture",
            log=object(),
        )

    assert calls == ["decoupling", "protection", "track-width"]
