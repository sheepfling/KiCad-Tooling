"""Focused regressions for repeated signal-function assignments on one IC."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling import ci_hosted_connector_return_context as connector_return_context
from kicad_tooling.ci_hosted_component_repeated_signal_pins import (
    COMPONENT_REPEATED_SIGNAL_PIN_CASES,
    COMPONENT_REPEATED_SIGNAL_PIN_CONTROL,
    COMPONENT_REPEATED_SIGNAL_PIN_FAULT,
    COMPONENT_REPEATED_SIGNAL_PIN_RULE_ID,
)
from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.repeated_signal_pin_functions import repeated_signal_pin_component
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

RULE_ID = COMPONENT_REPEATED_SIGNAL_PIN_RULE_ID

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract | None = None,
    policy: DesignLintPolicy | None = None,
) -> DesignLintReport:
    observed = repeated_signal_pin_component() if source is None else source
    return evaluate(
        "synthetic-repeated-signal-pins",
        coach(observed),
        DesignLintPolicy() if policy is None else policy,
    )


def _review_policy(mode: str = "review") -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="test policy"),)
    )


def test_split_repeated_signal_pins_request_configurable_review_with_exact_evidence() -> None:
    report = _report(policy=_review_policy())
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert finding.subject == (
        "U1 (Lint:RepeatedSignalPins): repeated READY signal pins use separate nets"
    )
    assert finding.evidence == {
        "U1.1": ("SIGNAL_A",),
        "U1.2": ("SIGNAL_B",),
        "component_symbol": ("Lint:RepeatedSignalPins",),
        "electrical_type": ("input",),
        "pin_function": ("READY",),
    }
    assert "does not require the pins to be tied" in finding.message


def test_rule_is_opt_in_by_default_and_project_policy_controls_it() -> None:
    default_finding = next(item for item in _report().findings if item.rule_id == RULE_ID)
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    assert _report().status == "PASS"
    blocked = _report(policy=_review_policy("block"))
    finding = next(
        item for item in _report(policy=_review_policy()).findings if item.rule_id == RULE_ID
    )
    ignored = _report(
        policy=DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="test policy"),),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="reviewed separate interface channels",
                ),
            ),
        )
    )

    assert blocked.status == "FAIL"
    assert ignored.status == "PASS"


def _missing_function_case() -> NetlistContract:
    source = repeated_signal_pin_component()
    return source.model_copy(
        update={"pin_functions": {"U1.1": "READY", "U1.2": "READY", "U1.3": "STATUS"}}
    )


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(repeated_signal_pin_component(split=False), id="common-net-control"),
        pytest.param(repeated_signal_pin_component(dnp=True), id="dnp"),
        pytest.param(
            repeated_signal_pin_component(reference="J1", symbol="Connector_Generic:Conn_01x04"),
            id="connector-owned-by-connector-rules",
        ),
        pytest.param(
            _missing_function_case(),
            id="incomplete-native-pin-functions",
        ),
        pytest.param(
            repeated_signal_pin_component(
                functions={"U1.1": "Pin_1", "U1.2": "Pin_2", "U1.3": "STATUS", "U1.4": "Pin_4"}
            ),
            id="generic-functions",
        ),
        pytest.param(
            repeated_signal_pin_component(
                functions={"U1.1": "VCC", "U1.2": "VCC", "U1.3": "STATUS", "U1.4": "Pin_4"}
            ),
            id="supply-owned-by-power-rules",
        ),
        pytest.param(
            repeated_signal_pin_component(
                functions={"U1.1": "GND", "U1.2": "GND", "U1.3": "STATUS", "U1.4": "Pin_4"}
            ),
            id="return-owned-by-return-rules",
        ),
        pytest.param(
            repeated_signal_pin_component(
                functions={
                    "U1.1": "SHIELD",
                    "U1.2": "SHIELD",
                    "U1.3": "STATUS",
                    "U1.4": "Pin_4",
                }
            ),
            id="shield-owned-by-return-rules",
        ),
        pytest.param(
            repeated_signal_pin_component(
                electrical_types={
                    "U1.1": "input",
                    "U1.2": "output",
                    "U1.3": "input",
                    "U1.4": "passive",
                }
            ),
            id="different-electrical-types",
        ),
        pytest.param(
            repeated_signal_pin_component().model_copy(
                update={"nets": {"SIGNAL_A": ("U1.1",), "STATUS": ("U1.3",)}}
            ),
            id="open-member",
        ),
        pytest.param(
            repeated_signal_pin_component().model_copy(
                update={
                    "nets": {
                        "SIGNAL_A": ("U1.1", "U1.2"),
                        "SIGNAL_B": ("U1.2",),
                        "STATUS": ("U1.3",),
                    }
                }
            ),
            id="ambiguous-member",
        ),
    ],
)
def test_common_and_unsupported_shapes_stay_quiet(source: NetlistContract) -> None:
    report = _report(source, _review_policy())

    assert not any(item.rule_id == RULE_ID for item in report.findings)


def test_mapping_order_is_stable_and_commoning_clears_the_finding() -> None:
    source = repeated_signal_pin_component()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
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

    assert repeated.evidence == original.evidence
    assert repeated.fingerprint == original.fingerprint
    assert not any(
        item.rule_id == RULE_ID
        for item in _report(repeated_signal_pin_component(split=False), _review_policy()).findings
    )


def test_native_fixture_lane_enables_only_the_split_fault_and_checks_its_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_component_repeated_signal_pins_lane import (
        component_repeated_signal_pin_fixture_lane,
    )

    root = tmp_path.resolve()
    image = PINNED_NATIVE_KICAD_IMAGES["10.0.0"]
    config = SimpleNamespace(image=image, kicad_version="10.0.0")
    observed = {
        COMPONENT_REPEATED_SIGNAL_PIN_FAULT: repeated_signal_pin_component(),
        COMPONENT_REPEATED_SIGNAL_PIN_CONTROL: repeated_signal_pin_component(
            split=False
        ).model_copy(update={"nets": {"SIGNAL_A": ("U1.1", "U1.2"), "STATUS": ("U1.3",)}}),
    }

    def fake_run_command(
        command_root: Path, argv: tuple[str, ...], timeout: int
    ) -> CommandEvidence:
        assert command_root == root
        assert timeout == 600
        assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert image in argv
        mounts = tuple(argv[index + 1] for index, value in enumerate(argv[:-1]) if value == "-v")
        source_directory = Path(
            next(item for item in mounts if item.endswith(":/fixtures:ro")).removesuffix(
                ":/fixtures:ro"
            )
        )
        output_directory = Path(
            next(item for item in mounts if item.endswith(":/output:rw")).removesuffix(
                ":/output:rw"
            )
        )
        assert {item.name for item in source_directory.iterdir()} == {
            f"{case}.kicad_sch" for case in COMPONENT_REPEATED_SIGNAL_PIN_CASES
        }
        for case in COMPONENT_REPEATED_SIGNAL_PIN_CASES:
            for run in ("first", "repeat"):
                (output_directory / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} {run}\n", encoding="utf-8"
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-10-24T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    def fake_read_netlist(path: Path) -> NetlistContract:
        return observed[path.name.split(".", 1)[0]]

    monkeypatch.setattr(connector_return_context, "selected_config", lambda *_args: config)
    monkeypatch.setattr(connector_return_context, "run_command", fake_run_command)
    monkeypatch.setattr(connector_return_context, "read_netlist", fake_read_netlist)

    log = HostedLog(root, "component-repeated-signal-pin-unit")
    component_repeated_signal_pin_fixture_lane(root, project="synthetic", image=image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {item["stage"]: item for item in events}

    fault = results[f"component-repeated-signal-pin-fixture/{COMPONENT_REPEATED_SIGNAL_PIN_FAULT}"]
    control = results[
        f"component-repeated-signal-pin-fixture/{COMPONENT_REPEATED_SIGNAL_PIN_CONTROL}"
    ]
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == RULE_ID
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_COMPONENT_REPEATED_SIGNAL_PIN_FIXTURES") != "1",
    reason="native fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"), (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5"))
)
def test_native_repeated_signal_pin_fault_and_control_are_focused_and_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_component_repeated_signal_pins_lane import (
        component_repeated_signal_pin_fixture_lane,
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
    assert config.kicad_version == version
    assert config.image == image

    log = HostedLog(root, f"native-component-repeated-signal-pin-{project}")
    component_repeated_signal_pin_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("component-repeated-signal-pin-fixture/")
    }
    native_export = results["component-repeated-signal-pin-fixture/native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert (
        tuple(
            source_hash.split(":", 1)[0]
            for source_hash in native_export["source_hashes"].split(",")
        )
        == COMPONENT_REPEATED_SIGNAL_PIN_CASES
    )
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    fault = results[f"component-repeated-signal-pin-fixture/{COMPONENT_REPEATED_SIGNAL_PIN_FAULT}"]
    control = results[
        f"component-repeated-signal-pin-fixture/{COMPONENT_REPEATED_SIGNAL_PIN_CONTROL}"
    ]
    assert fault["status"] == control["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == RULE_ID
    assert fault["kicad_version"] == version
    assert fault["repeatable"] == "true"
    assert fault["normalized_netlist_sha256"] == fault["repeat_normalized_netlist_sha256"]
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    assert control["kicad_version"] == version
    assert control["repeatable"] == "true"
    assert control["normalized_netlist_sha256"] == control["repeat_normalized_netlist_sha256"]
