"""Exact-version native fixtures for named signals open on every alias peer."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
    CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
    connector_return_fixture_sources,
)
from kicad_tooling.ci_hosted_connector_return_named_signal_all_open import (
    CONTROL_CASE,
    FAULT_CASE,
    RULE_ID,
    verify_footprint_alias_named_signal_all_open,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

FIXTURE_CASES = (FAULT_CASE, CONTROL_CASE)
EXPECTED_SOURCE_HASHES = MappingProxyType(
    {
        FAULT_CASE: "694b9284e1e08d029ffaf6c69198bb20a3179c2f90896f32cbecf9040b687af1",
        CONTROL_CASE: "f072787dbd52dafcc5e2fd0728ed2bc4add23653d8b4978c7472aa658b660d8f",
    }
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_signal_all_open_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/connector-footprint-named-signal-all-open-native"
    )
    control_source = (
        fixture_root.parent / "connector-footprint-named-signal-output-native/control.kicad_sch"
    )
    assert (
        hashlib.sha256((fixture_root / "fault.kicad_sch").read_bytes()).hexdigest()
        == (EXPECTED_SOURCE_HASHES[FAULT_CASE])
    )
    assert (
        hashlib.sha256(control_source.read_bytes()).hexdigest()
        == EXPECTED_SOURCE_HASHES[CONTROL_CASE]
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_signal_all_open_fixtures_are_registered_for_hosted_capture() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)

    assert sources[FAULT_CASE] == (
        fixture_root / "connector-footprint-named-signal-all-open-native/fault.kicad_sch"
    )
    assert sources[CONTROL_CASE] == (
        fixture_root / "connector-footprint-named-signal-output-native/control.kicad_sch"
    )
    assert all(
        CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] == EXPECTED_SOURCE_HASHES[case]
        for case in FIXTURE_CASES
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_signal_all_open_validator_checks_fault_and_control() -> None:
    fault_alias = SimpleNamespace(
        candidate_group_count=1,
        eligible_peer_group_count=1,
        peer_scope_group_count=1,
        common_anchor_group_count=1,
        named_signal_all_open_peer_pin_group_count=1,
        named_signal_all_open_finding_count=1,
        unanchored_named_signal_all_open_peer_pin_group_count=0,
    )
    fault_coverage = SimpleNamespace(
        netlist_sha256="synthetic-native-netlist-hash",
        footprint_alias_coverage=fault_alias,
        model_dump=lambda *, mode: {"netlist_sha256": "synthetic-native-netlist-hash"},
    )
    finding = SimpleNamespace(
        rule_id=RULE_ID,
        evidence={
            "assignments": ("J1.1=<unassigned>", "J2.1=<unassigned>"),
            "pin_electrical_type": ("output",),
            "common_anchor_pin_numbers": ("2",),
        },
    )
    fault = SimpleNamespace(
        status="REVIEW", findings=(finding,), connector_peer_pin_coverage=fault_coverage
    )
    control_alias = SimpleNamespace(
        named_signal_all_open_peer_pin_group_count=0,
        named_signal_all_open_finding_count=0,
    )
    control = SimpleNamespace(
        status="PASS",
        findings=(),
        connector_peer_pin_coverage=SimpleNamespace(footprint_alias_coverage=control_alias),
    )
    components = {
        reference: SimpleNamespace(
            part_id=None,
            value="Synthetic named signal-output peer",
            footprint="Synthetic:Package",
        )
        for reference in ("J1", "J2")
    }
    observed = SimpleNamespace(
        components=components,
        component_symbols={
            "J1": "Lint:NamedPeerSignalOutputA",
            "J2": "Lint:NamedPeerSignalOutputB",
        },
        component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
        pin_functions={"J1.1": "UART_TX", "J2.1": "UART_TX", "J1.2": "2", "J2.2": "2"},
        pin_electrical_types={
            "J1.1": "output",
            "J2.1": "output",
            "J1.2": "passive",
            "J2.2": "passive",
        },
        nets={"COMMON_ANCHOR": ("J1.2", "J2.2")},
    )
    control_observed = SimpleNamespace(
        nets={"UART_TX": ("J1.1", "J2.1"), "COMMON_ANCHOR": ("J1.2", "J2.2")}
    )
    context = SimpleNamespace(
        reports={(FAULT_CASE, "first"): fault, (CONTROL_CASE, "first"): control},
        observed_contracts={
            (FAULT_CASE, "first"): observed,
            (CONTROL_CASE, "first"): control_observed,
        },
        netlist_hashes={(FAULT_CASE, "first"): "synthetic-native-netlist-hash"},
    )

    receipts = verify_footprint_alias_named_signal_all_open(context)

    assert tuple(receipts) == (FAULT_CASE,)
    assert json.loads(receipts[FAULT_CASE]) == {"netlist_sha256": "synthetic-native-netlist-hash"}


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
def test_native_named_signal_all_open_fault_and_control_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic native fixture enables named all-open signal review.",
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

    log = HostedLog(root, f"native-named-signal-all-open-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="named-signal-all-open-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "named-signal-all-open-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])
    verify_footprint_alias_named_signal_all_open(context)

    fault = context.reports[FAULT_CASE, "first"]
    assert fault.status == "REVIEW"
    assert fault.findings[0].rule_id == RULE_ID
    assert fault.findings[0].evidence["assignments"] == (
        "J1.1=<unassigned>",
        "J2.1=<unassigned>",
    )
    for case in FIXTURE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
