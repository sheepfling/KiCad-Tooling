"""Run the scoped partial-open heuristic on pinned native KiCad exports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_connector_return_context import (
    prepare_connector_return_fixture_context,
)
from kicad_tooling.ci_hosted_connector_return_fixture_sources import (
    CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
    connector_return_fixture_sources,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.connector_peer_unanchored_scope_support import lint_report, reviewed_coverage
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

RULE_ID = "connector.footprint_peer_pin_open_outlier"
FAULT_CASE = "footprint-alias-unanchored-partial-open-fault"
CONTROL_CASE = "footprint-alias-control"
SOURCE_HASHES = {
    FAULT_CASE: "fb4fc447ef05fc97699b84bf5a21b7d106ed32e56e31059196982fa76d98e124",
    CONTROL_CASE: "d5c77a1b8de808ab82c9f98f0172af7f6f933ce43536dabe00c6fbf83e048e28",
}

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_scoped_partial_open_native_fixture_repeats(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    fixture_sources = connector_return_fixture_sources(fixture_root)
    assert {case: CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES[case] for case in SOURCE_HASHES} == (
        SOURCE_HASHES
    )
    assert {case: fixture_sources[case] for case in SOURCE_HASHES} == {
        FAULT_CASE: fixture_root
        / "connector-footprint-alias-native/unanchored-partial-open-fault.kicad_sch",
        CONTROL_CASE: fixture_root / "connector-footprint-alias-native/control.kicad_sch",
    }

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
    log = HostedLog(root, f"native-scoped-partial-open-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project,
        image=config.image,
        log=log,
        case_names=(FAULT_CASE, CONTROL_CASE),
        stage_prefix="scoped-partial-open-fixture",
    )
    assert context.source_hashes == SOURCE_HASHES
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    export_events = tuple(
        event
        for event in events
        if event.get("stage") == "scoped-partial-open-fixture/native-export"
    )
    assert tuple(event["status"] for event in export_events) == ("START", "PASS")
    assert export_events[-1]["kicad_version"] == version
    assert_native_fixture_mounts(root, export_events[-1]["command_receipt"])

    reports = {
        case: tuple(
            lint_report(
                context.observed_contracts[case, run],
                reviewed_coverage(context.observed_contracts[case, run]),
            )
            for run in ("first", "repeat")
        )
        for case in (FAULT_CASE, CONTROL_CASE)
    }
    findings = tuple(item for item in reports[FAULT_CASE][0].findings if item.rule_id == RULE_ID)
    assert len(findings) == 1
    assert findings[0].evidence["open_pins"] == ("J2.2",)
    assert findings[0].evidence["common_anchor_pin_numbers"] == ()
    assert reports[FAULT_CASE][1].model_dump(mode="json") == reports[FAULT_CASE][0].model_dump(
        mode="json"
    )
    assert not any(item.rule_id == RULE_ID for item in reports[CONTROL_CASE][0].findings)
    assert reports[CONTROL_CASE][1].model_dump(mode="json") == reports[CONTROL_CASE][0].model_dump(
        mode="json"
    )
