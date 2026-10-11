"""Review heuristics for generic connector power-output pins left open."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, connector_unconnected_power_output_fixture_lane
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import (
    coach,
    generic_connector_power_input_netlist,
    generic_connector_power_output_netlist,
)
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.unconnected_power_output"


def _report(
    source: NetlistContract,
    policy: DesignLintPolicy | None = None,
):
    return evaluate(
        "synthetic-generic-connector-power-output", coach(source), policy or DesignLintPolicy()
    )


def test_unassigned_generic_connector_power_output_contacts_are_reviewed() -> None:
    report = _report(generic_connector_power_output_netlist())

    assert report.status == "REVIEW"
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert {item.subject for item in findings} == {
        "J1.1: generic native power-output pin is unassigned",
        "J2.1: generic native power-output pin is unassigned",
    }
    assert len(findings) == 2
    assert findings[0].evidence == {
        "symbol": ("Synthetic:GenericPowerOutputPort",),
        "pin_electrical_type": ("power_out",),
        "J1.1": (),
        "native_pin_function": ("1",),
    }
    assert "does not identify the contact's specific role" in findings[0].message


@pytest.mark.parametrize(
    "function",
    (
        pytest.param(None, id="absent"),
        pytest.param("", id="blank"),
        pytest.param("Pin_1", id="placeholder"),
    ),
)
def test_absent_or_generic_native_function_is_reviewed(function: str | None) -> None:
    report = _report(generic_connector_power_output_netlist(function=function))

    assert len([item for item in report.findings if item.rule_id == RULE_ID]) == 2
    if function in {None, ""}:
        assert (
            "native_pin_function"
            not in next(item for item in report.findings if item.rule_id == RULE_ID).evidence
        )


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(generic_connector_power_output_netlist(connected=True), id="assigned"),
        pytest.param(generic_connector_power_output_netlist(dnp_references=("J1", "J2")), id="dnp"),
        pytest.param(
            generic_connector_power_input_netlist(electrical_type="power_in"), id="power-in"
        ),
        pytest.param(
            generic_connector_power_input_netlist(electrical_type="passive"), id="passive"
        ),
        pytest.param(generic_connector_power_output_netlist(function="VBUS"), id="named-supply"),
        pytest.param(generic_connector_power_output_netlist(function="OUT"), id="named-output"),
        pytest.param(
            generic_connector_power_output_netlist(references=("U1",)), id="non-connector"
        ),
    ),
)
def test_valid_and_out_of_scope_contacts_do_not_emit_the_rule(source: NetlistContract) -> None:
    assert RULE_ID not in {item.rule_id for item in _report(source).findings}


def test_typed_output_finding_owns_an_open_peer_outlier_when_enabled() -> None:
    source = generic_connector_power_output_netlist()
    source = source.model_copy(update={"nets": {"POWER_OUTPUT_TEST": ("J2.1",)}})

    report = _report(source)

    rule_ids = {item.rule_id for item in report.findings}
    assert RULE_ID in rule_ids
    assert "connector.peer_pin_assignment_outlier" not in rule_ids


def test_peer_outlier_remains_when_the_power_output_rule_is_disabled() -> None:
    source = generic_connector_power_output_netlist()
    source = source.model_copy(
        update={
            "nets": {"POWER_OUTPUT_TEST": ("J2.1",)},
            "pin_functions": {"J1.1": "Pin_1", "J2.1": "PWR"},
        }
    )
    report = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project uses peer differences only",
                ),
            )
        ),
    )

    assert "connector.peer_pin_assignment_outlier" in {
        item.rule_id for item in report.findings if item.disposition != "RULE_OFF"
    }


def test_project_can_block_ignore_or_disable_the_review() -> None:
    source = generic_connector_power_output_netlist(function="Pin_1")
    initial = _report(source)

    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic owner requires every connector power output to be decided",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=tuple(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic reviewed connector intentionally leaves the output open",
                )
                for finding in initial.findings
                if finding.rule_id == RULE_ID
            )
        ),
    )
    assert ignored.status == "PASS"
    assert any(item.disposition == "IGNORED" for item in ignored.findings)

    disabled = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project disables this advisory rule",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    assert any(item.disposition == "RULE_OFF" for item in disabled.findings)


def test_finding_is_mapping_order_stable_and_assignment_clears_it() -> None:
    source = generic_connector_power_output_netlist()
    initial = _report(source)
    finding = next(item for item in initial.findings if item.rule_id == RULE_ID)
    reordered = _report(
        source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            }
        )
    )
    reordered_finding = next(item for item in reordered.findings if item.rule_id == RULE_ID)
    assert (reordered_finding.fingerprint, reordered_finding.evidence) == (
        finding.fingerprint,
        finding.evidence,
    )

    assigned = source.model_copy(update={"nets": {"POWER_OUTPUT_TEST": ("J1.1", "J2.1")}})
    assert RULE_ID not in {item.rule_id for item in _report(assigned).findings}


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="pinned connector native fixtures run in package acceptance",
)
def test_generic_connector_power_output_fault_and_control_on_pinned_native_versions(
    tmp_path: Path,
) -> None:
    fixture_root = (
        Path(__file__).resolve().parent / "fixtures/design_lint/generic-connector-power-output"
    )
    source_hashes = {
        case: digest(fixture_root / f"{case}.kicad_sch") for case in ("fault", "control")
    }
    expected_versions = {"controller": "10.0.0", "raspberry-pi-status-led": "10.0.5"}

    for project, version in expected_versions.items():
        root, _ = synthetic_design_lint_project(
            tmp_path / project,
            DesignLintPolicy(),
            project_id=project,
            kicad_version=version,
            image=PINNED_NATIVE_KICAD_IMAGES[version],
        )
        config = selected_config(root, project)
        assert config.kicad_version == version
        assert config.image == PINNED_NATIVE_KICAD_IMAGES[version]
        log = HostedLog(root, f"native-connector-power-output-{project}")
        connector_unconnected_power_output_fixture_lane(
            root, project=project, image=config.image, log=log
        )

        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("connector-power-output-fixture/")
        }
        assert set(results) == {
            "connector-power-output-fixture/native-export",
            "connector-power-output-fixture/fault",
            "connector-power-output-fixture/control",
        }
        exported = results["connector-power-output-fixture/native-export"]
        assert exported["status"] == "PASS"
        assert exported["kicad_version"] == version
        assert exported["image"] == PINNED_NATIVE_KICAD_IMAGES[version]
        for case, lint_status, finding_count in (
            ("fault", "REVIEW", 2),
            ("control", "PASS", 0),
        ):
            result = results[f"connector-power-output-fixture/{case}"]
            assert result["status"] == "PASS"
            assert result["source_sha256"] == source_hashes[case]
            assert result["lint_status"] == lint_status
            assert result["finding_count"] == finding_count
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
