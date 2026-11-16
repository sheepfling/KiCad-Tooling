"""Regressions for Ethernet PHY receive-data outputs sharing one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, rule_catalog
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.ethernet_rx_output_sharing import (
    ethernet_phy_rx_output_role,
    ethernet_rx_output_sharing_candidates,
)
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_rx_output_sharing import ethernet_rx_output_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.ethernet_rx_outputs_share_net"


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
                reason="Review synthetic Ethernet PHY receive-output sharing",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-ethernet-rx-output-sharing", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.architecture
def test_catalog_owns_ethernet_rx_rule_in_its_theme_module() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/ethernet_rx_output_sharing.py#ethernet_rx_output_sharing_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/signal_pair_output_sharing.py#signal_output_sharing_groups"
        in rule.implementation_refs
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_ethernet_phy_rx_data_outputs_are_reviewed() -> None:
    finding = _findings(_report(ethernet_rx_output_netlist()))[0]

    assert finding.subject == "U1, U2: Ethernet PHY receive-data outputs share ETH_RXD_SHARED"
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "channels": ("ethernet-rx-data-0", "ethernet-rx-data-0"),
        "functions": ("RXD0", "RXD0"),
        "pins": ("U1.1", "U2.1"),
        "pin_types": ("passive", "passive"),
        "net": ("ETH_RXD_SHARED",),
        "identity_basis": ("Synthetic:Ethernet_PHY Ethernet PHY module",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bounded_mii_family_aliases_and_separate_nets_are_controls() -> None:
    aliases = ethernet_rx_output_netlist(receiver_functions=("RGMII_RXD0", "RMII_RXD1"))
    separate = ethernet_rx_output_netlist(shared=False)
    unrelated = ethernet_rx_output_netlist().model_copy(
        update={
            "components": {
                reference: component.model_copy(update={"value": "USB PHY module"})
                for reference, component in ethernet_rx_output_netlist().components.items()
            },
            "component_symbols": {"U1": "Synthetic:USB_PHY", "U2": "Synthetic:USB_PHY"},
        }
    )

    assert len(ethernet_rx_output_sharing_candidates(aliases)) == 1
    assert not ethernet_rx_output_sharing_candidates(separate)
    assert not ethernet_rx_output_sharing_candidates(unrelated)
    assert ethernet_phy_rx_output_role("U1", "RX_DATA[3]") == ("rx", "ethernet-rx-data-3")
    assert ethernet_phy_rx_output_role("U1", "RX_DV") is None
    assert ethernet_phy_rx_output_role("U1", "RXD8") is None


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_and_incomplete_evidence_suppress_the_group() -> None:
    source = ethernet_rx_output_netlist(references=("U1", "U2", "U3"))
    dnp = ethernet_rx_output_netlist(dnp_references=("U2",))
    open_pin = ethernet_rx_output_netlist().model_copy(
        update={"nets": {"PHY1_TXD": ("U1.2",), "PHY2_TXD": ("U2.2",)}}
    )
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "OTHER_RX": ("U3.1",)}})
    missing_inventory = ethernet_rx_output_netlist().model_copy(
        update={"component_pin_numbers": {"U1": ("1", "2")}}
    )
    duplicate_role = source.model_copy(
        update={
            "nets": {**source.nets, "ETH_RXD_SHARED": ("U1.1", "U1.3", "U2.1", "U3.1")},
            "pin_functions": {**source.pin_functions, "U1.3": "MII_RXDATA"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.3": "passive"},
            "component_pin_numbers": {**source.component_pin_numbers, "U1": ("1", "2", "3")},
        }
    )

    for case in (dnp, open_pin, multiply_assigned, missing_inventory, duplicate_role):
        assert not ethernet_rx_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_output_conflicts_return_nets_and_unsupported_types_are_skipped() -> None:
    source = ethernet_rx_output_netlist()
    native_conflict = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U2.1": "output"}}
    )
    return_net = source.model_copy(
        update={
            "nets": {
                "GND": source.nets["ETH_RXD_SHARED"],
                "PHY1_TXD": ("U1.2",),
                "PHY2_TXD": ("U2.2",),
            }
        }
    )
    unsupported = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "input", "U2.1": "input"}}
    )

    assert not ethernet_rx_output_sharing_candidates(native_conflict)
    assert not ethernet_rx_output_sharing_candidates(return_net)
    assert not ethernet_rx_output_sharing_candidates(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_ignore_the_exact_finding() -> None:
    netlist = ethernet_rx_output_netlist()
    finding = _findings(_report(netlist))[0]
    blocked = _findings(_report(netlist, "block"))[0]
    disabled = _findings(_report(netlist, "off"))[0]
    ignored = _findings(
        _report(
            netlist,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic example intentionally selects one Ethernet PHY",
            ),
        )
    )[0]

    assert _report(netlist, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_order_stable_and_separating_outputs_clears_finding() -> None:
    source = ethernet_rx_output_netlist()
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
    assert not _findings(_report(ethernet_rx_output_netlist(shared=False)))
