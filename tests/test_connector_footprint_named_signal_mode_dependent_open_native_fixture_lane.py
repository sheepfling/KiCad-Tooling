"""Source-pinned exact-version fixtures for mode-dependent named signals."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
    CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
    connector_return_fixture_sources,
)
from kicad_tooling.ci_hosted_connector_return_named_signal_mode_dependent_open import (
    CONTROL_CASE,
    FAULT_CASE,
    RULE_ID,
    verify_footprint_alias_named_signal_mode_dependent_open,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

FIXTURE_CASES = (FAULT_CASE, CONTROL_CASE)
EXPECTED_SOURCE_HASHES = {
    FAULT_CASE: "96314806f6a6b21e43c9de2b86754d6a9b6f9f15d8ed19b204c61415d9c40e49",
    CONTROL_CASE: "6375edf7f06cd00f66fcbd8d19675f151c428ebf9114b04891e7b9aff8977e3b",
}
FIXTURE_DIRECTORY = "connector-footprint-named-signal-mode-dependent-open-native"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mode_dependent_signal_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint" / FIXTURE_DIRECTORY
    for case, filename in zip(FIXTURE_CASES, ("fault.kicad_sch", "control.kicad_sch"), strict=True):
        assert (
            hashlib.sha256((fixture_root / filename).read_bytes()).hexdigest()
            == (EXPECTED_SOURCE_HASHES[case])
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mode_dependent_signal_fixtures_are_registered_for_hosted_capture() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)
    for case, filename in zip(FIXTURE_CASES, ("fault.kicad_sch", "control.kicad_sch"), strict=True):
        assert sources[case] == fixture_root / FIXTURE_DIRECTORY / filename
        assert CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] == EXPECTED_SOURCE_HASHES[case]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mode_dependent_signal_validator_checks_fault_and_control() -> None:
    fault_alias = SimpleNamespace(open_peer_pin_group_count=1, open_outlier_finding_count=1)
    fault_coverage = SimpleNamespace(
        netlist_sha256="synthetic-native-netlist-hash",
        footprint_alias_coverage=fault_alias,
        model_dump=lambda *, mode: {"netlist_sha256": "synthetic-native-netlist-hash"},
    )
    finding = SimpleNamespace(
        rule_id=RULE_ID,
        evidence={
            "assignments": ("J1.1=DATA_IO", "J2.1=<unassigned>"),
            "open_pins": ("J2.1",),
            "pin_electrical_type": ("bidirectional",),
            "common_anchor_pin_numbers": ("2",),
        },
    )
    fault = SimpleNamespace(
        status="REVIEW", findings=(finding,), connector_peer_pin_coverage=fault_coverage
    )
    control_alias = SimpleNamespace(open_outlier_finding_count=0)
    control_coverage = SimpleNamespace(
        footprint_alias_coverage=control_alias,
        model_dump=lambda *, mode: {"status": "PASS"},
    )
    control = SimpleNamespace(
        status="PASS", findings=(), connector_peer_pin_coverage=control_coverage
    )
    observed = SimpleNamespace(
        components={
            reference: SimpleNamespace(
                part_id=None,
                value="Synthetic mode-dependent signal peer",
                footprint="Synthetic:Package",
            )
            for reference in ("J1", "J2")
        },
        component_symbols={"J1": "Lint:ModeSignalA", "J2": "Lint:ModeSignalB"},
        component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
        pin_functions={"J1.1": "DATA_IO", "J2.1": "DATA_IO", "J1.2": "2", "J2.2": "2"},
        pin_electrical_types={
            "J1.1": "bidirectional",
            "J2.1": "bidirectional",
            "J1.2": "passive",
            "J2.2": "passive",
        },
        nets={"DATA_IO": ("J1.1",), "COMMON_ANCHOR": ("J1.2", "J2.2")},
    )
    control_observed = SimpleNamespace(
        nets={"DATA_IO": ("J1.1", "J2.1"), "COMMON_ANCHOR": ("J1.2", "J2.2")}
    )
    context = SimpleNamespace(
        reports={(FAULT_CASE, "first"): fault, (CONTROL_CASE, "first"): control},
        observed_contracts={
            (FAULT_CASE, "first"): observed,
            (CONTROL_CASE, "first"): control_observed,
        },
        netlist_hashes={(FAULT_CASE, "first"): "synthetic-native-netlist-hash"},
    )

    receipts = verify_footprint_alias_named_signal_mode_dependent_open(context)

    assert tuple(receipts) == FIXTURE_CASES
    assert json.loads(receipts[FAULT_CASE]) == {"netlist_sha256": "synthetic-native-netlist-hash"}
    assert json.loads(receipts[CONTROL_CASE]) == {"status": "PASS"}


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="digest-pinned native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_mode_dependent_signal_fault_and_control_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )
    from kicad_tooling.hwrepo.electrical import selected_config

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic native fixture enables partial-open signal review.",
            ),
        )
    )
    root, _ = synthetic_design_lint_project(
        tmp_path,
        policy,
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)

    log = HostedLog(root, f"native-mode-dependent-signal-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="mode-dependent-signal-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "mode-dependent-signal-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])
    verify_footprint_alias_named_signal_mode_dependent_open(context)

    fault = context.reports[FAULT_CASE, "first"]
    assert fault.status == "REVIEW"
    assert fault.findings[0].rule_id == RULE_ID
    assert fault.findings[0].evidence["assignments"] == (
        "J1.1=DATA_IO",
        "J2.1=<unassigned>",
    )
    for case in FIXTURE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
