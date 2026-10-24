"""Focused regressions for repeated signal-function assignments on one IC."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.repeated_signal_pin_functions import repeated_signal_pin_component

RULE_ID = "component.repeated_signal_pin_assignment_divergence"

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
