"""Test exact image gates for the isolated PCB fiducial native fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, pcb_fiducial_fixture_lane

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint]


def test_fiducial_fixture_rejects_an_unpinned_image_before_native_execution(
    tmp_path: Path,
) -> None:
    image = "ghcr.io/kicad/kicad:10.0.5@sha256:" + "0" * 64

    with pytest.raises(ValueError, match="Fiducial fixtures do not cover image"):
        pcb_fiducial_fixture_lane(
            tmp_path,
            project="synthetic-unpinned",
            image=image,
            log=HostedLog(tmp_path, "native-pcb-fiducial-unpinned-image"),
        )
