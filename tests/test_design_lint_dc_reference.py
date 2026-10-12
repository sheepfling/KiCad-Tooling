"""Focused synthetic regressions for the dc reference lint theme."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import (
    candidates,
    evaluate,
    fingerprint,
)
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures import (
    coach,
    connector_capacitor_only_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]


def test_connector_capacitor_only_net_requests_dc_reference_review() -> None:
    source = connector_capacitor_only_netlist()
    candidates_for_net = [
        item
        for item in candidates(source)
        if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
    ]
    assert len(candidates_for_net) == 1
    candidate = candidates_for_net[0]
    assert candidate.subject == "ANALOG_IN: connector/capacitor-only net"
    assert candidate.evidence["connector_pins"] == ("J1.1",)
    assert candidate.evidence["capacitor_pins"] == ("C1.1",)
    assert "off-board source" in candidate.message
    assert "does not trace a complete DC path" in candidate.message

    report = evaluate("synthetic-dc-reference", coach(source), DesignLintPolicy())
    finding = next(
        item
        for item in report.findings
        if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
    )
    assert report.status == "REVIEW"
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(connector_capacitor_only_netlist(dnp=("C1",)), id="dnp-capacitor"),
        pytest.param(connector_capacitor_only_netlist(dnp=("J1",)), id="dnp-connector"),
        pytest.param(
            connector_capacitor_only_netlist(extra_signal_pin=True), id="extra-signal-pin"
        ),
        pytest.param(
            connector_capacitor_only_netlist().model_copy(
                update={"component_symbols": {"J1": "Device:R", "C1": "Device:C"}}
            ),
            id="unsupported-peer-symbols",
        ),
        pytest.param(
            connector_capacitor_only_netlist().model_copy(
                update={"nets": {"ANALOG_IN": ("C1.1",), "GND": ("C1.2",)}}
            ),
            id="no-connector-pin",
        ),
        pytest.param(
            connector_capacitor_only_netlist().model_copy(
                update={
                    "nets": {
                        "ANALOG_IN": ("J1.1", "C1.1"),
                        "GND": ("J1.2", "C1.2"),
                    },
                    "pin_functions": {"J1.1": "GND"},
                }
            ),
            id="return-labeled-connector-pin",
        ),
    ),
)
def test_connector_capacitor_only_prompt_requires_fitted_known_peer_pins(
    source,
) -> None:
    assert not any(
        item.rule_id == "net.connector_capacitor_only_no_dc_anchor" for item in candidates(source)
    )


def test_connector_capacitor_only_prompt_supports_project_policy_and_ignore() -> None:
    source = connector_capacitor_only_netlist()
    initial = evaluate("synthetic-dc-reference-policy", coach(source), DesignLintPolicy())
    finding = next(
        item
        for item in initial.findings
        if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
    )
    blocked = evaluate(
        "synthetic-dc-reference-policy",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="net.connector_capacitor_only_no_dc_anchor",
                    mode="block",
                    reason="Synthetic project requires local DC-reference review",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-dc-reference-policy",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="net.connector_capacitor_only_no_dc_anchor",
                    mode="off",
                    reason="Synthetic interface is biased by its external source",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    assert (
        next(
            item
            for item in disabled.findings
            if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
        ).disposition
        == "RULE_OFF"
    )

    ignored_policy = DesignLintPolicy(
        ignores=(
            DesignLintIgnore(
                rule_id="net.connector_capacitor_only_no_dc_anchor",
                fingerprint=finding.fingerprint,
                reason="Synthetic project records the external DC source",
            ),
        )
    )
    ignored = evaluate("synthetic-dc-reference-policy", coach(source), ignored_policy)
    assert ignored.status == "PASS"
    assert (
        next(
            item
            for item in ignored.findings
            if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
        ).disposition
        == "IGNORED"
    )


def test_connector_capacitor_only_finding_is_order_stable_and_extra_pin_clears_it() -> None:
    source = connector_capacitor_only_netlist()
    original = next(
        item
        for item in candidates(source)
        if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
    )
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
        }
    )
    repeated = next(
        item
        for item in candidates(reordered)
        if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
    )
    assert fingerprint(original) == fingerprint(repeated)

    expanded = connector_capacitor_only_netlist(extra_signal_pin=True)
    assert "net.connector_capacitor_only_no_dc_anchor" not in {
        item.rule_id for item in candidates(expanded)
    }
