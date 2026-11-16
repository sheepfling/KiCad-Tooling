"""Regressions for shared Ethernet PHY MII collision-output review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.ethernet_col_output_sharing import (
    ethernet_mii_collision_output_sharing_candidates,
    ethernet_phy_mii_collision_output_role,
)
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_output_sharing import (
    ethernet_phy_output_sharing_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.ethernet_mii_collision_outputs_share_net"
SHARED_NET = "MII_COL_SHARED"


def _source(
    *,
    shared: bool = True,
    functions: tuple[str, ...] = ("COL", "COL"),
    references: tuple[str, ...] = ("U1", "U2"),
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    return ethernet_phy_output_sharing_netlist(
        default_function="COL",
        pin_number="8",
        shared=shared,
        references=references,
        functions=functions,
        net_name=SHARED_NET,
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
                reason="Review synthetic Ethernet PHY MII COL sharing",
            ),
        )
    )
    policy = DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,))
    return evaluate("synthetic-ethernet-mii-col-sharing", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_shared_mii_collision_outputs_from_fitted_identified_phys_are_reviewed() -> None:
    finding = _findings(_report(_source()))[0]

    assert finding.mode == "review"
    assert finding.subject == f"U1, U2: Ethernet PHY MII COL outputs share {SHARED_NET}"
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "channels": ("ethernet-mii-collision",) * 2,
        "functions": ("COL", "COL"),
        "pins": ("U1.8", "U2.8"),
        "pin_types": ("passive", "passive"),
        "net": (SHARED_NET,),
        "identity_basis": ("Synthetic:Ethernet_PHY DP83848 Ethernet PHY",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_exact_mii_col_aliases_and_unlike_or_separate_controls() -> None:
    assert ethernet_phy_mii_collision_output_role("U1", "COL") == (
        "collision",
        "ethernet-mii-collision",
    )
    assert ethernet_phy_mii_collision_output_role("U1", "MII_COL") == (
        "collision",
        "ethernet-mii-collision",
    )
    assert ethernet_phy_mii_collision_output_role("U1", "MII-COL") == (
        "collision",
        "ethernet-mii-collision",
    )
    for function in ("COL/PHYAD0", "COLLISION", "CRS_COL", "COL_DV", "GPIO_COL"):
        assert ethernet_phy_mii_collision_output_role("U1", function) is None
    assert not ethernet_mii_collision_output_sharing_candidates(_source(shared=False))
    assert not ethernet_mii_collision_output_sharing_candidates(_source(functions=("COL", "CRS")))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unrelated_identity_and_connector_references_are_not_counted() -> None:
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

    assert not ethernet_mii_collision_output_sharing_candidates(unrelated)
    assert not ethernet_mii_collision_output_sharing_candidates(_source(references=("J1", "J2")))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_incomplete_and_duplicate_role_evidence_suppress() -> None:
    source = _source()
    dnp = _source(dnp_references=("U2",))
    open_pin = source.model_copy(update={"nets": {}})
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "EXTRA": ("U2.8",)}})
    missing_inventory = source.model_copy(
        update={"component_pin_numbers": {"U1": (), "U2": ("8",)}}
    )
    duplicate_role = source.model_copy(
        update={
            "nets": {SHARED_NET: ("U1.8", "U1.9", "U2.8")},
            "pin_functions": {**source.pin_functions, "U1.9": "MII_COL"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.9": "passive"},
            "component_pin_numbers": {"U1": ("8", "9"), "U2": ("8",)},
        }
    )

    for case in (dnp, open_pin, multiply_assigned, missing_inventory, duplicate_role):
        assert not ethernet_mii_collision_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_nets_and_native_output_conflicts_are_left_to_other_checks() -> None:
    source = _source()
    return_net = source.model_copy(update={"nets": {"GND": ("U1.8", "U2.8")}})
    native_outputs = source.model_copy(
        update={"pin_electrical_types": {"U1.8": "output", "U2.8": "output"}}
    )

    assert not ethernet_mii_collision_output_sharing_candidates(return_net)
    assert not ethernet_mii_collision_output_sharing_candidates(native_outputs)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_review() -> None:
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
                reason="A reviewed MII selector connects only one active PHY at a time",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_order_stable_and_splitting_the_col_nets_clears_it() -> None:
    source = _source()
    reversed_source = _source(references=("U2", "U1"))

    assert (
        _findings(_report(source))[0].fingerprint
        == _findings(_report(reversed_source))[0].fingerprint
    )
    assert not ethernet_mii_collision_output_sharing_candidates(_source(shared=False))
