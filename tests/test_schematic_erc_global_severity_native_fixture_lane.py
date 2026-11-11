"""Digest-pinned native regressions for global schematic ERC suppression."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, schematic_erc_global_severity_fixture_lane
from kicad_tooling.ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from kicad_tooling.hwrepo.evidence import digest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id="schematic.erc_rule_ignored"),
    pytest.mark.design_lint_rule(rule_id="schematic.erc_error_downgraded"),
    pytest.mark.design_lint_rule(rule_id="schematic.erc_unknown_rule_key"),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_SCHEMATIC_ERC_GLOBAL_SEVERITY_FIXTURES") != "1",
        reason="native global ERC severity fixtures run in the digest-pinned acceptance lane",
    ),
]


@pytest.mark.parametrize(("version", "image"), KICAD_10_NATIVE_TOOLCHAINS)
def test_native_erc_honors_persisted_global_severities(version: str, image: str) -> None:
    repository = Path(__file__).resolve().parents[1]
    (repository / "build/ci").mkdir(parents=True, exist_ok=True)
    log = HostedLog(repository, f"native-schematic-erc-global-severity-{version}")

    schematic_erc_global_severity_fixture_lane(
        repository,
        project=f"kicad-{version}",
        image=image,
        log=log,
    )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_results = tuple(
        item
        for item in events
        if item.get("stage") == "schematic-erc-global-severity/native-export"
        and item.get("status") == "PASS"
    )
    assert native_results
    native_result = native_results[-1]
    assert native_result["kicad_version"] == version
    assert native_result["image"] == image
    assert native_result["ignored_pin_not_connected"] == "absent"
    assert native_result["active_pin_not_connected"] == "error"
    assert native_result["downgraded_pin_not_connected"] == "warning"
    assert native_result["unknown_key_pin_not_connected"] == "error"
    assert native_result["repeatable"] == "true"
    for key in (
        "ignored_settings_sha256",
        "active_settings_sha256",
        "downgraded_settings_sha256",
        "unknown_settings_sha256",
        "schematic_sha256",
    ):
        assert len(native_result[key]) == 64
    unknown_settings = (
        Path(__file__).parent
        / "fixtures/design_lint/schematic-erc-global-severity/unknown.kicad_pro"
    )
    assert native_result["unknown_settings_sha256"] == digest(unknown_settings)
