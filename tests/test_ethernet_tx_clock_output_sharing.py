"""Regressions for shared Ethernet PHY MII transmit-clock review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.ethernet_tx_clock_output_sharing import (
    ethernet_phy_tx_clock_output_role,
    ethernet_tx_clock_output_sharing_candidates,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_tx_clock_output_sharing import (
    ethernet_mii_tx_clock_output_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.ethernet_tx_clock_outputs_share_net"
SHARED_NET = "MII_TX_CLK_SHARED"


def _source(
    *,
    shared: bool = True,
    functions: tuple[str, ...] = ("TX_CLK", "TX_CLK"),
    references: tuple[str, ...] = ("U1", "U2"),
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    return ethernet_mii_tx_clock_output_netlist(
        shared=shared,
        references=references,
        functions=functions,
        dnp_references=dnp_references,
    )


def _report(
    netlist: NetlistContract,
    mode: str | None = None,
    *,
    ignore: DesignLintIgnore | None = None,
):
    overrides = (
        ()
        if mode is None
        else (
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic Ethernet PHY transmit-clock sharing",
            ),
        )
    )
    policy = DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,))
    return evaluate("synthetic-ethernet-mii-tx-clock-sharing", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_shared_mii_tx_clock_from_fitted_identified_phys_is_reviewed() -> None:
    finding = _findings(_report(_source()))[0]

    assert finding.mode == "review"
    assert finding.subject == f"U1, U2: Ethernet PHY TX_CLK outputs share {SHARED_NET}"
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "channels": ("ethernet-mii-transmit-clock",) * 2,
        "functions": ("TX_CLK", "TX_CLK"),
        "pins": ("U1.1", "U2.1"),
        "pin_types": ("passive", "passive"),
        "net": (SHARED_NET,),
        "identity_basis": ("Synthetic:Ethernet_PHY DP83848 Ethernet PHY",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_mii_aliases_and_separate_or_other_clock_controls() -> None:
    assert ethernet_phy_tx_clock_output_role("U1", "MII_TX_CLK") == (
        "tx",
        "ethernet-mii-transmit-clock",
    )
    assert ethernet_phy_tx_clock_output_role("U1", "MII-TX CLK") == (
        "tx",
        "ethernet-mii-transmit-clock",
    )
    assert ethernet_phy_tx_clock_output_role("U1", "GTX_CLK") is None
    assert ethernet_phy_tx_clock_output_role("U1", "GMII_TX_CLK") is None
    assert ethernet_phy_tx_clock_output_role("U1", "TX_CLK/PHYAD0") is None
    assert (
        len(
            ethernet_tx_clock_output_sharing_candidates(_source(functions=("MII_TX_CLK", "TX_CLK")))
        )
        == 1
    )
    assert not ethernet_tx_clock_output_sharing_candidates(_source(shared=False))
    assert not ethernet_tx_clock_output_sharing_candidates(_source(functions=("TX_CLK", "RX_CLK")))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unrelated_identity_is_not_classified_as_an_ethernet_phy() -> None:
    source = _source()
    unrelated = source.model_copy(
        update={
            "components": {
                reference: component.model_copy(update={"value": "USB PHY module"})
                for reference, component in source.components.items()
            },
            "component_symbols": {"U1": "Synthetic:USB_PHY", "U2": "Synthetic:USB_PHY"},
        }
    )

    assert not ethernet_tx_clock_output_sharing_candidates(unrelated)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_incomplete_and_duplicate_role_evidence_suppress() -> None:
    source = _source()
    dnp = _source(dnp_references=("U2",))
    open_pin = source.model_copy(update={"nets": {}})
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "EXTRA": ("U2.1",)}})
    missing_inventory = source.model_copy(
        update={"component_pin_numbers": {"U1": (), "U2": ("1",)}}
    )
    duplicate_role = source.model_copy(
        update={
            "nets": {SHARED_NET: ("U1.1", "U1.2", "U2.1")},
            "pin_functions": {**source.pin_functions, "U1.2": "MII_TX_CLK"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.2": "passive"},
            "component_pin_numbers": {"U1": ("1", "2"), "U2": ("1",)},
        }
    )

    for case in (dnp, open_pin, multiply_assigned, missing_inventory, duplicate_role):
        assert not ethernet_tx_clock_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_nets_and_two_native_outputs_are_left_to_other_checks() -> None:
    source = _source()
    return_net = source.model_copy(update={"nets": {"GND": ("U1.1", "U2.1")}})
    native_outputs = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U2.1": "output"}}
    )

    assert not ethernet_tx_clock_output_sharing_candidates(return_net)
    assert not ethernet_tx_clock_output_sharing_candidates(native_outputs)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_the_review() -> None:
    source = _source()
    finding = _findings(_report(source))[0]
    blocked = _findings(_report(source, "block"))[0]
    disabled = _findings(_report(source, "off"))[0]
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="A reviewed clock mux selects only one fitted PHY at a time",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_order_stable_and_separating_the_clock_nets_clears_it() -> None:
    source = _source()
    reversed_source = ethernet_mii_tx_clock_output_netlist(
        references=("U2", "U1"), functions=("TX_CLK", "TX_CLK")
    )

    assert (
        _findings(_report(source))[0].fingerprint
        == _findings(_report(reversed_source))[0].fingerprint
    )
    assert not ethernet_tx_clock_output_sharing_candidates(_source(shared=False))
