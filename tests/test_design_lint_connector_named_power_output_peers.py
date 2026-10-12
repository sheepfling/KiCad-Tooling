"""Regressions for named power-output contacts across connector aliases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.connector_named_power_aliases import (
    named_connector_power_alias_netlist as _connector_alias_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.peer_power_output_open_assignment"


def _report(source: NetlistContract, policy: DesignLintPolicy | None = None):
    return evaluate(
        "synthetic-connector-power-output-aliases",
        coach(source),
        policy or DesignLintPolicy(),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_named_power_output_on_one_connector_symbol_alias_is_reviewed() -> None:
    report = _report(
        _connector_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
        )
    )
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "PART_ID SYNTHETIC-NAMED-INPUT-001 pin 1 (BIAS_OUT): "
        "named connector power-output peer assignment is open"
    )
    assert finding.evidence["J1.1"] == ("SYNTHETIC_BIAS",)
    assert finding.evidence["J2.1"] == ()
    assert finding.evidence["peer_identity_basis"] == ("part_id",)
    assert finding.evidence["peer_symbols"] == ("Synthetic:PortA", "Synthetic:PortB")
    assert finding.evidence["assigned_peer_pins"] == ("J1.1",)
    assert finding.evidence["open_peer_pins"] == ("J2.1",)
    assert "do not establish" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_all_open_and_split_assigned_output_aliases_are_controls() -> None:
    cases = (
        _connector_alias_netlist(
            assignments=("SYNTHETIC_BIAS", "SYNTHETIC_BIAS"),
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
        ),
        _connector_alias_netlist(
            assignments=(None, None),
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
        ),
        _connector_alias_netlist(
            assignments=("SYNTHETIC_A", "SYNTHETIC_B"),
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
        ),
    )
    for source in cases:
        report = _report(source)
        assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_output_alias_rule_requires_guarded_identity_and_metadata() -> None:
    controls = (
        _connector_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
            symbols=("Synthetic:PortA", "Synthetic:PortA"),
        ),
        _connector_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
            part_ids=("SYNTHETIC-A", "SYNTHETIC-B"),
        ),
        _connector_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
            part_ids=(None, None),
        ),
        _connector_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
            values=("Synthetic peer", "Different peer"),
        ),
        _connector_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
            footprints=("Synthetic:2Pin", "Synthetic:Other"),
        ),
        _connector_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
            inventories=(("1", "2"), ("1",)),
        ),
        _connector_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_IN"),
            target_types=("power_out", "power_out"),
        ),
        _connector_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "input"),
        ),
        _connector_alias_netlist(
            target_functions=("Pin_1", "Pin_1"),
            target_types=("power_out", "power_out"),
        ),
        _connector_alias_netlist(
            target_functions=("VDD", "VDD"),
            target_types=("power_out", "power_out"),
        ),
        _connector_alias_netlist(
            target_functions=("GND", "GND"),
            target_types=("power_out", "power_out"),
        ),
        _connector_alias_netlist(
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
            dnp=("J2",),
        ),
    )
    for source in controls:
        report = _report(source)
        assert RULE_ID not in {item.rule_id for item in report.findings}

    ambiguous = _connector_alias_netlist(
        target_functions=("BIAS_OUT", "BIAS_OUT"),
        target_types=("power_out", "power_out"),
    )
    ambiguous_nets = dict(ambiguous.nets)
    ambiguous_nets["SYNTHETIC_OTHER"] = ("J1.1",)
    report = _report(ambiguous.model_copy(update={"nets": ambiguous_nets}))
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_output_alias_finding_is_stable_under_mapping_order() -> None:
    source = _connector_alias_netlist(
        target_functions=("BIAS_OUT", "BIAS_OUT"),
        target_types=("power_out", "power_out"),
    )
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    first = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    second = next(item for item in _report(reordered).findings if item.rule_id == RULE_ID)

    assert first.subject == second.subject
    assert first.evidence == second.evidence
    assert first.fingerprint == second.fingerprint


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_output_alias_rule_obeys_policy_and_exact_ignore() -> None:
    source = _connector_alias_netlist(
        target_functions=("BIAS_OUT", "BIAS_OUT"),
        target_types=("power_out", "power_out"),
    )
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic contract requires an explicit output-pin disposition",
                ),
            )
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic review accepts an optional output contact",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(
        item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings
    )
    changed = _report(
        _connector_alias_netlist(
            assignments=("SYNTHETIC_BIAS_ALT", None),
            target_functions=("BIAS_OUT", "BIAS_OUT"),
            target_types=("power_out", "power_out"),
        )
    )
    changed_finding = next(item for item in changed.findings if item.rule_id == RULE_ID)
    assert changed_finding.fingerprint != finding.fingerprint
