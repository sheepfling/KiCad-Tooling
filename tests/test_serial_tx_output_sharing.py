"""Focused review tests for fitted serial transmit functions sharing one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import NetlistContract
from kicad_tooling.hwrepo.serial_tx_output_sharing import serial_tx_output_sharing_candidates
from tests.serial_participant_support import coach, serial_tx_output_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.serial_tx_outputs_share_net"


def _report(
    netlist: NetlistContract,
    mode: str = "review",
    *,
    ignore: DesignLintIgnore | None = None,
):
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Review serial TX sharing"),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-serial-tx-sharing", coach(netlist), policy)


def _findings(report) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_transmit_functions_on_one_net_are_reviewed() -> None:
    netlist = serial_tx_output_netlist()
    finding = _findings(_report(netlist))[0]

    assert finding.subject == "U1, U2: serial TX functions share SERIAL_TX_BUS"
    assert finding.message.startswith(
        "Fitted IC transmit-function pins U1.1, U2.1 share one schematic net"
    )
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "channels": ("USART1", "USART2"),
        "functions": ("USART1_TX", "USART2_TX"),
        "pins": ("U1.1", "U2.1"),
        "pin_types": ("passive", "passive"),
        "net": ("SERIAL_TX_BUS",),
    }
    default = evaluate("synthetic-serial-tx-sharing", coach(netlist), DesignLintPolicy())
    default_finding = _findings(default)[0]
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_one_transmitter_with_multiple_receiver_peers_is_a_valid_control() -> None:
    netlist = serial_tx_output_netlist(references=("U1", "U2", "U3"))
    functions = {"U1.1": "USART1_TX", "U2.1": "USART2_RX", "U3.1": "USART3_RX"}

    assert not _findings(_report(netlist.model_copy(update={"pin_functions": functions})))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_output_conflicts_and_ambiguous_or_unsupported_groups_are_skipped() -> None:
    fault = serial_tx_output_netlist()
    output_conflict = fault.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U2.1": "output"}}
    )
    dnp = fault.model_copy(update={"dnp_components": ("U2",)})
    open_pin = fault.model_copy(update={"nets": {"SERIAL_TX_BUS": ("U1.1",)}})
    multiple_assignment = fault.model_copy(update={"nets": {**fault.nets, "SECOND_NET": ("U2.1",)}})
    missing_type = fault.model_copy(update={"pin_electrical_types": {"U1.1": "passive"}})
    connectors = serial_tx_output_netlist(references=("J1", "J2"))
    single_component = fault.model_copy(
        update={
            "components": {"U1": fault.components["U1"]},
            "nets": {"SERIAL_TX_BUS": ("U1.1", "U1.2")},
            "pin_functions": {"U1.1": "USART1_TX", "U1.2": "USART2_TX"},
            "pin_electrical_types": {"U1.1": "passive", "U1.2": "passive"},
            "component_pin_numbers": {"U1": ("1", "2")},
        }
    )

    assert serial_tx_output_sharing_candidates(output_conflict) == ()
    assert serial_tx_output_sharing_candidates(dnp) == ()
    assert serial_tx_output_sharing_candidates(open_pin) == ()
    assert serial_tx_output_sharing_candidates(multiple_assignment) == ()
    assert serial_tx_output_sharing_candidates(missing_type) == ()
    assert serial_tx_output_sharing_candidates(connectors) == ()
    assert serial_tx_output_sharing_candidates(single_component) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_ignore_an_intentional_shared_net() -> None:
    netlist = serial_tx_output_netlist()
    reviewed = _findings(_report(netlist))[0]
    blocked = _findings(_report(netlist, "block"))[0]
    disabled = _findings(_report(netlist, "off"))[0]
    ignored = _findings(
        _report(
            netlist,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=reviewed.fingerprint,
                reason="Synthetic board intentionally tri-states the shared line",
            ),
        )
    )[0]

    assert _report(netlist, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ordering_is_stable_and_separating_one_transmitter_clears_the_finding() -> None:
    netlist = serial_tx_output_netlist()
    reordered = netlist.model_copy(
        update={
            "components": dict(reversed(tuple(netlist.components.items()))),
            "nets": dict(reversed(tuple(netlist.nets.items()))),
            "pin_functions": dict(reversed(tuple(netlist.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(netlist.pin_electrical_types.items()))),
        }
    )
    separated = netlist.model_copy(update={"nets": {"TX_A": ("U1.1",), "TX_B": ("U2.1",)}})
    first = _findings(_report(netlist))[0]
    second = _findings(_report(reordered))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert not _findings(_report(separated))
