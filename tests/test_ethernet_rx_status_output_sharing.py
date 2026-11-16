"""Regressions for shared Ethernet PHY receive-status/control output review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, rule_catalog
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.ethernet_rx_status_output_sharing import (
    ethernet_phy_rx_status_output_role,
    ethernet_rx_status_output_sharing_candidates,
)
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_rx_status_output_sharing import (
    ethernet_rx_status_output_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.ethernet_rx_status_outputs_share_net"


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
                reason="Review synthetic Ethernet PHY receive-status sharing",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-ethernet-rx-status-sharing", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.architecture
def test_catalog_owns_ethernet_rx_status_rule_in_its_theme_module() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/ethernet_rx_status_output_sharing.py#"
        "ethernet_rx_status_output_sharing_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/ethernet_phy_identity.py#explicit_ethernet_phy_identity"
        in rule.implementation_refs
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_ethernet_phy_rxdv_outputs_on_one_net_are_reviewed() -> None:
    finding = _findings(_report(ethernet_rx_status_output_netlist()))[0]

    assert finding.subject == (
        "U1, U2: Ethernet PHY receive-status/control outputs share MII_RX_DV_SHARED"
    )
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "channels": (
            "ethernet-mii-receive-status-rxdv",
            "ethernet-mii-receive-status-rxdv",
        ),
        "functions": ("RXDV", "RXDV"),
        "pins": ("U1.1", "U2.1"),
        "pin_types": ("passive", "passive"),
        "net": ("MII_RX_DV_SHARED",),
        "identity_basis": ("Synthetic:Ethernet_PHY LAN8720 Ethernet PHY",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rxdv_rxer_aliases_and_separate_or_different_status_controls() -> None:
    aliases = ethernet_rx_status_output_netlist(status_functions=("MII_RX_DV", "RX_DV"))
    rxer = ethernet_rx_status_output_netlist(status_functions=("RXER", "MII_RX_ER"))
    separate = ethernet_rx_status_output_netlist(shared=False)
    different_status = ethernet_rx_status_output_netlist(status_functions=("RXDV", "RXER"))
    unrelated = ethernet_rx_status_output_netlist().model_copy(
        update={
            "components": {
                reference: component.model_copy(update={"value": "USB PHY module"})
                for reference, component in ethernet_rx_status_output_netlist().components.items()
            },
            "component_symbols": {"U1": "Synthetic:USB_PHY", "U2": "Synthetic:USB_PHY"},
        }
    )

    assert len(ethernet_rx_status_output_sharing_candidates(aliases)) == 1
    assert len(ethernet_rx_status_output_sharing_candidates(rxer)) == 1
    assert not ethernet_rx_status_output_sharing_candidates(separate)
    assert not ethernet_rx_status_output_sharing_candidates(different_status)
    assert not ethernet_rx_status_output_sharing_candidates(unrelated)
    assert ethernet_phy_rx_status_output_role("U1", "RX_DV") == (
        "rx",
        "ethernet-mii-receive-status-rxdv",
    )
    assert ethernet_phy_rx_status_output_role("U1", "GMII_RX_ER") == (
        "rx",
        "ethernet-mii-receive-status-rxer",
    )
    assert ethernet_phy_rx_status_output_role("U1", "RX_CTRL") == (
        "rx",
        "ethernet-rgmii-receive-control",
    )
    assert ethernet_phy_rx_status_output_role("U1", "RGMII_RX_CTRL") == (
        "rx",
        "ethernet-rgmii-receive-control",
    )
    assert ethernet_phy_rx_status_output_role("U1", "RX_CTL") is None
    assert ethernet_phy_rx_status_output_role("U1", "TXER") is None


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rgmii_rx_control_outputs_and_separate_control_are_classified() -> None:
    shared = ethernet_rx_status_output_netlist(
        receive_control_functions=("RX_CTRL", "RGMII_RX_CTRL")
    )
    separate = ethernet_rx_status_output_netlist(
        receive_control_functions=("RX_CTRL", "RGMII_RX_CTRL"),
        receive_control_shared=False,
    )
    native_outputs = ethernet_rx_status_output_netlist(
        receive_control_functions=("RX_CTRL", "RGMII_RX_CTRL"),
        receive_control_type="output",
    )
    mixed = ethernet_rx_status_output_netlist(
        status_functions=("RXDV", "RX_CTRL"),
        status_net_name="MIXED_RX_STATUS",
    )

    candidates = ethernet_rx_status_output_sharing_candidates(shared)
    candidate = next(
        item
        for item in candidates
        if item.evidence["channels"]
        == (
            "ethernet-rgmii-receive-control",
            "ethernet-rgmii-receive-control",
        )
    )
    assert len(candidates) == 2
    assert candidate.evidence["channels"] == (
        "ethernet-rgmii-receive-control",
        "ethernet-rgmii-receive-control",
    )
    assert candidate.evidence["functions"] == ("RGMII_RX_CTRL", "RX_CTRL")
    assert candidate.evidence["pins"] == ("U1.3", "U2.3")
    separate_candidates = ethernet_rx_status_output_sharing_candidates(separate)
    native_output_candidates = ethernet_rx_status_output_sharing_candidates(native_outputs)
    assert len(separate_candidates) == 1
    assert len(native_output_candidates) == 1
    assert all(
        channel != "ethernet-rgmii-receive-control"
        for candidate in separate_candidates + native_output_candidates
        for channel in candidate.evidence["channels"]
    )
    assert not ethernet_rx_status_output_sharing_candidates(mixed)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_incomplete_and_duplicate_evidence_suppress_group() -> None:
    dnp = ethernet_rx_status_output_netlist(dnp_references=("U2",))
    open_pin = ethernet_rx_status_output_netlist().model_copy(
        update={"nets": {"PHY1_RXD0": ("U1.2",), "PHY2_RXD0": ("U2.2",)}}
    )
    multiply_assigned = ethernet_rx_status_output_netlist().model_copy(
        update={
            "nets": {
                **ethernet_rx_status_output_netlist().nets,
                "OTHER_STATUS": ("U2.1",),
            }
        }
    )
    missing_inventory = ethernet_rx_status_output_netlist().model_copy(
        update={"component_pin_numbers": {"U1": ("2",), "U2": ("2",)}}
    )
    duplicate_role = ethernet_rx_status_output_netlist(references=("U1", "U2", "U3")).model_copy(
        update={
            "nets": {
                "MII_RX_DV_SHARED": ("U1.1", "U1.3", "U2.1", "U3.1"),
                "PHY1_RXD0": ("U1.2",),
                "PHY2_RXD0": ("U2.2",),
                "PHY3_RXD0": ("U3.2",),
            },
            "pin_functions": {
                **ethernet_rx_status_output_netlist(references=("U1", "U2", "U3")).pin_functions,
                "U1.3": "MII_RX_DV",
            },
            "pin_electrical_types": {
                **ethernet_rx_status_output_netlist(
                    references=("U1", "U2", "U3")
                ).pin_electrical_types,
                "U1.3": "passive",
            },
            "component_pin_numbers": {
                **ethernet_rx_status_output_netlist(
                    references=("U1", "U2", "U3")
                ).component_pin_numbers,
                "U1": ("1", "2", "3"),
            },
        }
    )

    for case in (dnp, open_pin, multiply_assigned, missing_inventory, duplicate_role):
        assert not ethernet_rx_status_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_nets_unsupported_types_and_native_outputs_are_skipped() -> None:
    source = ethernet_rx_status_output_netlist()
    return_net = source.model_copy(
        update={
            "nets": {
                "GND": source.nets["MII_RX_DV_SHARED"],
                "PHY1_RXD0": ("U1.2",),
                "PHY2_RXD0": ("U2.2",),
            }
        }
    )
    unsupported = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "input", "U2.1": "input"}}
    )
    native_output = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U2.1": "output"}}
    )

    assert not ethernet_rx_status_output_sharing_candidates(return_net)
    assert not ethernet_rx_status_output_sharing_candidates(unsupported)
    assert not ethernet_rx_status_output_sharing_candidates(native_output)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_ignore_the_exact_finding() -> None:
    netlist = ethernet_rx_status_output_netlist()
    finding = _findings(_report(netlist))[0]
    blocked = _findings(_report(netlist, "block"))[0]
    disabled = _findings(_report(netlist, "off"))[0]
    ignored = _findings(
        _report(
            netlist,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic fixture selects one PHY through a reviewed mux",
            ),
        )
    )[0]

    assert _report(netlist, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_order_stable_and_separating_status_pins_clears_finding() -> None:
    source = ethernet_rx_status_output_netlist()
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
    assert not _findings(_report(ethernet_rx_status_output_netlist(shared=False)))
