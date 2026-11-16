"""Regressions for shared Ethernet PHY MII carrier-sense output review."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.ethernet_crs_output_sharing import (
    ethernet_crs_output_sharing_candidates,
    ethernet_phy_crs_output_role,
)
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_crs_output_sharing import (
    ethernet_mii_crs_output_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.ethernet_crs_outputs_share_net"
SHARED_NET = "MII_CRS_SHARED"


def _source(
    *,
    shared: bool = True,
    functions: tuple[str, ...] = ("CRS", "CRS"),
    references: tuple[str, ...] = ("U1", "U2"),
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    return ethernet_mii_crs_output_netlist(
        shared=shared,
        references=references,
        crs_functions=functions,
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
                reason="Review synthetic Ethernet PHY MII carrier-sense sharing",
            ),
        )
    )
    policy = DesignLintPolicy(
        rules=overrides,
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-ethernet-mii-crs-sharing", coach(netlist), policy)


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_ethernet_phy_crs_outputs_are_reviewed_by_default() -> None:
    finding = _findings(_report(_source()))[0]

    assert finding.mode == "review"
    assert finding.subject == f"U1, U2: Ethernet PHY CRS outputs share {SHARED_NET}"
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "channels": ("ethernet-mii-carrier-sense",) * 2,
        "functions": ("CRS", "CRS"),
        "pins": ("U1.1", "U2.1"),
        "pin_types": ("passive", "passive"),
        "net": (SHARED_NET,),
        "identity_basis": ("Synthetic:Ethernet_PHY DP83848 Ethernet PHY",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_bounded_mii_crs_alias_and_non_crs_or_separate_controls() -> None:
    aliases = _source(functions=("MII_CRS", "CRS"))
    separate = _source(shared=False)
    unrelated = _source().model_copy(
        update={
            "components": {
                reference: component.model_copy(update={"value": "USB PHY module"})
                for reference, component in _source().components.items()
            },
            "component_symbols": {"U1": "Synthetic:USB_PHY", "U2": "Synthetic:USB_PHY"},
        }
    )

    assert len(ethernet_crs_output_sharing_candidates(aliases)) == 1
    assert not ethernet_crs_output_sharing_candidates(separate)
    assert not ethernet_crs_output_sharing_candidates(_source(functions=("CRS", "COL")))
    assert not ethernet_crs_output_sharing_candidates(_source(functions=("CRS_DV", "CRS_DV")))
    assert not ethernet_crs_output_sharing_candidates(unrelated)
    assert ethernet_phy_crs_output_role("U1", "MII-CRS") == (
        "rx",
        "ethernet-mii-carrier-sense",
    )
    assert ethernet_phy_crs_output_role("U1", "CRS_DV") is None
    assert ethernet_phy_crs_output_role("U1", "CRS/RGMII_SEL0") is None
    assert ethernet_phy_crs_output_role("U1", "COL") is None


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_incomplete_and_duplicate_evidence_suppress_group() -> None:
    dnp = _source(dnp_references=("U2",))
    open_pin = _source().model_copy(
        update={"nets": {"PHY1_RXD0": ("U1.2",), "PHY2_RXD0": ("U2.2",)}}
    )
    multiply_assigned = _source().model_copy(
        update={"nets": {**_source().nets, "EXTRA": ("U2.1",)}}
    )
    missing_inventory = _source().model_copy(
        update={"component_pin_numbers": {"U1": ("2",), "U2": ("2",)}}
    )
    three_phy = _source(references=("U1", "U2", "U3"), functions=("CRS",) * 3)
    duplicate_role = three_phy.model_copy(
        update={
            "nets": {
                SHARED_NET: ("U1.1", "U1.3", "U2.1", "U3.1"),
                "PHY1_RXD0": ("U1.2",),
                "PHY2_RXD0": ("U2.2",),
                "PHY3_RXD0": ("U3.2",),
            },
            "pin_functions": {**three_phy.pin_functions, "U1.3": "MII_CRS"},
            "pin_electrical_types": {**three_phy.pin_electrical_types, "U1.3": "passive"},
            "component_pin_numbers": {
                **three_phy.component_pin_numbers,
                "U1": ("1", "2", "3"),
            },
        }
    )

    for case in (dnp, open_pin, multiply_assigned, missing_inventory, duplicate_role):
        assert not ethernet_crs_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_return_nets_and_two_native_outputs_are_skipped() -> None:
    source = _source()
    return_net = source.model_copy(
        update={
            "nets": {
                "GND": source.nets[SHARED_NET],
                "PHY1_RXD0": ("U1.2",),
                "PHY2_RXD0": ("U2.2",),
            }
        }
    )
    native_outputs = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U2.1": "output"}}
    )

    assert not ethernet_crs_output_sharing_candidates(return_net)
    assert not ethernet_crs_output_sharing_candidates(native_outputs)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_ignore_the_exact_finding() -> None:
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
                reason="Synthetic fixture selects one PHY through a reviewed mux",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_order_stable_and_splitting_crs_nets_clears_finding() -> None:
    source = _source()
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
    assert not _findings(_report(_source(shared=False)))
