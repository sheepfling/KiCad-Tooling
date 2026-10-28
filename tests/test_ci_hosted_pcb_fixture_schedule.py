"""Guard exact-version boundaries for hosted PCB fixture lanes."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from kicad_tooling import (
    ci_hosted_pcb_access as access_lane,
)
from kicad_tooling import (
    ci_hosted_pcb_reference_planes as reference_plane_lane,
)
from kicad_tooling import (
    ci_hosted_pcb_return_context as return_lane,
)
from kicad_tooling import (
    ci_hosted_pcb_switching_loop_context as switching_loop_lane,
)
from kicad_tooling.ci_hosted import (
    HostedLog,
    pcb_access_fixture_lane,
    pcb_reference_plane_narrow_void_fixture_lane,
    pcb_reference_plane_via_fixture_lane,
    pcb_return_fixture_lane,
    pcb_switching_loop_fixture_lane,
)
from kicad_tooling.hwrepo import electrical

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.return_path_lint,
]

_FixtureLane = Callable[..., None]


def _assert_unsupported_version_stops_before_capture(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    lane: _FixtureLane,
    log_name: str,
) -> None:
    config = electrical.selected_config(root, "controller")
    unsupported = config.model_copy(update={"kicad_version": "10.0.6"})
    for owner in (access_lane, return_lane, switching_loop_lane, reference_plane_lane):
        monkeypatch.setattr(owner, "selected_config", lambda *_args: unsupported)

    with pytest.raises(ValueError, match="do not cover KiCad 10.0.6"):
        lane(
            root,
            project="controller",
            image=config.image,
            log=HostedLog(root, log_name),
        )


def test_pcb_access_fixture_rejects_an_untested_kicad_minor_before_native_execution(
    hosted_reference_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_unsupported_version_stops_before_capture(
        hosted_reference_root,
        monkeypatch,
        pcb_access_fixture_lane,
        "native-pcb-access-fixture-version",
    )


def test_pcb_return_fixture_rejects_an_untested_kicad_minor_before_native_execution(
    hosted_reference_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_unsupported_version_stops_before_capture(
        hosted_reference_root,
        monkeypatch,
        pcb_return_fixture_lane,
        "native-pcb-fixture-version",
    )


def test_pcb_switching_loop_fixture_rejects_an_untested_kicad_minor(
    hosted_reference_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_unsupported_version_stops_before_capture(
        hosted_reference_root,
        monkeypatch,
        pcb_switching_loop_fixture_lane,
        "native-pcb-switching-loop-fixture-version",
    )


@pytest.mark.parametrize(
    "lane",
    [
        pytest.param(pcb_reference_plane_via_fixture_lane, id="via-antipad"),
        pytest.param(pcb_reference_plane_narrow_void_fixture_lane, id="narrow-void"),
    ],
)
def test_reference_plane_fixture_rejects_an_untested_kicad_minor(
    hosted_reference_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    lane: _FixtureLane,
) -> None:
    _assert_unsupported_version_stops_before_capture(
        hosted_reference_root,
        monkeypatch,
        lane,
        "native-pcb-reference-plane-fixture-version",
    )
