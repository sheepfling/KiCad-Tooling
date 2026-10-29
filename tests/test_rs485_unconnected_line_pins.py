"""Focused fault, control, policy, and stability tests for open RS-485 A/B pins."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintIgnore, DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.rs485_unconnected_line_pin import (
    RULE_ID,
    rs485_unconnected_line_pin_candidates,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_unconnected_line_pin import (
    rs485_unconnected_line_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _findings(source: NetlistContract):
    return tuple(item for item in candidates(source) if item.rule_id == RULE_ID)


def _report(
    source: NetlistContract,
    *,
    mode: str | None = None,
    ignore: DesignLintIgnore | None = None,
):
    overrides = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Reviewed test policy"),)
    )
    policy = DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,))
    return evaluate("synthetic-rs485-unconnected-line", coach(source), policy)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("open_role", ("a", "b"))
def test_one_open_line_is_localized_with_its_assigned_pair_member(open_role: str) -> None:
    source = rs485_unconnected_line_netlist(open_role=open_role)
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    pin_number = "1" if open_role == "a" else "2"
    paired_number = "2" if open_role == "a" else "1"

    assert len(_findings(source)) == 1
    assert finding.subject == (
        f"U1.{pin_number}: RS-485 {open_role.upper()} bus-line function is open"
    )
    assert finding.evidence["paired_pin"] == (f"U1.{paired_number}",)
    assert finding.evidence["paired_net"] == (f"RS485_{'B' if open_role == 'a' else 'A'}",)
    assert "do not establish interface use or PCB routing" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_complete_pair_and_unsupported_identity_shapes_are_quiet() -> None:
    controls = (
        rs485_unconnected_line_netlist(open_role=None),
        rs485_unconnected_line_netlist(identity="Generic interface", symbol="Logic:Device"),
        rs485_unconnected_line_netlist(identity="SN65HVD230", symbol="Vendor:Transceiver"),
        rs485_unconnected_line_netlist(dnp=True),
        rs485_unconnected_line_netlist(reference="J1"),
    )
    assert all(not _findings(source) for source in controls)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_duplicate_and_ambiguous_pair_evidence_is_skipped() -> None:
    source = rs485_unconnected_line_netlist()
    cases = (
        source.model_copy(
            update={"nets": {}, "unconnected_nets": {"unconnected": ("U1.1", "U1.2")}}
        ),
        source.model_copy(update={"component_pin_numbers": {}}),
        source.model_copy(update={"component_pin_numbers": {"U1": ("1",)}}),
        source.model_copy(update={"pin_functions": {"U1.1": "A", "U1.2": "A"}}),
        source.model_copy(update={"pin_functions": {"U1.1": "A+", "U1.2": "B"}}),
        source.model_copy(update={"nets": {"RS485_B": ("U1.2",), "AUX": ("U1.2",)}}),
    )
    assert all(not _findings(case) for case in cases)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_default_review_policy_can_block_disable_and_ignore_exact_candidate() -> None:
    source = rs485_unconnected_line_netlist()
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)
    assert _report(source).findings[0].mode == "review"
    assert finding.disposition == "OPEN"
    assert _report(source, mode="review").status == "REVIEW"
    assert _report(source, mode="block").status == "FAIL"
    assert _report(source, mode="off").status == "PASS"
    ignored = _report(
        source,
        mode="review",
        ignore=DesignLintIgnore(
            rule_id=RULE_ID, fingerprint=finding.fingerprint, reason="Reviewed partial interface"
        ),
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapping_order_is_stable_and_assignment_repair_clears_candidate() -> None:
    source = rs485_unconnected_line_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
        }
    )
    repaired = rs485_unconnected_line_netlist(open_role=None)

    assert _findings(reordered) == _findings(source)
    assert not _findings(repaired)
    assert rs485_unconnected_line_pin_candidates(source) == _findings(source)
