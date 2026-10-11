"""Project-independent guards for hosted native PCB fixture adapters."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted import (
    pcb_component_inventory_fixture_lane,
    pcb_return_fixture_lane,
    pcb_switching_loop_fixture_lane,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


@pytest.mark.parametrize(
    ("lane", "message"),
    [
        pytest.param(
            pcb_component_inventory_fixture_lane,
            "PCB component inventory native fixtures do not cover KiCad 10.0.6",
            id="component-inventory",
        ),
        pytest.param(
            pcb_return_fixture_lane,
            "PCB return-path native fixtures do not cover KiCad 10.0.6",
            marks=pytest.mark.return_path_lint,
            id="return-path",
        ),
        pytest.param(
            pcb_switching_loop_fixture_lane,
            "Switching-loop native fixtures do not cover KiCad 10.0.6",
            marks=pytest.mark.return_path_lint,
            id="switching-loop",
        ),
    ],
)
def test_hosted_pcb_fixture_adapters_reject_uncovered_versions_before_native_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lane,
    message: str,
) -> None:
    image = "fixture.invalid/kicad@sha256:" + "a" * 64
    config = SimpleNamespace(image=image, kicad_version="10.0.6")
    monkeypatch.setattr(
        "kicad_tooling.hwrepo.electrical.selected_config",
        lambda *_args: config,
    )
    log = SimpleNamespace(directory=tmp_path)

    with pytest.raises(ValueError, match=message):
        lane(tmp_path, project="synthetic-project", image=image, log=log)
