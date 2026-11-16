"""Regressions for shared Ethernet PHY RMII CRS_DV output review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.ethernet_crs_dv_output_sharing import (
    ethernet_crs_dv_output_sharing_candidates,
    ethernet_phy_crs_dv_output_role,
)
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_rx_status_output_sharing import (
    ethernet_rx_status_output_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.ethernet_crs_dv_outputs_share_net"
SHARED_NET = "RMII_CRS_DV_SHARED"


def _netlist(
    *,
    functions: tuple[str, ...] = ("CRS_DV", "CRS_DV"),
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    return ethernet_rx_status_output_netlist(
        references=references,
        status_functions=functions,
        status_net_name=SHARED_NET,
        shared=shared,
        dnp_references=dnp_references,
    )


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
                reason="Review synthetic Ethernet PHY CRS_DV sharing",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-ethernet-crs-dv-sharing", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_ethernet_phy_crs_dv_outputs_are_reviewed() -> None:
    finding = _findings(_report(_netlist()))[0]

    assert finding.subject == f"U1, U2: Ethernet PHY CRS_DV outputs share {SHARED_NET}"
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "channels": ("ethernet-rmii-carrier-sense-rx-data-valid",) * 2,
        "functions": ("CRS_DV", "CRS_DV"),
        "pins": ("U1.1", "U2.1"),
        "pin_types": ("passive", "passive"),
        "net": (SHARED_NET,),
        "identity_basis": ("Synthetic:Ethernet_PHY LAN8720 Ethernet PHY",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bounded_crs_dv_aliases_and_separate_or_different_roles_are_controls() -> None:
    aliases = _netlist(functions=("RMII_CRS_DV", "CRSDV"))
    separate = _netlist(shared=False)
    different_role = _netlist(functions=("CRS_DV", "RXDV"))
    unrelated = _netlist().model_copy(
        update={
            "components": {
                reference: component.model_copy(update={"value": "USB PHY module"})
                for reference, component in _netlist().components.items()
            },
            "component_symbols": {"U1": "Synthetic:USB_PHY", "U2": "Synthetic:USB_PHY"},
        }
    )

    assert len(ethernet_crs_dv_output_sharing_candidates(aliases)) == 1
    assert not ethernet_crs_dv_output_sharing_candidates(separate)
    assert not ethernet_crs_dv_output_sharing_candidates(different_role)
    assert not ethernet_crs_dv_output_sharing_candidates(unrelated)
    assert ethernet_phy_crs_dv_output_role("U1", "CRS_DV") == (
        "rx",
        "ethernet-rmii-carrier-sense-rx-data-valid",
    )
    assert ethernet_phy_crs_dv_output_role("U1", "RMII_CRSDV") == (
        "rx",
        "ethernet-rmii-carrier-sense-rx-data-valid",
    )
    assert ethernet_phy_crs_dv_output_role("U1", "MII_CRS_DV") is None
    assert ethernet_phy_crs_dv_output_role("U1", "TX_EN") is None


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_incomplete_and_duplicate_evidence_suppress_group() -> None:
    dnp = _netlist(dnp_references=("U2",))
    open_pin = _netlist().model_copy(
        update={"nets": {"PHY1_RXD0": ("U1.2",), "PHY2_RXD0": ("U2.2",)}}
    )
    multiply_assigned = _netlist().model_copy(
        update={
            "nets": {
                **_netlist().nets,
                "OTHER_STATUS": ("U2.1",),
            }
        }
    )
    missing_inventory = _netlist().model_copy(
        update={"component_pin_numbers": {"U1": ("2",), "U2": ("2",)}}
    )
    three_phy = _netlist(references=("U1", "U2", "U3"), functions=("CRS_DV",) * 3)
    duplicate_role = three_phy.model_copy(
        update={
            "nets": {
                SHARED_NET: ("U1.1", "U1.3", "U2.1", "U3.1"),
                "PHY1_RXD0": ("U1.2",),
                "PHY2_RXD0": ("U2.2",),
                "PHY3_RXD0": ("U3.2",),
            },
            "pin_functions": {**three_phy.pin_functions, "U1.3": "RMII_CRS_DV"},
            "pin_electrical_types": {**three_phy.pin_electrical_types, "U1.3": "passive"},
            "component_pin_numbers": {**three_phy.component_pin_numbers, "U1": ("1", "2", "3")},
        }
    )

    for case in (dnp, open_pin, multiply_assigned, missing_inventory, duplicate_role):
        assert not ethernet_crs_dv_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_nets_unsupported_types_and_native_outputs_are_skipped() -> None:
    source = _netlist()
    return_net = source.model_copy(
        update={
            "nets": {
                "GND": source.nets[SHARED_NET],
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

    assert not ethernet_crs_dv_output_sharing_candidates(return_net)
    assert not ethernet_crs_dv_output_sharing_candidates(unsupported)
    assert not ethernet_crs_dv_output_sharing_candidates(native_output)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_ignore_the_exact_finding() -> None:
    source = _netlist()
    finding = _findings(_report(source))[0]
    blocked = _findings(_report(source, "block"))[0]
    disabled = _findings(_report(source, "off"))[0]
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic fixture selects one PHY through a reviewed mux",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_order_stable_and_separating_status_pins_clears_finding() -> None:
    source = _netlist()
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
    assert not _findings(_report(_netlist(shared=False)))
