"""Focused review regressions for CAN controller TX/RX pins sharing one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.can_tx_rx_same_net import (
    can_signal_role_and_channel,
    can_tx_rx_same_net_candidates,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.can_tx_rx_same_net import can_tx_rx_same_net_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.can_tx_rx_same_net"


def _report(
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
                reason="Review synthetic CAN controller TX/RX assignments",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-can-tx-rx-same-net", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_explicit_same_channel_can_tx_rx_pins_on_one_net_are_reviewed() -> None:
    assert can_signal_role_and_channel("CAN1_TX") == ("tx", "can:index1")
    assert can_signal_role_and_channel("CAN_RXD") == ("rx", "can:default")
    assert can_signal_role_and_channel("FDCAN2_TX") == ("tx", "fdcan:index2")
    assert can_signal_role_and_channel("TXD_CAN") == ("tx", "can:default")
    assert can_signal_role_and_channel("TXD") is None
    assert can_signal_role_and_channel("UART1_RX") is None

    source = can_tx_rx_same_net_netlist()
    finding = _findings(_report(source))[0]

    assert finding.subject == (
        "U1: CAN channel 1 TX CAN1_TX and RX CAN1_RX share CAN_CONTROL_SHARED"
    )
    assert finding.evidence == {
        "component": ("U1",),
        "channel": ("CAN channel 1",),
        "tx_pin": ("U1.1",),
        "tx_function": ("CAN1_TX",),
        "tx_electrical_type": ("output",),
        "rx_pin": ("U1.2",),
        "rx_function": ("CAN1_RX",),
        "rx_electrical_type": ("input",),
        "net": ("CAN_CONTROL_SHARED",),
    }


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_separate_assignments_and_other_protocols_remain_quiet() -> None:
    separated = can_tx_rx_same_net_netlist(shared=False)
    uart_functions = can_tx_rx_same_net_netlist(
        tx_function="USART1_TX",
        rx_function="USART1_RX",
    )
    assert not can_tx_rx_same_net_candidates(separated)
    assert not can_tx_rx_same_net_candidates(uart_functions)
    assert not _findings(_report(separated))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_duplicate_role_channel_mismatch_and_incomplete_inventory_are_skipped() -> None:
    source = can_tx_rx_same_net_netlist()
    dnp = can_tx_rx_same_net_netlist(dnp=True)
    open_tx = source.model_copy(update={"nets": {"CAN_CONTROL_SHARED": ("U1.2",)}})
    multiply_assigned = source.model_copy(update={"nets": {**source.nets, "CAN_AUX": ("U1.1",)}})
    duplicate_tx = source.model_copy(
        update={
            "nets": {
                "CAN_CONTROL_SHARED": ("U1.1", "U1.2", "U1.3"),
            },
            "pin_functions": {**source.pin_functions, "U1.3": "CAN1_TX"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.3": "output"},
            "component_pin_numbers": {"U1": ("1", "2", "3")},
        }
    )
    channel_mismatch = can_tx_rx_same_net_netlist(rx_function="CAN2_RX")
    missing_inventory = source.model_copy(update={"component_pin_numbers": {}})
    pin_missing_from_inventory = source.model_copy(update={"component_pin_numbers": {"U1": ("2",)}})
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "component_symbols": {"J1": "Connector:Conn_01x02"},
            "nets": {"CAN_CONTROL_SHARED": ("J1.1", "J1.2")},
            "pin_functions": {"J1.1": "CAN1_TX", "J1.2": "CAN1_RX"},
            "pin_electrical_types": {"J1.1": "output", "J1.2": "input"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )

    for unsupported in (
        dnp,
        open_tx,
        multiply_assigned,
        duplicate_tx,
        channel_mismatch,
        missing_inventory,
        pin_missing_from_inventory,
        connector,
    ):
        assert not can_tx_rx_same_net_candidates(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_native_outputs_defer_to_erc_and_unknown_types_remain_reviewable() -> None:
    outputs = can_tx_rx_same_net_netlist(tx_type="output", rx_type="output")
    unknown = outputs.model_copy(update={"pin_electrical_types": {}})

    assert not can_tx_rx_same_net_candidates(outputs)
    finding = can_tx_rx_same_net_candidates(unknown)[0]
    assert finding.evidence["tx_electrical_type"] == ("unknown",)
    assert finding.evidence["rx_electrical_type"] == ("unknown",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_block_disable_or_ignore_the_exact_pair() -> None:
    source = can_tx_rx_same_net_netlist()
    initial = _findings(_report(source))[0]
    blocked = _findings(_report(source, "block"))[0]
    disabled = _findings(_report(source, "off"))[0]
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=initial.fingerprint,
                reason="The controller intentionally uses an external loopback path",
            ),
        )
    )[0]

    assert _report(source, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprints_are_stable_and_repair_clears_candidate() -> None:
    source = can_tx_rx_same_net_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    first = _findings(_report(source))[0]
    second = _findings(_report(reordered))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert not _findings(_report(can_tx_rx_same_net_netlist(shared=False)))
