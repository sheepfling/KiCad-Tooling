"""Exact KiCad export evidence for the mapped-other named-rail heuristic."""

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
from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import ContractCoachReport
from tests.design_lint_fixtures.connector_mapped_other_named_rail import (
    native_return_board_coverage,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]

RULE_ID = "connector.mapped_interface_other_named_rail"
FIXTURE_CASE = "ret-control"
EXPECTED_SOURCE_SHA256 = "7fb0e168dcf55270162327d4480c3dec21dac3c5c80cfc4fe9d3a7f3c3d70efa"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="exact-version native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"), (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
)
def test_native_single_other_pin_on_ret_is_reviewed_and_role_control_is_clean(
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
    assert source == fixture_root / "four-port-db9-returns/ret-control.kicad_sch"
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

    log = HostedLog(root, f"native-mapped-other-named-rail-{project}")
    context = prepare_connector_return_fixture_context(
        root,
        project=project,
        image=config.image,
        log=log,
        case_names=(FIXTURE_CASE,),
        stage_prefix="mapped-other-named-rail-native",
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    native_events = tuple(
        item
        for item in events
        if item.get("stage") == "mapped-other-named-rail-native/native-export"
    )
    assert tuple(item["status"] for item in native_events) == ("START", "PASS")
    assert native_events[-1]["kicad_version"] == version
    assert context.source_hashes == {FIXTURE_CASE: EXPECTED_SOURCE_SHA256}
    assert_native_fixture_mounts(root, native_events[-1]["command_receipt"])

    observed = context.observed_contracts[FIXTURE_CASE, "first"]
    assert "7" in observed.component_pin_numbers["J1"]
    assert observed.pin_functions["J1.7"] == "7"
    assert (
        context.normalized_netlist_hashes[FIXTURE_CASE, "first"]
        == context.normalized_netlist_hashes[FIXTURE_CASE, "repeat"]
    )
    assert observed.nets["RET"].count("J1.7") == 1

    fault_coverage = native_return_board_coverage(observed, other_pins=frozenset({"J1.7"}))
    control_coverage = native_return_board_coverage(observed)
    netlist_sha256 = hashlib.sha256(model_json_bytes(observed)).hexdigest()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-native-mapped-other-rail",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )
    fault = evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(),
        connector_coverage=fault_coverage,
    )
    control = evaluate(
        coach.project_id,
        coach,
        DesignLintPolicy(),
        connector_coverage=control_coverage,
    )
    fault_findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    control_findings = tuple(item for item in control.findings if item.rule_id == RULE_ID)
    assert fault_coverage.status == control_coverage.status == "COMPLETE"
    assert len(fault_findings) == 1
    assert fault_findings[0].evidence["component_pin"] == ("J1.7",)
    assert fault_findings[0].evidence["assigned_nets"] == ("RET",)
    assert not control_findings
