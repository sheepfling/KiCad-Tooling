"""Exact-version native schematic evidence for BJT component lint rules."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.ci_hosted_component_lint import component_lint_fixture_lane
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.component_bjt_terminal_order import RULE_ID
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
        "fault": "bjt-terminal-order-native/fault.kicad_sch",
        "control": "bjt-terminal-order-native/control.kicad_sch",
    }
)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        "fault": "deca669b12ceec4fbd21004d48f6eebbe86f68dd9820a727bb01adbd9a663c9d",
        "control": "2b68e0bb4818e82917047e2e9caf07b0b9ebf25cf5fd939a6bb4b7a1f7c45845",
    }
)
EXPECTED_SUBJECTS = MappingProxyType(
    {
        "fault": (
            "Q1: NPN transistor collector/emitter order merits review",
            "Q2: PNP transistor collector/emitter order merits review",
        ),
        "control": None,
    }
)
SAME_NET_FIXTURES = MappingProxyType(
    {
        "fault": "bjt-ce-same-net-native/fault.kicad_sch",
        "control": "bjt-terminal-order-native/control.kicad_sch",
    }
)
EXPECTED_SAME_NET_SOURCE_HASHES = MappingProxyType(
    {
        "fault": "5fda7f1f6b248be52260d4e472444f9a517ba5b92bec06bc2f5ef3609cdf93c3",
        "control": "2b68e0bb4818e82917047e2e9caf07b0b9ebf25cf5fd939a6bb4b7a1f7c45845",
    }
)
SAME_NET_EXPECTED_SUBJECTS = MappingProxyType(
    {
        "fault": (
            "Q1: BJT collector and emitter share one schematic net",
            "Q2: BJT collector and emitter share one schematic net",
        ),
        "control": None,
    }
)
BASE_EMITTER_SAME_NET_FIXTURES = MappingProxyType(
    {
        "fault": "bjt-be-same-net-native/fault.kicad_sch",
        "control": "bjt-terminal-order-native/control.kicad_sch",
    }
)
BASE_EMITTER_SAME_NET_SOURCE_HASHES = MappingProxyType(
    {
        "fault": "3ff07964aaea5f8a879d82eaf918902c8b5a1ff83dee877a8609613a6c91b77b",
        "control": "2b68e0bb4818e82917047e2e9caf07b0b9ebf25cf5fd939a6bb4b7a1f7c45845",
    }
)
BASE_EMITTER_SAME_NET_EXPECTED_SUBJECTS = MappingProxyType(
    {
        "fault": (
            "Q1: BJT base and emitter share one schematic net",
            "Q2: BJT base and emitter share one schematic net",
        ),
        "control": None,
    }
)


def test_native_bjt_terminal_order_fixture_sources_are_pinned() -> None:
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
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES") != "1",
    reason="native BJT fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_bjt_terminal_order_fault_and_control_are_deterministic(
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
    log = HostedLog(root, f"native-bjt-terminal-order-{version}")
    component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="bjt-terminal-order-fixture",
        project_id_prefix="synthetic-bjt-terminal-order",
        rule_id=RULE_ID,
        fixtures=FIXTURES,
        expected_subjects=EXPECTED_SUBJECTS,
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if "bjt-terminal-order-fixture/" in event.get("stage", "")
    }
    assert set(results) == {
        "bjt-terminal-order-fixture/native-export",
        "bjt-terminal-order-fixture/fault",
        "bjt-terminal-order-fixture/control",
    }
    native = results["bjt-terminal-order-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SOURCE_HASHES[case]}" for case in FIXTURES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    for case, expected in EXPECTED_SUBJECTS.items():
        result = results[f"bjt-terminal-order-fixture/{case}"]
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


@pytest.mark.design_lint_rule(rule_id="component.bjt_collector_emitter_same_net")
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES") != "1",
    reason="native BJT terminal fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_bjt_collector_emitter_same_net_fault_and_control_are_deterministic(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in SAME_NET_FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == EXPECTED_SAME_NET_SOURCE_HASHES[case]
        )

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-bjt-same-net-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="bjt-same-net-fixture",
        project_id_prefix="synthetic-bjt-same-net",
        rule_id="component.bjt_collector_emitter_same_net",
        fixtures=SAME_NET_FIXTURES,
        expected_subjects=SAME_NET_EXPECTED_SUBJECTS,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="component.bjt_collector_emitter_same_net",
                    mode="review",
                    reason="Synthetic native fixture enables the BJT same-net review",
                ),
            )
        ),
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        event["stage"]: event
        for event in events
        if "bjt-same-net-fixture/" in event.get("stage", "")
    }
    assert set(results) == {
        "bjt-same-net-fixture/native-export",
        "bjt-same-net-fixture/fault",
        "bjt-same-net-fixture/control",
    }
    native = results["bjt-same-net-fixture/native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{EXPECTED_SAME_NET_SOURCE_HASHES[case]}" for case in SAME_NET_FIXTURES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    for case, expected in SAME_NET_EXPECTED_SUBJECTS.items():
        result = results[f"bjt-same-net-fixture/{case}"]
        expected_text = "; ".join(expected) if expected is not None else "none"
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == EXPECTED_SAME_NET_SOURCE_HASHES[case]
        assert result["rule_findings"] == expected_text
        assert reports[case].status == ("REVIEW" if expected is not None else "PASS")
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]


@pytest.mark.design_lint_rule(rule_id="component.bjt_base_emitter_same_net")
@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES") != "1",
    reason="native BJT terminal fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("version", ("10.0.0", "10.0.5"))
def test_native_bjt_base_emitter_same_net_fault_and_control_are_deterministic(
    tmp_path: Path,
    version: str,
) -> None:
    fixture_root = Path(__file__).parent / "fixtures/design_lint"
    for case, relative in BASE_EMITTER_SAME_NET_FIXTURES.items():
        assert (
            hashlib.sha256((fixture_root / relative).read_bytes()).hexdigest()
            == BASE_EMITTER_SAME_NET_SOURCE_HASHES[case]
        )

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id="controller",
        kicad_version=version,
        image=image,
    )
    log = HostedLog(root, f"native-bjt-base-emitter-same-net-{version}")
    reports = component_lint_fixture_lane(
        root,
        project="controller",
        image=image,
        log=log,
        fixture_prefix="bjt-base-emitter-same-net-fixture",
        project_id_prefix="synthetic-bjt-base-emitter-same-net",
        rule_id="component.bjt_base_emitter_same_net",
        fixtures=BASE_EMITTER_SAME_NET_FIXTURES,
        expected_subjects=BASE_EMITTER_SAME_NET_EXPECTED_SUBJECTS,
        policy=DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="component.bjt_base_emitter_same_net",
                    mode="review",
                    reason="Synthetic native fixture enables the BJT base/emitter review",
                ),
            )
        ),
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    prefix = "bjt-base-emitter-same-net-fixture/"
    results = {
        event["stage"]: event for event in events if event.get("stage", "").startswith(prefix)
    }
    assert set(results) == {f"{prefix}native-export", f"{prefix}fault", f"{prefix}control"}
    native = results[f"{prefix}native-export"]
    assert native["status"] == "PASS"
    assert native["kicad_version"] == version
    assert native["image"] == image
    assert native["source_hashes"] == ",".join(
        f"{case}:{BASE_EMITTER_SAME_NET_SOURCE_HASHES[case]}"
        for case in BASE_EMITTER_SAME_NET_FIXTURES
    )
    assert_native_fixture_mounts(root, native["command_receipt"])

    for case, expected in BASE_EMITTER_SAME_NET_EXPECTED_SUBJECTS.items():
        result = results[f"{prefix}{case}"]
        expected_text = "; ".join(expected) if expected is not None else "none"
        assert result["status"] == "PASS"
        assert result["kicad_version"] == version
        assert result["image"] == image
        assert result["source_sha256"] == BASE_EMITTER_SAME_NET_SOURCE_HASHES[case]
        assert result["rule_findings"] == expected_text
        assert reports[case].status == ("REVIEW" if expected is not None else "PASS")
        assert result["erc_errors"] == "none"
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
