"""Exact-native regression coverage for mapped USB and serial connector returns."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from kicad_tooling.ci_hosted_mixed_interface_returns import mixed_interface_return_fixture_lane
from kicad_tooling.ci_hosted_support import HostedLog
from tests.native_fixture_support import assert_native_fixture_mounts

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.return_path_lint,
]


@pytest.mark.design_lint_rule(rule_id="connector.repeated_pin_function")
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_MIXED_INTERFACE_RETURN_FIXTURES") != "1",
    reason="mixed USB/serial native fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(("version", "image"), KICAD_10_NATIVE_TOOLCHAINS)
def test_native_mixed_interface_returns_are_source_bound_and_repeatable(
    version: str, image: str
) -> None:
    root = Path(__file__).resolve().parents[1]
    log = HostedLog(root, f"mixed-interface-returns-kicad-{version}")

    mixed_interface_return_fixture_lane(root, version=version, image=image, log=log)

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    stages = {item["stage"]: item for item in events}
    prefix = "mixed-interface-return-fixture/"
    expected_stages = {
        f"{prefix}native-export",
        f"{prefix}fault",
        f"{prefix}control",
        f"{prefix}separate-scope-control",
    }
    assert expected_stages <= set(stages)
    results = {stage: stages[stage] for stage in expected_stages}
    assert all(item["status"] == "PASS" for item in results.values())

    native_export = results[f"{prefix}native-export"]
    assert native_export["kicad_version"] == version
    source_hashes = dict(entry.split(":", 1) for entry in native_export["source_hashes"].split(","))
    assert set(source_hashes) == {"fault", "control"}
    assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in source_hashes.values())
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    fault = results[f"{prefix}fault"]
    assert fault["kicad_version"] == version
    assert fault["connector_coverage"] == "COMPLETE"
    assert fault["findings"] != "none"
    assert fault["erc_errors"] == "none"
    assert fault["repeatable"] == "true"
    control = results[f"{prefix}control"]
    assert control["kicad_version"] == version
    assert control["connector_coverage"] == "COMPLETE"
    assert control["findings"] == "none"
    assert control["erc_errors"] == "none"
    assert control["repeatable"] == "true"
    separate_scope = results[f"{prefix}separate-scope-control"]
    assert separate_scope["kicad_version"] == version
    assert separate_scope["connector_coverage"] == "COMPLETE"
    assert separate_scope["findings"] == "none"
