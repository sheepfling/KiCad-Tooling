"""Focused serial TX/RX same-net review regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.serial_same_net import serial_tx_rx_same_net_candidates
from tests.serial_participant_support import coach, same_net_serial_netlist, serial_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.serial_tx_rx_same_net"


def _lint(
    netlist: NetlistContract,
    mode: str = "review",
    *,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode=mode,
                reason="Review synthetic serial TX/RX topology",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-serial-tx-rx-tie", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_uart_tx_rx_pair_is_reviewed_and_full_duplex_control_is_quiet() -> None:
    fault = same_net_serial_netlist()
    default_report = evaluate("synthetic-serial-tx-rx-tie", coach(fault), DesignLintPolicy())
    default_finding = _findings(default_report)[0]
    reviewed = _findings(_lint(fault))[0]
    control = serial_netlist()

    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    assert reviewed.mode == "review"
    assert reviewed.subject == "U1: USART1 TX/RX share UART1_DATA"
    assert reviewed.evidence == {
        "component": ("U1",),
        "channel": ("USART1",),
        "tx_pin": ("U1.1",),
        "rx_pin": ("U1.2",),
        "net": ("UART1_DATA",),
    }
    assert not _findings(_lint(control))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_and_different_channel_pairs_are_unclassified() -> None:
    fault = same_net_serial_netlist()
    open_nets = dict(fault.nets)
    open_nets["UART1_DATA"] = ("U1.1",)
    open_rx = fault.model_copy(update={"nets": open_nets})
    extra_assignment = fault.model_copy(update={"nets": {**fault.nets, "SECOND_NET": ("U1.1",)}})
    duplicate_role_nets = dict(fault.nets)
    del duplicate_role_nets["DIFF_TX_P"]
    duplicate_role_nets["UART1_DATA"] = ("U1.1", "U1.2", "U1.5")
    duplicate_role = fault.model_copy(
        update={
            "nets": duplicate_role_nets,
            "pin_functions": {**fault.pin_functions, "U1.5": "USART1_RX"},
        }
    )
    different_channel = fault.model_copy(
        update={"pin_functions": {**fault.pin_functions, "U1.2": "UART2_RX"}}
    )
    dnp = fault.model_copy(update={"dnp_components": ("U1",)})

    assert serial_tx_rx_same_net_candidates(dnp) == ()
    assert serial_tx_rx_same_net_candidates(open_rx) == ()
    assert serial_tx_rx_same_net_candidates(extra_assignment) == ()
    assert serial_tx_rx_same_net_candidates(duplicate_role) == ()
    assert serial_tx_rx_same_net_candidates(different_channel) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_or_ignore_an_intentional_single_wire_pair() -> None:
    fault = same_net_serial_netlist()
    initial = _findings(_lint(fault))[0]
    blocked = _findings(_lint(fault, "block"))[0]
    ignored = _findings(
        _lint(
            fault,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=initial.fingerprint,
                reason="Synthetic endpoint intentionally uses one-wire UART",
            ),
        )
    )[0]

    assert _lint(fault, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ordering_is_stable_and_separating_the_pair_clears_the_candidate() -> None:
    fault = same_net_serial_netlist()
    reordered = fault.model_copy(
        update={
            "components": dict(reversed(tuple(fault.components.items()))),
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    first = _findings(_lint(fault))[0]
    second = _findings(_lint(reordered))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert not _findings(_lint(serial_netlist()))
