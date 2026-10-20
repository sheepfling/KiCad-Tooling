"""Exact-version native fixtures for named power inputs open on every alias."""

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
from kicad_tooling.ci_hosted_connector_return_named_power_input_all_open import (
    CONTROL_CASE,
    FAULT_CASE,
    RULE_ID,
    verify_footprint_alias_named_power_input_all_open,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

FIXTURE_CASES = (FAULT_CASE, CONTROL_CASE)
EXPECTED_SOURCE_HASHES = {
    FAULT_CASE: "fc7bf0d75bcc8775e39328d6e9cf0e19a2c244f3ac1b782fed9d95e23b30271d",
    CONTROL_CASE: "8b055617a737dde04b6647a7ce8f5e4a167aa9567b712a1b0d88696eae1f8a7c",
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_input_all_open_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/connector-footprint-named-power-input-all-open-native"
    )
    assert {
        case: hashlib.sha256((fixture_root / f"{name}.kicad_sch").read_bytes()).hexdigest()
        for case, name in ((FAULT_CASE, "fault"), (CONTROL_CASE, "control"))
    } == EXPECTED_SOURCE_HASHES


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_input_all_open_fixtures_are_registered_for_hosted_capture() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    sources = connector_return_fixture_sources(fixture_root)

    for case, name in ((FAULT_CASE, "fault"), (CONTROL_CASE, "control")):
        assert sources[case] == (
            fixture_root
            / "connector-footprint-named-power-input-all-open-native"
            / f"{name}.kicad_sch"
        )
        assert case in CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES
        assert CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] == EXPECTED_SOURCE_HASHES[case]


def test_named_power_input_all_open_validator_checks_fault_and_control() -> None:
    fault_alias = SimpleNamespace(
        candidate_group_count=1,
        eligible_peer_group_count=1,
        peer_scope_group_count=1,
        common_anchor_group_count=1,
        named_power_input_all_open_peer_pin_group_count=1,
        named_power_input_all_open_finding_count=1,
        unanchored_named_power_input_all_open_peer_pin_group_count=0,
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
            "pin_electrical_type": ("power_in",),
            "common_anchor_pin_numbers": ("2",),
        },
    )
    fault = SimpleNamespace(
        status="REVIEW",
        findings=(finding,),
        connector_peer_pin_coverage=fault_coverage,
    )
    control_alias = SimpleNamespace(
        named_power_input_all_open_peer_pin_group_count=0,
        named_power_input_all_open_finding_count=0,
    )
    control = SimpleNamespace(
        status="PASS",
        findings=(),
        connector_peer_pin_coverage=SimpleNamespace(footprint_alias_coverage=control_alias),
    )
    components = {
        reference: SimpleNamespace(
            part_id=None,
            value="Synthetic named power-input peer",
            footprint="Synthetic:Package",
        )
        for reference in ("J1", "J2")
    }
    observed = SimpleNamespace(
        components=components,
        component_symbols={"J1": "Lint:NamedPeerPowerInputA", "J2": "Lint:NamedPeerPowerInputB"},
        component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
        pin_functions={"J1.1": "BIAS_IN", "J2.1": "BIAS_IN", "J1.2": "2", "J2.2": "2"},
        pin_electrical_types={
            "J1.1": "power_in",
            "J2.1": "power_in",
            "J1.2": "passive",
            "J2.2": "passive",
        },
        nets={"COMMON_ANCHOR": ("J1.2", "J2.2")},
    )
    control_observed = SimpleNamespace(
        nets={"BIAS_INPUT": ("J1.1", "J2.1"), "COMMON_ANCHOR": ("J1.2", "J2.2")}
    )
    context = SimpleNamespace(
        reports={(FAULT_CASE, "first"): fault, (CONTROL_CASE, "first"): control},
        observed_contracts={
            (FAULT_CASE, "first"): observed,
            (CONTROL_CASE, "first"): control_observed,
        },
        netlist_hashes={(FAULT_CASE, "first"): "synthetic-native-netlist-hash"},
    )

    receipts = verify_footprint_alias_named_power_input_all_open(context)

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
def test_native_named_power_input_all_open_fault_and_control_are_repeatable(
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
                reason="Synthetic native fixture enables named all-open input review.",
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

    log = HostedLog(root, f"native-named-power-input-all-open-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="named-power-input-all-open-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "named-power-input-all-open-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])
    verify_footprint_alias_named_power_input_all_open(context)

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
