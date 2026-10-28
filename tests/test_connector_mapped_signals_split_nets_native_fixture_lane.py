"""Exact-version native exports for repeated mapped signal contacts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
    CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
    connector_return_fixture_sources,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from tests.design_lint_fixtures.connector_mapped_signal_sharing import (
    signal_sharing_coverage,
    signal_sharing_report,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "connector.mapped_signals_split_nets"
FIXTURE_CASE = "mapped-same-signal-split-nets"
EXPECTED_SOURCE_SHA256 = "fa11e55fe8cc046fd093eb3cb6fdd1c9a6cfc2c75a838320ea8ff720fa3c512e"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="exact-version native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"), (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
)
def test_native_split_nets_are_reviewed_only_for_repeated_mapped_signal(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )
    from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
    from tests.native_fixture_support import assert_native_fixture_mounts
    from tests.synthetic_design_lint_project import (
        PINNED_NATIVE_KICAD_IMAGES,
        synthetic_design_lint_project,
    )

    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    source = connector_return_fixture_sources(fixture_root)[FIXTURE_CASE]
    assert source == fixture_root / "mapped-repeated-signal-split-nets/split-signal.kicad_sch"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == EXPECTED_SOURCE_SHA256
    assert CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[FIXTURE_CASE] == EXPECTED_SOURCE_SHA256

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)

    log = HostedLog(root, f"native-mapped-signal-split-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=(FIXTURE_CASE,),
        stage_prefix="mapped-signal-split-native",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item for item in events if item.get("stage") == "mapped-signal-split-native/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == {FIXTURE_CASE: EXPECTED_SOURCE_SHA256}
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    observed = context.observed_contracts[FIXTURE_CASE, "first"]
    assert observed.pin_functions["J1.1"] == "1"
    assert observed.pin_functions["J1.2"] == "2"
    assert observed.nets["CONTACT_NET_A"] == ("J1.1",)
    assert observed.nets["CONTACT_NET_B"] == ("J1.2",)
    assert (
        context.normalized_netlist_hashes[FIXTURE_CASE, "first"]
        == context.normalized_netlist_hashes[FIXTURE_CASE, "repeat"]
    )

    fault_coverage = signal_sharing_coverage(observed, signal_names=("CONTROL", "control"))
    control_coverage = signal_sharing_coverage(
        observed,
        signal_names=("CONTROL_A", "CONTROL_B"),
    )
    fault, fault_coverage = signal_sharing_report(observed, coverage=fault_coverage)
    control, control_coverage = signal_sharing_report(observed, coverage=control_coverage)
    fault_findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    control_findings = tuple(item for item in control.findings if item.rule_id == RULE_ID)

    assert fault_coverage.status == control_coverage.status == "COMPLETE"
    assert len(fault_findings) == 1
    assert fault_findings[0].evidence["component_pin"] == ("J1.1", "J1.2")
    assert fault_findings[0].evidence["assigned_nets"] == (
        "CONTACT_NET_A",
        "CONTACT_NET_B",
    )
    assert not control_findings
