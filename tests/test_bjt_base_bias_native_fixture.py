"""Exact-version native schematic evidence for BJT base-bias review."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.ci_hosted_component_lint import component_lint_fixture_lane
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.component_bjt_base_bias import RULE_ID
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

FIXTURES = MappingProxyType(
    {
        "fault": "bjt-base-bias-native/fault.kicad_sch",
        "control": "bjt-base-bias-native/control.kicad_sch",
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "fault": "55cc042c83a59be9df77953cb9167533fe459bf5a7e5b7b6d2bcf3e6cc8d4d17",
        "control": "e457df2782144a90b2c74141892defe416b82e5c0c10d5546d9ab6c854155461",
    }
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "fault": (
            "Q1.2: BJT base has no visible base-emitter bias resistor",
            "Q2.1: BJT base has no visible base-emitter bias resistor",
        ),
        "control": None,
    }
)


def test_native_bjt_base_bias_fixture_sources_are_pinned() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    assert set(FIXTURES) == set(EXPECTED_SOURCE_HASHES)
    for case, relative in FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_BASE_DRIVE_FIXTURES") != "1",
    reason="native BJT base-bias fixtures run in the digest-pinned component acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_bjt_base_bias_fault_and_control_are_repeatable(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-bjt-base-bias-{version}")
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic native fixture enables the opt-in review rule",
            ),
        )
    )
    component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="bjt-base-bias-fixture",
        project_id_prefix="synthetic-bjt-base-bias",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=policy,
    )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if "bjt-base-bias-fixture/" in event.get("stage", "")
    }
    assert set(results) == {
        "bjt-base-bias-fixture/native-export",
        "bjt-base-bias-fixture/fault",
        "bjt-base-bias-fixture/control",
    }
    native = results["bjt-base-bias-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in FIXTURES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    for case, expected in EXPECTED_SUBJECTS.items():
        result = results[f"bjt-base-bias-fixture/{case}"]
        expected_text = "; ".join(expected) if expected is not None else "none"
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == EXPECTED_SOURCE_HASHES[case]
        assert result["rule_findings"] == expected_text
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
