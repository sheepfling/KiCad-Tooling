"""Hosted lane adapters retain their exact KiCad version boundary."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from kicad_tooling import ci_hosted
from kicad_tooling.hwrepo import electrical

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
]


@pytest.mark.parametrize(
    "lane_name",
    (
        "pcb_reference_plane_via_fixture_lane",
        "pcb_reference_plane_narrow_void_fixture_lane",
    ),
)
def test_reference_plane_fixture_lanes_reject_untested_kicad_minors(
    lane_name: str,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SimpleNamespace(image="synthetic-image", kicad_version="10.0.6")
    monkeypatch.setattr(electrical, "selected_config", lambda root, project: config)
    lane = getattr(ci_hosted, lane_name)

    with pytest.raises(ValueError, match="fixtures do not cover KiCad 10.0.6"):
        lane(
            tmp_path,
            project="synthetic-project",
            image="synthetic-image",
            log=SimpleNamespace(directory=tmp_path),
        )
