"""Fault, control, and boundary cases for open Ethernet data pairs."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_ethernet_unconnected_data import (
    ethernet_data_unconnected_pin_candidates,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_data_unconnected import (
    ethernet_data_unconnected_netlist,
)

RULE_ID = "bus.ethernet_data_unconnected_pin"
pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    ("open_pin", "expected"),
    (
        ("U1.1", "U1.1: TDP is open while TDN U1.2 is assigned to ETH_TX_N"),
        ("U1.2", "U1.2: TDN is open while TDP U1.1 is assigned to ETH_TX_P"),
        ("U1.3", "U1.3: RDP is open while RDN U1.4 is assigned to ETH_RX_N"),
        ("U1.4", "U1.4: RDN is open while RDP U1.3 is assigned to ETH_RX_P"),
    ),
)
def test_open_data_pair_pin_is_localized_beside_assigned_mate(open_pin: str, expected: str) -> None:
    findings = ethernet_data_unconnected_pin_candidates(
        ethernet_data_unconnected_netlist(open_pins=(open_pin,))
    )

    assert tuple(item.subject for item in findings) == (expected,)
    assert findings[0].rule_id == RULE_ID


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_both_open_and_fully_assigned_pairs_are_quiet() -> None:
    both_open = ethernet_data_unconnected_pin_candidates(
        ethernet_data_unconnected_netlist(open_pins=("U1.1", "U1.2"))
    )
    connected = ethernet_data_unconnected_pin_candidates(ethernet_data_unconnected_netlist())

    assert both_open == ()
    assert connected == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_incomplete_inventory_duplicate_roles_and_ambiguous_pin_are_skipped() -> None:
    fault = ethernet_data_unconnected_netlist(open_pins=("U1.1",))
    incomplete = fault.model_copy(update={"component_pin_numbers": {"U1": ("1", "2", "3")}})
    duplicate = fault.model_copy(update={"pin_functions": {**fault.pin_functions, "U1.5": "TDP"}})
    ambiguous = fault.model_copy(update={"nets": {**fault.nets, "AUX": ("U1.1",)}})

    assert (
        ethernet_data_unconnected_pin_candidates(
            ethernet_data_unconnected_netlist(open_pins=("U1.1",), dnp=True)
        )
        == ()
    )
    assert ethernet_data_unconnected_pin_candidates(incomplete) == ()
    assert ethernet_data_unconnected_pin_candidates(duplicate) == ()
    assert ethernet_data_unconnected_pin_candidates(ambiguous) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapping_order_is_stable_and_repair_clears_finding() -> None:
    fault = ethernet_data_unconnected_netlist(open_pins=("U1.1",))
    reordered = fault.model_copy(update={"nets": dict(reversed(tuple(fault.nets.items())))})
    repaired = fault.model_copy(update={"nets": {**fault.nets, "ETH_TX_P": ("U1.1",)}})

    assert ethernet_data_unconnected_pin_candidates(reordered) == (
        ethernet_data_unconnected_pin_candidates(fault)
    )
    assert ethernet_data_unconnected_pin_candidates(repaired) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_defaults_off_and_supports_review_block_and_exact_ignore() -> None:
    source = ethernet_data_unconnected_netlist(open_pins=("U1.1",))
    default = evaluate("synthetic-ethernet-data-open", coach(source), DesignLintPolicy())
    finding = next(item for item in default.findings if item.rule_id == RULE_ID)
    assert finding.mode == "off"
    generic_rule_id = "bus.complementary_pair_assignment"
    generic_finding = next(item for item in default.findings if item.rule_id == generic_rule_id)
    assert generic_finding.mode == "review"

    focused = evaluate(
        "synthetic-ethernet-data-open",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID, mode="review", reason="Use the focused Ethernet prompt"
                ),
            ),
            ignores=(
                DesignLintIgnore(
                    rule_id=generic_rule_id,
                    fingerprint=generic_finding.fingerprint,
                    reason="Use the pin-specific Ethernet review for this pair",
                ),
            ),
        ),
    )
    focused_finding = next(item for item in focused.findings if item.rule_id == RULE_ID)
    ignored_generic = next(item for item in focused.findings if item.rule_id == generic_rule_id)
    assert focused_finding.mode == "review"
    assert focused_finding.disposition == "OPEN"
    assert ignored_generic.mode == "review"
    assert ignored_generic.disposition == "IGNORED"

    reviewed = evaluate(
        "synthetic-ethernet-data-open",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="Inspect"),)
        ),
    )
    assert next(item for item in reviewed.findings if item.rule_id == RULE_ID).mode == "review"

    blocked = evaluate(
        "synthetic-ethernet-data-open",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Approved map"),)
        ),
    )
    assert blocked.status == "FAIL"

    ignored = evaluate(
        "synthetic-ethernet-data-open",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="Inspect"),),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Intentionally unused Ethernet lane",
                ),
            ),
        ),
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )
