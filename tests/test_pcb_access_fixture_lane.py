"""Synthetic orchestration checks for the PCB access native fixture lane."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted import pcb_access_fixture_lane
from kicad_tooling.hwrepo import electrical

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_unsupported_kicad_minor_fails_before_native_access(tmp_path: Path, monkeypatch) -> None:
    image = "fixture.invalid/kicad@sha256:" + "a" * 64
    config = SimpleNamespace(image=image, kicad_version="10.0.6")
    monkeypatch.setattr(electrical, "selected_config", lambda root, project: config)
    log = SimpleNamespace(directory=tmp_path)

    with pytest.raises(ValueError, match="do not cover KiCad 10.0.6"):
        pcb_access_fixture_lane(tmp_path, project="synthetic", image=image, log=log)
