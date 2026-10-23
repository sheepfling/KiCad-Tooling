"""Digest-pinned exact-version native evidence for BJT base/collector lint."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_component_lint import component_lint_fixture_lane
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

RULE_ID = "component.bjt_base_collector_same_net"
FIXTURES = {
    "fault": "bjt-bc-same-net-native/fault.kicad_sch",
    "control": "bjt-terminal-order-native/control.kicad_sch",
}
SOURCE_HASHES = {
    "fault": "32dff25a342646150e18a765bcba4cc13ef360d52d06b51ef448bad4c5f17a21",
    "control": "2b68e0bb4818e82917047e2e9caf07b0b9ebf25cf5fd939a6bb4b7a1f7c45845",
}
EXPECTED_SUBJECTS = {
    "fault": (
        "Q1: BJT base and collector share one schematic net",
        "Q2: BJT base and collector share one schematic net",
    ),
    "control": None,
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES") != "1",
    reason="native BJT terminal fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_bjt_base_collector_same_net_fault_and_control_are_deterministic(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == SOURCE_HASHES[case]
        )

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-bjt-base-collector-same-net-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="bjt-base-collector-same-net-fixture",
        project_id_prefix="synthetic-bjt-base-collector-same-net",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic native fixture enables the BJT base/collector review",
                ),
            )
        ),
    )

    prefix = "bjt-base-collector-same-net-fixture/"
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event for event in events if event.get("stage", "").startswith(prefix)
    }
    assert set(results) == {f"{prefix}native-export", f"{prefix}fault", f"{prefix}control"}

    native = results[f"{prefix}native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(f"{case}:{SOURCE_HASHES[case]}" for case in FIXTURES)
    assert_native_fixture_mounts(root, native["command_receipt"])

    for case, expected in EXPECTED_SUBJECTS.items():
        result = results[f"{prefix}{case}"]
        expected_text = "; ".join(expected) if expected is not None else "none"
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == SOURCE_HASHES[case]
        assert result["rule_findings"] == expected_text
        assert reports[case].status == ("REVIEW" if expected is not None else "PASS")
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
