"""Digest-pinned native regressions for persisted schematic ERC exclusions."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, schematic_erc_exclusion_fixture_lane
from kicad_tooling.ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_SCHEMATIC_ERC_EXCLUSION_FIXTURES") != "1",
        reason="native ERC exclusion fixtures run in the digest-pinned acceptance lane",
    ),
]


@pytest.mark.design_lint_rule("schematic.erc_exclusion_present")
@pytest.mark.parametrize(("version", "image"), KICAD_10_NATIVE_TOOLCHAINS)
def test_kicad_10_reloads_and_reports_saved_exclusions(version: str, image: str) -> None:
    repository = Path(__file__).resolve().parents[1]
    (repository / "build/ci").mkdir(parents=True, exist_ok=True)
    log = HostedLog(repository, f"native-schematic-erc-exclusions-{version}")

    schematic_erc_exclusion_fixture_lane(
        repository,
        project=f"kicad-{version}",
        image=image,
        log=log,
    )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_result = next(
        item
        for item in events
        if item.get("stage") == "schematic-erc-exclusion-fixture/native-export"
        and item.get("status") == "PASS"
    )
    assert native_result["kicad_version"] == version
    assert native_result["image"] == image
    assert native_result["excluded_types"] == "label_dangling,pin_not_connected"
    assert native_result["repeatable"] == "true"
    assert len(native_result["project_settings_sha256"]) == 64
    assert len(native_result["schematic_sha256"]) == 64
