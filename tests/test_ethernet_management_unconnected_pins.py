"""Fault, control, policy, and stability tests for open Ethernet MDC/MDIO pairs."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_management_labels import ethernet_management_netlist

RULE_ID = "bus.ethernet_management_unconnected_pin"
pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _findings(netlist: NetlistContract):
    return tuple(item for item in candidates(netlist) if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_management_member_is_localized_beside_its_assigned_peer() -> None:
    clock_open = _findings(ethernet_management_netlist(open_functions=("MDC",)))
    data_open = _findings(ethernet_management_netlist(open_functions=("MDIO",)))

    assert tuple(item.subject for item in clock_open) == (
        "U1.5: MDC is open while MDIO U1.6 is assigned to ETH_MDIO",
    )
    assert tuple(item.evidence["ethernet_management_role"] for item in clock_open) == (("clock",),)
    assert tuple(item.subject for item in data_open) == (
        "U1.6: MDIO is open while MDC U1.5 is assigned to ETH_MDC",
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_both_open_and_fully_assigned_management_pairs_are_quiet() -> None:
    assert not _findings(ethernet_management_netlist(open_functions=("MDC", "MDIO")))
    assert not _findings(ethernet_management_netlist())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_duplicate_roles_incomplete_inventory_and_ambiguous_pins_are_skipped() -> None:
    fault = ethernet_management_netlist(open_functions=("MDC",))
    incomplete = fault.model_copy(update={"component_pin_numbers": {"U1": ("5", "6", "7")}})
    duplicate_role = ethernet_management_netlist(functions=("MDC", "MDC"), open_functions=("MDC",))
    ambiguous = fault.model_copy(update={"nets": {"ETH_MDIO": ("U1.6",), "AUX": ("U1.5",)}})

    assert not _findings(ethernet_management_netlist(open_functions=("MDC",), dnp=True))
    assert not _findings(incomplete)
    assert not _findings(duplicate_role)
    assert not _findings(ambiguous)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_only_integrated_circuit_references_and_exact_management_functions_are_classified() -> None:
    connector = ethernet_management_netlist(open_functions=("MDC",)).model_copy(
        update={
            "components": {"J1": ethernet_management_netlist().components["U1"]},
            "nets": {"ETH_MDIO": ("J1.6",)},
            "pin_functions": {"J1.5": "MDC", "J1.6": "MDIO"},
            "component_pin_numbers": {"J1": ("5", "6")},
        }
    )
    unsupported = ethernet_management_netlist(
        functions=("MDC/MDIO", "MDIO"), open_functions=("MDC/MDIO",)
    )

    assert not _findings(connector)
    assert not _findings(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rule_defaults_off_and_supports_review_block_and_exact_ignore() -> None:
    source = ethernet_management_netlist(open_functions=("MDC",))
    default = evaluate("synthetic-ethernet-management-open", coach(source), DesignLintPolicy())
    finding = next(item for item in default.findings if item.rule_id == RULE_ID)
    assert finding.mode == "off"
    assert default.status == "PASS"

    reviewed = evaluate(
        "synthetic-ethernet-management-open",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="Inspect"),)
        ),
    )
    assert next(item for item in reviewed.findings if item.rule_id == RULE_ID).mode == "review"

    blocked = evaluate(
        "synthetic-ethernet-management-open",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Approved map"),)
        ),
    )
    assert blocked.status == "FAIL"

    ignored = evaluate(
        "synthetic-ethernet-management-open",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="review", reason="Inspect"),),
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Intentionally unused management interface",
                ),
            ),
        ),
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapping_order_is_stable_and_assigning_the_open_pin_clears_the_candidate() -> None:
    fault = ethernet_management_netlist(open_functions=("MDC",))
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    repaired = fault.model_copy(update={"nets": {"ETH_MDIO": ("U1.6",), "ETH_MDC": ("U1.5",)}})

    assert _findings(reordered) == _findings(fault)
    assert not _findings(repaired)
