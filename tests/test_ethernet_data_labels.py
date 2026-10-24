"""Focused Ethernet pin-function and net-label review regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates, evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach

RULE_ID = "bus.ethernet_data_label_mismatch"
pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _ethernet_netlist(
    functions: tuple[str, str, str, str],
    labels: tuple[str, str, str, str],
    *,
    dnp: bool = False,
) -> NetlistContract:
    pins = tuple(f"U1.{number}" for number in range(1, 5))
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic Ethernet PHY", footprint="")},
        nets={label: (pin,) for label, pin in zip(labels, pins, strict=True)},
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:EthernetPhy"},
        pin_functions=dict(zip(pins, functions, strict=True)),
        component_pin_numbers={"U1": ("1", "2", "3", "4")},
    )


def _findings(netlist: NetlistContract):
    return tuple(item for item in candidates(netlist) if item.rule_id == RULE_ID)


@pytest.mark.parametrize(
    ("functions", "valid_labels", "crossed_labels"),
    (
        (
            ("TD+", "TD-", "RD+", "RD-"),
            ("ETH_TX_P", "ETH_TX_N", "ETH_RX_P", "ETH_RX_N"),
            ("ETH_RX_P", "ETH_RX_N", "ETH_TX_P", "ETH_TX_N"),
        ),
        (
            ("TDP", "TDN", "RDP", "RDN"),
            ("MDI_TXP", "MDI_TXN", "MDI_RXP", "MDI_RXN"),
            ("MDI_RXP", "MDI_RXN", "MDI_TXP", "MDI_TXN"),
        ),
    ),
    ids=("signed-pin-functions", "p-n-pin-functions"),
)
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_crossed_ethernet_pair_labels_are_reviewed_with_exact_pin_evidence(
    functions: tuple[str, str, str, str],
    valid_labels: tuple[str, str, str, str],
    crossed_labels: tuple[str, str, str, str],
) -> None:
    assert not _findings(_ethernet_netlist(functions, valid_labels))

    findings = _findings(_ethernet_netlist(functions, crossed_labels))

    assert tuple(item.subject for item in findings) == tuple(
        f"U1.{number}: {function} on {net}"
        for number, function, net in zip(range(1, 5), functions, crossed_labels, strict=True)
    )
    assert tuple(item.evidence["pin_direction"] for item in findings) == (
        ("TX",),
        ("TX",),
        ("RX",),
        ("RX",),
    )
    assert tuple(item.evidence["net_direction"] for item in findings) == (
        ("RX",),
        ("RX",),
        ("TX",),
        ("TX",),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_neutral_indexed_dnp_and_ambiguous_net_labels_are_not_classified() -> None:
    functions = ("TDP", "TDN", "RDP", "RDN")
    controls = (
        _ethernet_netlist(functions, ("TX+", "TX-", "RX+", "RX-")),
        _ethernet_netlist(functions, ("DATA_A", "DATA_B", "DATA_C", "DATA_D")),
        _ethernet_netlist(functions, ("ETH_TX1_P", "ETH_TX1_N", "ETH_RX1_P", "ETH_RX1_N")),
        _ethernet_netlist(functions, ("ETH_TX_P", "ETH_TX_N", "ETH_RX_P", "ETH_RX_N"), dnp=True),
    )
    ambiguous = _ethernet_netlist(
        functions,
        ("ETH_TX_P", "ETH_TX_N", "ETH_RX_P", "ETH_RX_N"),
    ).model_copy(
        update={
            "nets": {
                "ETH_TX_P": ("U1.1",),
                "AUX": ("U1.1",),
                "ETH_TX_N": ("U1.2",),
                "ETH_RX_P": ("U1.3",),
                "ETH_RX_N": ("U1.4",),
            }
        }
    )

    assert all(not _findings(control) for control in controls)
    assert not _findings(ambiguous)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_pair_short_remains_with_complementary_pair_rule() -> None:
    source = _ethernet_netlist(
        ("TDP", "TDN", "RDP", "RDN"),
        ("ETH_TX_P", "ETH_TX_N", "ETH_RX_P", "ETH_RX_N"),
    )
    shorted = source.model_copy(
        update={
            "nets": {
                "ETH_TX_P": ("U1.1", "U1.2"),
                "ETH_RX_P": ("U1.3",),
                "ETH_RX_N": ("U1.4",),
            }
        }
    )

    assert not _findings(shorted)
    assert any(item.rule_id == "bus.complementary_pair_assignment" for item in candidates(shorted))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_review_block_off_and_exact_ignore_policy_are_supported() -> None:
    source = _ethernet_netlist(
        ("TDP", "TDN", "RDP", "RDN"),
        ("ETH_RX_P", "ETH_RX_N", "ETH_TX_P", "ETH_TX_N"),
    )
    reviewed = evaluate("synthetic-ethernet-labels", coach(source), DesignLintPolicy())
    finding = next(item for item in reviewed.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review"

    blocked = evaluate(
        "synthetic-ethernet-labels",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="block", reason="Reviewed map"),)
        ),
    )
    assert blocked.status == "FAIL"

    disabled = evaluate(
        "synthetic-ethernet-labels",
        coach(source),
        DesignLintPolicy(
            rules=(DesignLintRuleOverride(rule_id=RULE_ID, mode="off", reason="Intentional"),)
        ),
    )
    assert all(
        item.disposition == "RULE_OFF" for item in disabled.findings if item.rule_id == RULE_ID
    )

    ignored = evaluate(
        "synthetic-ethernet-labels",
        coach(source),
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project pin map reviewed",
                ),
            )
        ),
    )
    ignored_finding = next(item for item in ignored.findings if item.rule_id == RULE_ID)
    assert ignored_finding.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_reordering_is_stable_and_corrected_labels_clear_findings() -> None:
    fault = _ethernet_netlist(
        ("TD+", "TD-", "RD+", "RD-"),
        ("ETH_RX_P", "ETH_RX_N", "ETH_TX_P", "ETH_TX_N"),
    )
    reordered = fault.model_copy(
        update={
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )

    assert _findings(reordered) == _findings(fault)
    corrected = _ethernet_netlist(
        ("TD+", "TD-", "RD+", "RD-"),
        ("ETH_TX_P", "ETH_TX_N", "ETH_RX_P", "ETH_RX_N"),
    )
    assert not _findings(corrected)
