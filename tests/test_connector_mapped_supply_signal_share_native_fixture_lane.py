"""Exact KiCad exports for mapped connector supply/signal net sharing."""

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
from tests.design_lint_fixtures.connector_mapped_supply_signal_sharing import (
    supply_signal_coverage,
    supply_signal_report,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "connector.mapped_supply_signal_share_net"
FIXTURE_CASES = {
    "mapped-supply-signal-share-fault": (
        "fault.kicad_sch",
        "1fed938a34c42fcbb5518de81eca7bf2698e47e6b739c750e77ee56e914bd8a5",
    ),
    "mapped-supply-signal-share-control": (
        "control.kicad_sch",
        "b71ebb62b93bd63a6f52c4540f41e85ddafede34253df708e4834b71272dbb15",
    ),
}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="exact-version native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"), (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
)
@pytest.mark.parametrize("fixture_case", tuple(FIXTURE_CASES))
def test_native_mapped_supply_signal_share_fault_and_control(
    tmp_path: Path,
    project: str,
    version: str,
    fixture_case: str,
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
    source_name, source_sha256 = FIXTURE_CASES[fixture_case]
    source = fixture_root / "mapped-supply-signal-share" / source_name
    assert connector_return_fixture_sources(fixture_root)[fixture_case] == source
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha256
    assert CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[fixture_case] == source_sha256

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

    log = HostedLog(root, f"native-mapped-supply-signal-share-{project}-{fixture_case}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=(fixture_case,),
        stage_prefix="mapped-supply-signal-share-native",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "mapped-supply-signal-share-native/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == {fixture_case: source_sha256}
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    observed = context.observed_contracts[fixture_case, "first"]
    assert observed.pin_functions["J1.1"] == "1"
    assert observed.pin_functions["J1.2"] == "2"
    report, coverage = supply_signal_report(
        observed,
        coverage=supply_signal_coverage(observed),
    )
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert coverage.status == "COMPLETE"
    assert (
        context.normalized_netlist_hashes[fixture_case, "first"]
        == context.normalized_netlist_hashes[fixture_case, "repeat"]
    )
    if fixture_case.endswith("fault"):
        assert observed.nets["SHARED_NET"] == ("J1.1", "J1.2")
        assert len(findings) == 1
        assert findings[0].evidence["assigned_net"] == ("SHARED_NET",)
    else:
        assert observed.nets["SUPPLY_NET"] == ("J1.1",)
        assert observed.nets["SIGNAL_NET"] == ("J1.2",)
        assert not findings
