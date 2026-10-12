"""Regressions for named power-input pins across connector symbol aliases."""

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

RULE_ID = "connector.peer_power_input_open_assignment"
ALL_OPEN_RULE_ID = "connector.peer_power_input_named_all_open"


def _report(
    source: NetlistContract,
    policy: DesignLintPolicy | None = None,
):
    return evaluate(
        "synthetic-connector-power-input-aliases",
        coach(source),
        policy or DesignLintPolicy(),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_named_power_input_on_one_connector_symbol_alias_is_reviewed() -> None:
    report = _report(_connector_alias_netlist())
    findings = [item for item in report.findings if item.rule_id == RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "PART_ID SYNTHETIC-NAMED-INPUT-001 pin 1 (BIAS_IN): "
        "named connector power-input peer assignment is open"
    )
    assert finding.evidence["J1.1"] == ("SYNTHETIC_BIAS",)
    assert finding.evidence["J2.1"] == ()
    assert finding.evidence["peer_identity_basis"] == ("part_id",)
    assert finding.evidence["peer_symbols"] == ("Synthetic:PortA", "Synthetic:PortB")
    assert finding.evidence["assigned_peer_pins"] == ("J1.1",)
    assert finding.evidence["open_peer_pins"] == ("J2.1",)
    assert "do not establish" in finding.message
    assert "connector.repeated_pin_function" not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_common_and_all_open_named_power_input_aliases_are_controls() -> None:
    common = _report(_connector_alias_netlist(assignments=("SYNTHETIC_BIAS", "SYNTHETIC_BIAS")))
    all_open = _report(_connector_alias_netlist(assignments=(None, None)))

    assert RULE_ID not in {item.rule_id for item in common.findings}
    assert RULE_ID not in {item.rule_id for item in all_open.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_input_alias_rule_requires_guarded_identity_and_eligible_metadata() -> None:
    controls = (
        _connector_alias_netlist(symbols=("Synthetic:PortA", "Synthetic:PortA")),
        _connector_alias_netlist(part_ids=("SYNTHETIC-A", "SYNTHETIC-B")),
        _connector_alias_netlist(part_ids=(None, None)),
        _connector_alias_netlist(values=("Synthetic peer", "Different peer")),
        _connector_alias_netlist(footprints=("Synthetic:2Pin", "Synthetic:Other")),
        _connector_alias_netlist(inventories=(("1", "2"), ("1",))),
        _connector_alias_netlist(target_functions=("BIAS_IN", "BIAS_OUT")),
        _connector_alias_netlist(target_types=("power_in", "input")),
        _connector_alias_netlist(target_functions=("Pin_1", "Pin_1")),
        _connector_alias_netlist(target_functions=("VDD", "VDD")),
        _connector_alias_netlist(target_functions=("GND", "GND")),
        _connector_alias_netlist(dnp=("J2",)),
    )
    for source in controls:
        report = _report(source)
        assert RULE_ID not in {item.rule_id for item in report.findings}

    ambiguous = _connector_alias_netlist()
    ambiguous_nets = dict(ambiguous.nets)
    ambiguous_nets["SYNTHETIC_OTHER"] = ("J1.1",)
    ambiguous_report = _report(ambiguous.model_copy(update={"nets": ambiguous_nets}))
    assert RULE_ID not in {item.rule_id for item in ambiguous_report.findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_input_alias_rule_is_stable_under_mapping_order() -> None:
    source = _connector_alias_netlist()
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
def test_named_power_input_alias_rule_obeys_policy_and_exact_ignore() -> None:
    source = _connector_alias_netlist()
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic contract requires an explicit pin disposition",
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
                    reason="Synthetic review accepts an optional connector contact",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(
        item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings
    )
    changed = _report(_connector_alias_netlist(assignments=("SYNTHETIC_BIAS_ALT", None)))
    changed_finding = next(item for item in changed.findings if item.rule_id == RULE_ID)
    assert changed_finding.fingerprint != finding.fingerprint


@pytest.mark.design_lint_rule(rule_id=ALL_OPEN_RULE_ID)
def test_named_power_input_open_on_every_connector_alias_is_reviewed() -> None:
    report = _report(_connector_alias_netlist(assignments=(None, None)))
    findings = [item for item in report.findings if item.rule_id == ALL_OPEN_RULE_ID]

    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert finding.subject == (
        "PART_ID SYNTHETIC-NAMED-INPUT-001 pin 1 (BIAS_IN): "
        "named connector power-input peer pin is open everywhere"
    )
    assert finding.evidence["J1.1"] == ()
    assert finding.evidence["J2.1"] == ()
    assert finding.evidence["peer_identity_basis"] == ("part_id",)
    assert finding.evidence["peer_symbols"] == ("Synthetic:PortA", "Synthetic:PortB")
    assert RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=ALL_OPEN_RULE_ID)
def test_named_power_input_alias_all_open_rule_keeps_assignment_controls_quiet() -> None:
    controls = (
        _connector_alias_netlist(assignments=("SYNTHETIC_BIAS", "SYNTHETIC_BIAS")),
        _connector_alias_netlist(assignments=("SYNTHETIC_BIAS", None)),
        _connector_alias_netlist(symbols=("Synthetic:PortA", "Synthetic:PortA")),
        _connector_alias_netlist(part_ids=(None, None)),
        _connector_alias_netlist(values=("Synthetic peer", "Different peer")),
        _connector_alias_netlist(footprints=("Synthetic:2Pin", "Synthetic:Other")),
        _connector_alias_netlist(inventories=(("1", "2"), ("1",))),
        _connector_alias_netlist(target_functions=("BIAS_IN", "BIAS_OUT")),
        _connector_alias_netlist(target_types=("power_in", "input")),
        _connector_alias_netlist(target_functions=("Pin_1", "Pin_1")),
        _connector_alias_netlist(target_functions=("VDD", "VDD")),
        _connector_alias_netlist(target_functions=("GND", "GND")),
        _connector_alias_netlist(assignments=(None, None), dnp=("J2",)),
    )
    for source in controls:
        report = _report(source)
        assert ALL_OPEN_RULE_ID not in {item.rule_id for item in report.findings}

    ambiguous = _connector_alias_netlist(assignments=(None, None))
    ambiguous_nets = dict(ambiguous.nets)
    ambiguous_nets["SYNTHETIC_OTHER"] = ("J1.1",)
    report = _report(ambiguous.model_copy(update={"nets": ambiguous_nets}))
    assert ALL_OPEN_RULE_ID not in {item.rule_id for item in report.findings}


@pytest.mark.design_lint_rule(rule_id=ALL_OPEN_RULE_ID)
def test_named_power_input_alias_all_open_rule_is_stable_under_mapping_order() -> None:
    source = _connector_alias_netlist(assignments=(None, None))
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
    first = next(item for item in _report(source).findings if item.rule_id == ALL_OPEN_RULE_ID)
    second = next(item for item in _report(reordered).findings if item.rule_id == ALL_OPEN_RULE_ID)

    assert first.subject == second.subject
    assert first.evidence == second.evidence
    assert first.fingerprint == second.fingerprint


@pytest.mark.design_lint_rule(rule_id=ALL_OPEN_RULE_ID)
def test_named_power_input_alias_all_open_rule_obeys_policy_and_exact_ignore() -> None:
    source = _connector_alias_netlist(assignments=(None, None))
    finding = next(item for item in _report(source).findings if item.rule_id == ALL_OPEN_RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=ALL_OPEN_RULE_ID,
                    mode="block",
                    reason="Synthetic contract requires an explicit pin disposition",
                ),
            )
        ),
    )
    ignored = _report(
        source,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=ALL_OPEN_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic review accepts optional connector contacts",
                ),
            )
        ),
    )
    changed = _report(
        _connector_alias_netlist(
            assignments=(None, None),
            part_ids=("SYNTHETIC-NAMED-INPUT-002", "SYNTHETIC-NAMED-INPUT-002"),
        )
    )
    changed_finding = next(item for item in changed.findings if item.rule_id == ALL_OPEN_RULE_ID)

    assert blocked.status == "FAIL"
    assert any(
        item.rule_id == ALL_OPEN_RULE_ID and item.disposition == "IGNORED"
        for item in ignored.findings
    )
    assert changed_finding.fingerprint != finding.fingerprint
