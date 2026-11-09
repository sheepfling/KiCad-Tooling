"""Exact-version native export for mapped open-signal peer context."""

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
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.electrical import selected_config
from tests.design_lint_fixtures.connector_reviewed_peer_signal_split import (
    peer_signal_coverage,
    peer_signal_report,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "connector.mapped_interface_signal_unassigned"
FIXTURE_CASE = "mapped-interface-peer-context-open"
EXPECTED_SOURCE_SHA256 = "8ac7fb8938022ec33b46c599a001ab3b6240b27ae79fdbb0e63362a4ff401b1b"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="exact-version native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"), (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
)
def test_native_open_mapped_signal_peer_context_and_reasoned_control(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted_connector_return_context import (
        prepare_connector_return_fixture_context,
    )
    from tests.native_fixture_support import assert_native_fixture_mounts
    from tests.synthetic_design_lint_project import (
        PINNED_NATIVE_KICAD_IMAGES,
        synthetic_design_lint_project,
    )

    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    source = connector_return_fixture_sources(fixture_root)[FIXTURE_CASE]
    assert source == fixture_root / "mapped-interface-peer-context-native/open-peer.kicad_sch"
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

    log = HostedLog(root, f"native-mapped-peer-context-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=(FIXTURE_CASE,),
        stage_prefix="mapped-interface-peer-context-native",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "mapped-interface-peer-context-native/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == {FIXTURE_CASE: EXPECTED_SOURCE_SHA256}
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    observed = context.observed_contracts[FIXTURE_CASE, "first"]
    assert observed.nets["SHARED_RX_NET"] == ("J1.2",)
    assert (
        context.normalized_netlist_hashes[FIXTURE_CASE, "first"]
        == (context.normalized_netlist_hashes[FIXTURE_CASE, "repeat"])
    )

    fault_coverage = peer_signal_coverage(observed)
    control_coverage = peer_signal_coverage(
        observed,
        unconnected_reasons=(None, "Reviewed as an intentionally unused signal contact"),
    )
    fault = peer_signal_report(observed, coverage=fault_coverage)
    control = peer_signal_report(observed, coverage=control_coverage)
    fault_findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    control_findings = tuple(item for item in control.findings if item.rule_id == RULE_ID)

    assert fault_coverage.status == control_coverage.status == "COMPLETE"
    assert len(fault_findings) == 1
    assert fault_findings[0].evidence["component_pin"] == ("J2.7",)
    assert fault_findings[0].evidence["peer_component_pin"] == ("J1.2",)
    assert fault_findings[0].evidence["peer_assigned_nets"] == ("SHARED_RX_NET",)
    assert "does not require commoning" in fault_findings[0].message
    assert not control_findings
