"""Regressions for named power-input assignments across connector aliases."""

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
    named_connector_power_alias_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.peer_power_input_named_assignment_divergence"


def _report(source: NetlistContract, policy: DesignLintPolicy | None = None):
    return evaluate(
        "synthetic-connector-named-power-input-divergence",
        coach(source),
        policy or DesignLintPolicy(),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_input_aliases_on_distinct_nets_are_reviewed() -> None:
    source = named_connector_power_alias_netlist(
        assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"),
        part_ids=("SYNTHETIC-NAMED-INPUT-001", "SYNTHETIC-NAMED-INPUT-001"),
        target_functions=("BIAS_IN", "BIAS_IN"),
        target_types=("power_in", "power_in"),
    )

    report = _report(source)
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)

    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].evidence["J1.1"] == ("SYNTHETIC_RAIL_A",)
    assert findings[0].evidence["J2.1"] == ("SYNTHETIC_RAIL_B",)
    assert findings[0].evidence["distinct_net_assignments"] == (
        "J1.1=SYNTHETIC_RAIL_A",
        "J2.1=SYNTHETIC_RAIL_B",
    )
    assert "do not establish" in findings[0].message
    assert not {
        "connector.peer_power_input_open_assignment",
        "connector.peer_power_input_named_all_open",
    }.intersection(item.rule_id for item in report.findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_input_divergence_ignores_common_open_mixed_and_ambiguous_groups() -> None:
    common = named_connector_power_alias_netlist(
        assignments=("SYNTHETIC_RAIL", "SYNTHETIC_RAIL"),
        part_ids=("SYNTHETIC-NAMED-INPUT-001", "SYNTHETIC-NAMED-INPUT-001"),
        target_functions=("BIAS_IN", "BIAS_IN"),
        target_types=("power_in", "power_in"),
    )
    mixed = named_connector_power_alias_netlist(
        assignments=("SYNTHETIC_RAIL_A", None),
        part_ids=("SYNTHETIC-NAMED-INPUT-001", "SYNTHETIC-NAMED-INPUT-001"),
        target_functions=("BIAS_IN", "BIAS_IN"),
        target_types=("power_in", "power_in"),
    )
    all_open = named_connector_power_alias_netlist(
        assignments=(None, None),
        part_ids=("SYNTHETIC-NAMED-INPUT-001", "SYNTHETIC-NAMED-INPUT-001"),
        target_functions=("BIAS_IN", "BIAS_IN"),
        target_types=("power_in", "power_in"),
    )
    ambiguous = named_connector_power_alias_netlist(
        assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"),
        part_ids=("SYNTHETIC-NAMED-INPUT-001", "SYNTHETIC-NAMED-INPUT-001"),
        target_functions=("BIAS_IN", "BIAS_IN"),
        target_types=("power_in", "power_in"),
    )
    ambiguous_nets = dict(ambiguous.nets)
    ambiguous_nets["SYNTHETIC_OTHER"] = ("J1.1",)
    ambiguous = ambiguous.model_copy(update={"nets": ambiguous_nets})

    for source in (common, mixed, all_open, ambiguous):
        assert RULE_ID not in {item.rule_id for item in _report(source).findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_input_divergence_requires_guarded_alias_identity_and_metadata() -> None:
    controls = (
        {"symbols": ("Synthetic:PortA", "Synthetic:PortA")},
        {"part_ids": ("SYNTHETIC-A", "SYNTHETIC-B")},
        {"part_ids": (None, None)},
        {"values": ("Synthetic peer", "Different peer")},
        {"footprints": ("Synthetic:2Pin", "Synthetic:Other")},
        {"inventories": (("1", "2"), ("1",))},
        {"target_functions": ("BIAS_IN", "BIAS_OUT")},
        {"target_types": ("power_in", "input")},
        {"target_functions": ("Pin_1", "Pin_1")},
        {"target_functions": ("VDD", "VDD")},
        {"target_functions": ("GND", "GND")},
        {"dnp": ("J2",)},
    )
    for changes in controls:
        arguments = {
            "assignments": ("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"),
            "part_ids": ("SYNTHETIC-NAMED-INPUT-001", "SYNTHETIC-NAMED-INPUT-001"),
            "target_functions": ("BIAS_IN", "BIAS_IN"),
            "target_types": ("power_in", "power_in"),
        }
        source = named_connector_power_alias_netlist(**(arguments | changes))
        assert RULE_ID not in {item.rule_id for item in _report(source).findings}


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_power_input_divergence_is_stable_under_mapping_order() -> None:
    source = named_connector_power_alias_netlist(
        assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"),
        part_ids=("SYNTHETIC-NAMED-INPUT-001", "SYNTHETIC-NAMED-INPUT-001"),
        target_functions=("BIAS_IN", "BIAS_IN"),
        target_types=("power_in", "power_in"),
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
def test_named_power_input_divergence_obeys_policy_and_exact_ignore() -> None:
    source = named_connector_power_alias_netlist(
        assignments=("SYNTHETIC_RAIL_A", "SYNTHETIC_RAIL_B"),
        part_ids=("SYNTHETIC-NAMED-INPUT-001", "SYNTHETIC-NAMED-INPUT-001"),
        target_functions=("BIAS_IN", "BIAS_IN"),
        target_types=("power_in", "power_in"),
    )
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    blocked = _report(
        source,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic review requires an explicit input pin disposition",
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
                    reason="Synthetic review accepts separate input rails",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
    assert any(
        item.rule_id == RULE_ID and item.disposition == "IGNORED" for item in ignored.findings
    )
