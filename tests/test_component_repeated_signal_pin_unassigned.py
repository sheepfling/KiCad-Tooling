"""Focused regressions for repeated signal-function pins left open."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_component_repeated_signal_pin_unassigned import (
    COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CASES,
    COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CONTROL,
    COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_FAULT,
    COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_RULE_ID,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.repeated_signal_pin_functions import (
    repeated_signal_pin_component,
    repeated_signal_pin_split_assignments_with_open_member,
    repeated_signal_pin_with_unassigned_member,
)
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

RULE_ID = COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_RULE_ID

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract | None = None,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    observed = repeated_signal_pin_with_unassigned_member() if source is None else source
    return evaluate(
        "synthetic-repeated-signal-pin-unassigned",
        coach(observed),
        DesignLintPolicy() if policy is None else policy,
    )


def _review_policy(mode: str = "review") -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="test policy"),)
    )


def test_open_repeated_signal_pin_requests_configurable_review_with_exact_evidence() -> None:
    report = _report(policy=_review_policy())
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == (
        "U1 (Lint:RepeatedSignalPins): repeated READY signal pins include an unassigned pin"
    )
    assert finding.evidence == {
        "U1.1": ("SIGNAL",),
        "U1.2": (),
        "assigned_signal_pins": ("U1.1",),
        "component_symbol": ("Lint:RepeatedSignalPins",),
        "electrical_type": ("input",),
        "pin_function": ("READY",),
        "unassigned_signal_pins": ("U1.2",),
    }
    assert "does not require the pins to be tied" in finding.message


def test_rule_is_opt_in_and_policy_can_promote_or_ignore_the_finding() -> None:
    default_finding = next(item for item in _report().findings if item.rule_id == RULE_ID)
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    assert _report().status == "PASS"
    assert _report(policy=_review_policy("block")).status == "FAIL"
    ignored = _report(
        policy=DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="test policy"),),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=default_finding.fingerprint,
                    reason="reviewed intentional open alternate",
                ),
            ),
        )
    )

    assert ignored.status == "PASS"


def test_open_member_is_reported_when_assigned_peers_are_split() -> None:
    source = repeated_signal_pin_split_assignments_with_open_member()
    findings = tuple(
        item for item in _report(source, _review_policy()).findings if item.rule_id == RULE_ID
    )
    assert len(findings) == 1
    assert findings[0].evidence["U1.1"] == ("SIGNAL_A",)
    assert findings[0].evidence["U1.2"] == ("SIGNAL_B",)
    assert findings[0].evidence["U1.3"] == ()


def _all_open_repeated_group() -> NetlistContract:
    source = repeated_signal_pin_with_unassigned_member()
    return source.model_copy(
        update={
            "nets": {"STATUS": ("U1.3",)},
            "unconnected_nets": {"unconnected": ("U1.1", "U1.2")},
        }
    )


def _connector_open_repeated_group() -> NetlistContract:
    source = repeated_signal_pin_component(reference="J1", symbol="Connector_Generic:Conn_01x04")
    return source.model_copy(
        update={
            "nets": {"SIGNAL": ("J1.1",), "STATUS": ("J1.3",)},
            "unconnected_nets": {"unconnected": ("J1.2",)},
        }
    )


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(repeated_signal_pin_component(split=False), id="common-net-control"),
        pytest.param(_all_open_repeated_group(), id="all-open-group"),
        pytest.param(
            repeated_signal_pin_with_unassigned_member().model_copy(
                update={"dnp_components": ("U1",)}
            ),
            id="dnp",
        ),
        pytest.param(_connector_open_repeated_group(), id="connector"),
        pytest.param(
            repeated_signal_pin_with_unassigned_member().model_copy(
                update={"pin_functions": {"U1.1": "READY", "U1.2": "READY", "U1.3": "STATUS"}}
            ),
            id="incomplete-native-inventory",
        ),
        pytest.param(
            repeated_signal_pin_with_unassigned_member().model_copy(
                update={
                    "pin_functions": {
                        "U1.1": "Pin_1",
                        "U1.2": "Pin_2",
                        "U1.3": "STATUS",
                        "U1.4": "Pin_4",
                    }
                }
            ),
            id="generic-functions",
        ),
        pytest.param(
            repeated_signal_pin_with_unassigned_member().model_copy(
                update={
                    "pin_functions": {
                        "U1.1": "VCC",
                        "U1.2": "VCC",
                        "U1.3": "STATUS",
                        "U1.4": "Pin_4",
                    }
                }
            ),
            id="supply-function",
        ),
        pytest.param(
            repeated_signal_pin_with_unassigned_member().model_copy(
                update={
                    "pin_functions": {
                        "U1.1": "GND",
                        "U1.2": "GND",
                        "U1.3": "STATUS",
                        "U1.4": "Pin_4",
                    }
                }
            ),
            id="return-function",
        ),
        pytest.param(
            repeated_signal_pin_with_unassigned_member().model_copy(
                update={
                    "pin_functions": {
                        "U1.1": "SHIELD",
                        "U1.2": "SHIELD",
                        "U1.3": "STATUS",
                        "U1.4": "Pin_4",
                    }
                }
            ),
            id="shield-function",
        ),
        pytest.param(
            repeated_signal_pin_with_unassigned_member().model_copy(
                update={
                    "pin_electrical_types": {
                        "U1.1": "input",
                        "U1.2": "output",
                        "U1.3": "input",
                        "U1.4": "passive",
                    }
                }
            ),
            id="different-electrical-types",
        ),
        pytest.param(
            repeated_signal_pin_with_unassigned_member().model_copy(
                update={"nets": {"SIGNAL": ("U1.1",), "OTHER": ("U1.2",), "STATUS": ("U1.3",)}}
            ),
            id="all-members-assigned-to-separate-nets",
        ),
        pytest.param(
            repeated_signal_pin_with_unassigned_member().model_copy(
                update={
                    "nets": {"SIGNAL": ("U1.1", "U1.2"), "OTHER": ("U1.2",), "STATUS": ("U1.3",)}
                }
            ),
            id="ambiguous-net-assignment",
        ),
    ],
)
def test_common_and_unsupported_shapes_stay_quiet(source: NetlistContract) -> None:
    report = _report(source, _review_policy())

    assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_mapping_order_is_stable_and_connection_repairs_the_finding() -> None:
    source = repeated_signal_pin_with_unassigned_member()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "unconnected_nets": dict(reversed(tuple(source.unconnected_nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
        }
    )
    original = next(
        item for item in _report(source, _review_policy()).findings if item.rule_id == RULE_ID
    )
    repeated = next(
        item for item in _report(reordered, _review_policy()).findings if item.rule_id == RULE_ID
    )
    connected = source.model_copy(
        update={"nets": {"SIGNAL": ("U1.1", "U1.2"), "STATUS": ("U1.3",)}, "unconnected_nets": {}}
    )

    assert repeated.evidence == original.evidence
    assert repeated.fingerprint == original.fingerprint
    assert not any(
        item.rule_id == RULE_ID for item in _report(connected, _review_policy()).findings
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_FIXTURES") != "1",
    reason="native fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"), (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
)
def test_native_open_repeated_signal_pin_fault_and_control_are_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_component_repeated_signal_pin_unassigned_lane import (
        component_repeated_signal_pin_unassigned_fixture_lane,
    )

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

    log = HostedLog(root, f"native-component-repeated-signal-pin-unassigned-{project}")
    component_repeated_signal_pin_unassigned_fixture_lane(
        root, project=project, image=config.image, log=log
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("component-repeated-signal-pin-unassigned-fixture/")
    }
    native_export = results["component-repeated-signal-pin-unassigned-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert (
        tuple(
            source_hash.split(":", 1)[0]
            for source_hash in native_export["source_hashes"].split(",")
        )
        == COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CASES
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    fault = results[
        f"component-repeated-signal-pin-unassigned-fixture/{COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_FAULT}"
    ]
    control = results[
        f"component-repeated-signal-pin-unassigned-fixture/{COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_CONTROL}"
    ]
    assert fault["status"] == control["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == RULE_ID
    assert fault["repeatable"] == "true"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    assert control["repeatable"] == "true"
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]
