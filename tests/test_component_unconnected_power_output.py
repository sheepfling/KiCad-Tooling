"""Review heuristics for generic native power-output pins left open."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import HostedLog, component_unconnected_power_output_fixture_lane
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.component_peer_pin_support import peer_power_output_netlist
from tests.design_lint_fixtures import (
    coach,
    generic_component_power_output_netlist,
)
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.power_lint]

RULE_ID = "component.unconnected_power_output"


def _report(
    source: NetlistContract,
    policy: DesignLintPolicy | None = None,
):
    return evaluate("synthetic-generic-power-output", coach(source), policy or DesignLintPolicy())


def test_unconnected_generic_power_output_is_an_evidence_backed_review() -> None:
    report = _report(generic_component_power_output_netlist())

    assert report.status == "REVIEW"
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.rule_id == RULE_ID
    assert finding.subject == "U1.1: generic native power-output pin is unassigned"
    assert finding.evidence == {
        "symbol": ("Synthetic:GenericPowerOutputComponent",),
        "pin_electrical_type": ("power_out",),
        "U1.1": (),
        "native_pin_function": ("1",),
    }
    assert "does not identify the pin's specific role" in finding.message


def test_absent_generic_pin_function_is_still_reviewed() -> None:
    report = _report(generic_component_power_output_netlist(function=None))

    assert {item.rule_id for item in report.findings} == {RULE_ID}
    assert "native_pin_function" not in report.findings[0].evidence


def test_generic_pin_placeholder_is_reviewed() -> None:
    report = _report(generic_component_power_output_netlist(function="Pin_1"))

    assert {item.rule_id for item in report.findings} == {RULE_ID}


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(generic_component_power_output_netlist(connected=True), id="assigned"),
        pytest.param(generic_component_power_output_netlist(dnp_references=("U1",)), id="dnp"),
        pytest.param(
            generic_component_power_output_netlist(electrical_type="passive"), id="passive"
        ),
        pytest.param(
            generic_component_power_output_netlist(electrical_type="power_in"), id="power-in"
        ),
        pytest.param(generic_component_power_output_netlist(function="VOUT"), id="named-output"),
        pytest.param(
            generic_component_power_output_netlist(function="OUT"), id="role-labelled-output"
        ),
        pytest.param(generic_component_power_output_netlist(reference="J1"), id="connector"),
    ),
)
def test_valid_pin_controls_do_not_emit_the_generic_power_output_rule(
    source: NetlistContract,
) -> None:
    assert RULE_ID not in {item.rule_id for item in _report(source).findings}


def test_comparable_open_peer_keeps_its_more_specific_rule_only() -> None:
    report = _report(peer_power_output_netlist(output_function="Pin_2"))

    rule_ids = {item.rule_id for item in report.findings}
    assert rule_ids == {"component.peer_power_output_unconnected"}
    assert RULE_ID not in rule_ids


def test_generic_rule_remains_available_when_peer_rule_is_disabled() -> None:
    report = _report(
        peer_power_output_netlist(output_function="Pin_2"),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="component.peer_power_output_unconnected",
                    mode="off",
                    reason="Synthetic project reviews open outputs individually",
                ),
            )
        ),
    )

    generic = [item for item in report.findings if item.rule_id == RULE_ID]
    assert len(generic) == 1
    assert generic[0].evidence["U2.2"] == ()


def test_policy_can_block_ignore_or_disable_the_review() -> None:
    source = generic_component_power_output_netlist()
    initial = _report(source)
    finding = next(item for item in initial.findings if item.rule_id == RULE_ID)

    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic owner requires every output pin to be dispositioned",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic reviewed design intentionally leaves this output open",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert ignored.findings[0].disposition == "IGNORED"

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
    assert disabled.findings[0].disposition == "RULE_OFF"


def test_finding_is_mapping_order_stable_and_assignment_clears_it() -> None:
    source = generic_component_power_output_netlist()
    initial = _report(source)
    finding = next(item for item in initial.findings if item.rule_id == RULE_ID)
    reordered = _report(
        source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
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

    assigned = source.model_copy(update={"nets": {**source.nets, "POWER_OUTPUT": ("U1.1",)}})
    assert RULE_ID not in {item.rule_id for item in _report(assigned).findings}


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES") != "1",
    reason="pinned native fixtures run in package acceptance",
)
def test_generic_power_output_fault_and_control_on_pinned_native_versions(
    tmp_path: Path,
) -> None:
    fixture_root = (
        Path(__file__).resolve().parent / "fixtures/design_lint/generic-component-power-output"
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
        log = HostedLog(root, f"native-component-power-output-{project}")
        component_unconnected_power_output_fixture_lane(
            root, project=project, image=config.image, log=log
        )

        events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
        results = {
            item["stage"]: item
            for item in events
            if item.get("stage", "").startswith("component-unconnected-power-output-fixture/")
        }
        assert set(results) == {
            "component-unconnected-power-output-fixture/native-export",
            "component-unconnected-power-output-fixture/fault",
            "component-unconnected-power-output-fixture/control",
        }
        exported = results["component-unconnected-power-output-fixture/native-export"]
        assert exported["status"] == "PASS"
        assert exported["kicad_version"] == version
        assert exported["image"] == PINNED_NATIVE_KICAD_IMAGES[version]
        for case, lint_status, finding_count in (
            ("fault", "REVIEW", 1),
            ("control", "PASS", 0),
        ):
            result = results[f"component-unconnected-power-output-fixture/{case}"]
            assert result["status"] == "PASS"
            assert result["source_sha256"] == source_hashes[case]
            assert result["lint_status"] == lint_status
            assert result["finding_count"] == finding_count
            assert result["repeatable"] == "true"
            assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
