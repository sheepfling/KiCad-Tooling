"""Regressions for shared Ethernet PHY receive-clock output review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, rule_catalog
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.ethernet_rx_clock_output_sharing import (
    ethernet_phy_rx_clock_output_role,
    ethernet_rx_clock_output_sharing_candidates,
)
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_rx_clock_output_sharing import (
    ethernet_rx_clock_output_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.ethernet_rx_clock_outputs_share_net"


def _report(
    netlist: NetlistContract,
    mode: str = "review",
    *,
    ignore: DesignLintIgnore | None = None,
):
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic Ethernet PHY receive-clock output sharing",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-ethernet-rx-clock-sharing", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.architecture
def test_catalog_owns_ethernet_rx_clock_rule_in_its_theme_module() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/ethernet_rx_clock_output_sharing.py#"
        "ethernet_rx_clock_output_sharing_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/signal_pair_output_sharing.py#signal_output_sharing_groups"
        in rule.implementation_refs
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_ethernet_phy_rx_clocks_on_one_net_are_reviewed() -> None:
    finding = _findings(_report(ethernet_rx_clock_output_netlist()))[0]

    assert finding.subject == ("U1, U2: Ethernet PHY receive-clock outputs share MII_RX_CLK_SHARED")
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "channels": (
            "ethernet-mii-receive-clock",
            "ethernet-mii-receive-clock",
        ),
        "functions": ("RXC", "RXC"),
        "pins": ("U1.1", "U2.1"),
        "pin_types": ("passive", "passive"),
        "net": ("MII_RX_CLK_SHARED",),
        "identity_basis": ("Synthetic:Ethernet_PHY LAN8720 Ethernet PHY",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mii_aliases_and_separate_or_unrelated_clocks_are_controls() -> None:
    aliases = ethernet_rx_clock_output_netlist(clock_functions=("MII_RX_CLK", "RGMII_RXC"))
    separate = ethernet_rx_clock_output_netlist(shared=False)
    unrelated = ethernet_rx_clock_output_netlist().model_copy(
        update={
            "components": {
                reference: component.model_copy(update={"value": "USB PHY module"})
                for reference, component in ethernet_rx_clock_output_netlist().components.items()
            },
            "component_symbols": {"U1": "Synthetic:USB_PHY", "U2": "Synthetic:USB_PHY"},
        }
    )
    ambiguous_mode = ethernet_rx_clock_output_netlist(clock_functions=("REF_CLK", "REF_CLK"))
    wrong_direction = ethernet_rx_clock_output_netlist(clock_functions=("TXC", "TXC"))

    assert len(ethernet_rx_clock_output_sharing_candidates(aliases)) == 1
    assert not ethernet_rx_clock_output_sharing_candidates(separate)
    assert not ethernet_rx_clock_output_sharing_candidates(unrelated)
    assert not ethernet_rx_clock_output_sharing_candidates(ambiguous_mode)
    assert not ethernet_rx_clock_output_sharing_candidates(wrong_direction)
    assert ethernet_phy_rx_clock_output_role("U1", "RX_CLK") == (
        "rx",
        "ethernet-mii-receive-clock",
    )
    assert ethernet_phy_rx_clock_output_role("U1", "MII_RXC") == (
        "rx",
        "ethernet-mii-receive-clock",
    )
    assert ethernet_phy_rx_clock_output_role("U1", "RX_DV") is None
    assert ethernet_phy_rx_clock_output_role("U1", "REF_CLK") is None


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_incomplete_and_duplicate_evidence_suppress_group() -> None:
    source = ethernet_rx_clock_output_netlist(references=("U1", "U2", "U3"))
    dnp = ethernet_rx_clock_output_netlist(dnp_references=("U2",))
    open_pin = ethernet_rx_clock_output_netlist().model_copy(
        update={"nets": {"PHY1_RXD0": ("U1.2",), "PHY2_RXD0": ("U2.2",)}}
    )
    multiply_assigned = source.model_copy(
        update={"nets": {**source.nets, "OTHER_CLOCK": ("U3.1",)}}
    )
    missing_inventory = ethernet_rx_clock_output_netlist().model_copy(
        update={"component_pin_numbers": {"U1": ("1", "2")}}
    )
    duplicate_role = source.model_copy(
        update={
            "nets": {
                **source.nets,
                "MII_RX_CLK_SHARED": ("U1.1", "U1.3", "U2.1", "U3.1"),
            },
            "pin_functions": {**source.pin_functions, "U1.3": "MII_RX_CLK"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.3": "passive"},
            "component_pin_numbers": {**source.component_pin_numbers, "U1": ("1", "2", "3")},
        }
    )

    for case in (dnp, open_pin, multiply_assigned, missing_inventory, duplicate_role):
        assert not ethernet_rx_clock_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_output_conflicts_return_nets_and_unsupported_types_are_skipped() -> None:
    source = ethernet_rx_clock_output_netlist()
    native_conflict = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U2.1": "output"}}
    )
    return_net = source.model_copy(
        update={
            "nets": {
                "GND": source.nets["MII_RX_CLK_SHARED"],
                "PHY1_RXD0": ("U1.2",),
                "PHY2_RXD0": ("U2.2",),
            }
        }
    )
    unsupported = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "input", "U2.1": "input"}}
    )

    assert not ethernet_rx_clock_output_sharing_candidates(native_conflict)
    assert not ethernet_rx_clock_output_sharing_candidates(return_net)
    assert not ethernet_rx_clock_output_sharing_candidates(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_ignore_the_exact_finding() -> None:
    netlist = ethernet_rx_clock_output_netlist()
    finding = _findings(_report(netlist))[0]
    blocked = _findings(_report(netlist, "block"))[0]
    disabled = _findings(_report(netlist, "off"))[0]
    ignored = _findings(
        _report(
            netlist,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic PHY selection uses a reviewed clock mux",
            ),
        )
    )[0]

    assert _report(netlist, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_order_stable_and_separating_clocks_clears_finding() -> None:
    source = ethernet_rx_clock_output_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    first = _findings(_report(source))[0]
    second = _findings(_report(reordered))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert not _findings(_report(ethernet_rx_clock_output_netlist(shared=False)))
