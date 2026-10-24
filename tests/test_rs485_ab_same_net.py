"""Focused regressions for RS-485 A/B bus pins assigned to one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.rs485_ab_same_net import RULE_ID, rs485_ab_same_net_candidates
from kicad_tooling.hwrepo.rs485_line_functions import rs485_bus_line_role
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_ab_same_net import rs485_ab_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _report(
    source: NetlistContract,
    *,
    mode: str | None = None,
    ignore: DesignLintIgnore | None = None,
):
    overrides = ()
    if mode is not None:
        overrides = (
            DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Reviewed test policy"),
        )
    policy = DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,))
    return evaluate("synthetic-rs485-ab-same-net", coach(source), policy)


def _findings(source: NetlistContract):
    return tuple(item for item in _report(source).findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_explicit_rs485_a_b_pins_on_one_net_request_review() -> None:
    source = rs485_ab_same_net_netlist()
    findings = _findings(source)

    assert len(findings) == 1
    assert findings[0].subject == "U1: RS-485 A/B bus pins share AB_SHARED"
    assert findings[0].mode == "review"
    assert findings[0].evidence == {
        "component": ("U1",),
        "A_pin": ("U1.1",),
        "A_function": ("A",),
        "B_pin": ("U1.2",),
        "B_function": ("B",),
        "net": ("AB_SHARED",),
        "identity_basis": ("Synthetic:Rs485Transceiver RS-485 transceiver",),
    }
    assert _report(source).status == "REVIEW"
    assert "does not establish the exact part pinout" in findings[0].message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_distinct_lines_and_unrelated_a_b_functions_are_valid_controls() -> None:
    separated = rs485_ab_same_net_netlist(shared=False)
    generic_ic = rs485_ab_same_net_netlist(identity="Generic logic IC", symbol="Logic:Device")
    can_ic = rs485_ab_same_net_netlist(identity="SN65HVD230", symbol="Vendor:Transceiver")
    assert not _findings(separated)
    assert not _findings(generic_ic)
    assert not _findings(can_ic)
    assert rs485_bus_line_role("a") == "a"
    assert rs485_bus_line_role("B") == "b"
    assert rs485_bus_line_role("A+") is None
    assert rs485_bus_line_role("CANH") is None


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_duplicate_ambiguous_and_incomplete_evidence_is_skipped() -> None:
    source = rs485_ab_same_net_netlist()
    unsupported = (
        rs485_ab_same_net_netlist(dnp=True),
        source.model_copy(update={"nets": {"AB_SHARED": ("U1.1",)}}),
        source.model_copy(update={"nets": {**source.nets, "OTHER": ("U1.1",)}}),
        source.model_copy(update={"component_pin_numbers": {}}),
        source.model_copy(update={"component_pin_numbers": {"U1": ("1",)}}),
        source.model_copy(
            update={
                "pin_functions": {**source.pin_functions, "U1.3": "A"},
                "component_pin_numbers": {"U1": ("1", "2", "3")},
                "nets": {"AB_SHARED": ("U1.1", "U1.2", "U1.3")},
            }
        ),
        source.model_copy(update={"pin_functions": {"U1.1": "A", "U1.2": "A"}}),
    )
    for case in unsupported:
        assert not rs485_ab_same_net_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connectors_and_two_output_pairs_are_left_outside_the_heuristic() -> None:
    source = rs485_ab_same_net_netlist()
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "nets": {"AB_SHARED": ("J1.1", "J1.2")},
            "dnp_components": (),
            "component_symbols": {"J1": "Synthetic:Rs485Transceiver"},
            "pin_functions": {"J1.1": "A", "J1.2": "B"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )
    two_outputs = rs485_ab_same_net_netlist(pin_types=("output", "output"))
    assert not _findings(connector)
    assert not _findings(two_outputs)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_a_shared_pair() -> None:
    source = rs485_ab_same_net_netlist()
    initial = _findings(source)[0]
    blocked = _report(source, mode="block")
    disabled = _report(source, mode="off")
    ignored = _report(
        source,
        ignore=DesignLintIgnore(
            rule_id=RULE_ID,
            fingerprint=initial.fingerprint,
            reason="Intentional A/B strap for this reviewed interface mode",
        ),
    )

    assert blocked.status == "FAIL"
    assert (
        next(item for item in disabled.findings if item.rule_id == RULE_ID).disposition
        == "RULE_OFF"
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordering_is_stable_and_splitting_the_pair_clears_review() -> None:
    source = rs485_ab_same_net_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    repaired = rs485_ab_same_net_netlist(shared=False)

    assert tuple(item.model_dump() for item in _findings(source)) == tuple(
        item.model_dump() for item in _findings(reordered)
    )
    assert not _findings(repaired)
