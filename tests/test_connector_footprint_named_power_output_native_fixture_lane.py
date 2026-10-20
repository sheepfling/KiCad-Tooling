"""Exact-version native acceptance for split named connector power outputs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted_connector_return_named_power_output_divergence import (
    CONTROL_CASE,
    FAULT_CASE,
    RULE_ID,
    verify_footprint_alias_named_power_output_divergence,
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
    FAULT_CASE: "4c46589c7cd8b8ef9ec6db778b10c5f7200918b92dfb60c522208dcc24d243b9",
    CONTROL_CASE: "ca350129168dc67fe71153a59a53d7901c92e413119798463cdca04d96e43482",
}


def test_named_power_output_divergence_fixture_sources_match_reviewed_hashes() -> None:
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures/design_lint/connector-footprint-named-power-output-divergence-native"
    )
    assert {
        case: hashlib.sha256((fixture_root / f"{name}.kicad_sch").read_bytes()).hexdigest()
        for case, name in ((FAULT_CASE, "fault"), (CONTROL_CASE, "control"))
    } == EXPECTED_SOURCE_HASHES


def test_named_power_output_divergence_validator_checks_fault_and_control() -> None:
    fault_alias = SimpleNamespace(
        status="EVALUATED",
        candidate_group_count=1,
        eligible_peer_group_count=1,
        peer_scope_group_count=1,
        common_anchor_group_count=1,
        different_assignment_pin_group_count=1,
        named_power_output_different_assignment_pin_group_count=1,
        named_power_output_divergence_finding_count=1,
        unanchored_named_power_output_divergence_pin_group_count=0,
    )
    fault_coverage = SimpleNamespace(
        netlist_sha256="synthetic-native-netlist-hash",
        footprint_alias_coverage=fault_alias,
        model_dump=lambda *, mode: {"netlist_sha256": "synthetic-native-netlist-hash"},
    )
    finding = SimpleNamespace(
        rule_id=RULE_ID,
        evidence={
            "assignments": ("J1.1=BIAS_OUTPUT_A", "J2.1=BIAS_OUTPUT_B"),
            "pin_electrical_type": ("power_out",),
            "common_anchor_pin_numbers": ("2",),
        },
    )
    fault = SimpleNamespace(
        status="REVIEW",
        findings=(finding,),
        connector_peer_pin_coverage=fault_coverage,
    )
    control_alias = SimpleNamespace(
        named_power_output_different_assignment_pin_group_count=0,
        named_power_output_divergence_finding_count=0,
    )
    control = SimpleNamespace(
        status="PASS",
        findings=(),
        connector_peer_pin_coverage=SimpleNamespace(footprint_alias_coverage=control_alias),
    )
    components = {
        reference: SimpleNamespace(
            part_id=None,
            value="Synthetic named power-output peer",
            footprint="Synthetic:Package",
        )
        for reference in ("J1", "J2")
    }
    observed = SimpleNamespace(
        components=components,
        component_symbols={"J1": "Lint:NamedPeerPowerOutputA", "J2": "Lint:NamedPeerPowerOutputB"},
        component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
        pin_functions={"J1.1": "BIAS_OUT", "J2.1": "BIAS_OUT", "J1.2": "2", "J2.2": "2"},
        pin_electrical_types={
            "J1.1": "power_out",
            "J2.1": "power_out",
            "J1.2": "passive",
            "J2.2": "passive",
        },
        nets={
            "BIAS_OUTPUT_A": ("J1.1",),
            "BIAS_OUTPUT_B": ("J2.1",),
            "COMMON_ANCHOR": ("J1.2", "J2.2"),
        },
    )
    control_observed = SimpleNamespace(
        nets={"BIAS_OUTPUT": ("J1.1", "J2.1"), "COMMON_ANCHOR": ("J1.2", "J2.2")}
    )
    context = SimpleNamespace(
        reports={(FAULT_CASE, "first"): fault, (CONTROL_CASE, "first"): control},
        observed_contracts={
            (FAULT_CASE, "first"): observed,
            (CONTROL_CASE, "first"): control_observed,
        },
        netlist_hashes={(FAULT_CASE, "first"): "synthetic-native-netlist-hash"},
    )

    receipts = verify_footprint_alias_named_power_output_divergence(context)

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
def test_native_named_power_output_divergence_fault_and_control_are_repeatable(
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
                reason="Synthetic native fixture enables this bounded review heuristic.",
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

    log = HostedLog(root, f"native-named-power-output-divergence-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=FIXTURE_CASES,
        stage_prefix="named-power-output-divergence-fixture",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "named-power-output-divergence-fixture/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == EXPECTED_SOURCE_HASHES
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])
    verify_footprint_alias_named_power_output_divergence(context)

    fault = context.reports[FAULT_CASE, "first"]
    assert fault.status == "REVIEW"
    assert fault.findings[0].rule_id == RULE_ID
    assert fault.findings[0].evidence["assignments"] == (
        "J1.1=BIAS_OUTPUT_A",
        "J2.1=BIAS_OUTPUT_B",
    )
    for case in FIXTURE_CASES:
        assert (
            context.normalized_netlist_hashes[case, "first"]
            == context.normalized_netlist_hashes[case, "repeat"]
        )
