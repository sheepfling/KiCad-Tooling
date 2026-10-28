"""Exact-version native exports for transformer winding same-net lint."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.ci_hosted_transformer_windings import (
    EXPECTED_FINDINGS,
    EXPECTED_GROUP_BRIDGE_FINDINGS,
    FIXTURE_CASES,
    RULE_ID,
    transformer_winding_fixture_lane,
)
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "fault": "d2029e5dde45f91dbc2b66a319c0994fa720489f5a1624da70ae39ad161c50c1",
        "cross_winding_fault": "812e43c602373b37d468b9d8d0b081d0a28c75974f79877b8719fafcb62a720c",
        "control": "444f6bb48b2e9796293e373812e6dc605932d666dc4c737cb8c9561dfb09daf3",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.design_lint_rule(rule_id="component.transformer_winding_groups_share_net")
def test_transformer_winding_native_fixture_scope_is_source_hashed_and_complete() -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"

    assert set(FIXTURE_CASES) == set(EXPECTED_SOURCE_HASHES)
    assert set(EXPECTED_FINDINGS) == set(FIXTURE_CASES)
    assert set(EXPECTED_GROUP_BRIDGE_FINDINGS) == set(FIXTURE_CASES)
    assert EXPECTED_FINDINGS["fault"] == ("T1: winding 1 pins 1/2 share WINDING_1_TIED",)
    assert EXPECTED_FINDINGS["cross_winding_fault"] == ()
    assert EXPECTED_FINDINGS["control"] == ()
    assert EXPECTED_GROUP_BRIDGE_FINDINGS["fault"] == ()
    assert EXPECTED_GROUP_BRIDGE_FINDINGS["cross_winding_fault"] == (
        "T1: winding groups share WINDING_GROUPS_SHARED",
    )
    assert EXPECTED_GROUP_BRIDGE_FINDINGS["control"] == ()
    for case, relative in FIXTURE_CASES.items():
        source = fixture_root / relative
        assert source.is_file()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == EXPECTED_SOURCE_HASHES[case]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.design_lint_rule(rule_id="component.transformer_winding_groups_share_net")
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TRANSFORMER_WINDING_FIXTURES") != "1",
    reason="native transformer winding fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_transformer_winding_cases_are_repeatable(
    tmp_path: Path,
    version: str,
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-transformer-winding-{version}")
    transformer_winding_fixture_lane(root, project="controller", image=image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if event.get("stage", "").startswith("transformer-winding-fixture/")
    }

    assert set(results) == {
        "transformer-winding-fixture/native-export",
        "transformer-winding-fixture/fault",
        "transformer-winding-fixture/cross_winding_fault",
        "transformer-winding-fixture/control",
    }
    native = results["transformer-winding-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in FIXTURE_CASES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    for case in FIXTURE_CASES:
        result = results[f"transformer-winding-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == EXPECTED_SOURCE_HASHES[case]
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
    fault = results["transformer-winding-fixture/fault"]
    cross_fault = results["transformer-winding-fixture/cross_winding_fault"]
    control = results["transformer-winding-fixture/control"]
    assert fault["rule_findings"] == EXPECTED_FINDINGS["fault"][0]
    assert fault["group_bridge_rule_findings"] == "none"
    assert fault["lint_status"] == "REVIEW"
    assert cross_fault["rule_findings"] == "none"
    assert (
        cross_fault["group_bridge_rule_findings"]
        == EXPECTED_GROUP_BRIDGE_FINDINGS["cross_winding_fault"][0]
    )
    assert cross_fault["lint_status"] == "REVIEW"
    assert control["rule_findings"] == "none"
    assert control["group_bridge_rule_findings"] == "none"
    assert control["lint_status"] == "PASS"
