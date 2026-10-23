"""Focused review regressions for CAN TX functions sharing one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.can_tx_output_sharing import can_tx_output_sharing_candidates
from kicad_tooling.hwrepo.design_lint import evaluate, rule_catalog
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.can_tx_output_sharing import can_tx_output_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.can_tx_outputs_share_net"


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
                reason="Review synthetic CAN transmit pin sharing",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-can-tx-output-sharing", coach(netlist), policy)


def _findings(report) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.architecture
def test_catalog_owns_can_tx_rule_in_its_theme_module() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/can_tx_output_sharing.py#can_tx_output_sharing_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/signal_pair_tx_output_sharing.py#tx_output_sharing_groups"
        in rule.implementation_refs
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_can_tx_functions_on_one_net_are_reviewed() -> None:
    netlist = can_tx_output_netlist()
    finding = _findings(_report(netlist))[0]

    assert finding.subject == "U1, U2: CAN TX functions share CAN_TX_SHARED"
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "channels": ("CAN channel 1", "CAN channel 2"),
        "functions": ("CAN1_TX", "CAN2_TX"),
        "pins": ("U1.1", "U2.1"),
        "pin_types": ("passive", "passive"),
        "net": ("CAN_TX_SHARED",),
    }
    default = evaluate("synthetic-can-tx-output-sharing", coach(netlist), DesignLintPolicy())
    assert _findings(default)[0].disposition == "RULE_OFF"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_single_tx_to_receiver_and_split_tx_nets_are_valid_controls() -> None:
    source = can_tx_output_netlist()
    receiver_control = source.model_copy(
        update={
            "nets": {
                "CAN_CONTROLLER_LINK": ("U1.1", "U2.2"),
                "CAN1_RX": ("U1.2",),
                "CAN2_TX": ("U2.1",),
            }
        }
    )
    separate = can_tx_output_netlist(shared=False)

    assert not can_tx_output_sharing_candidates(receiver_control)
    assert not _findings(_report(receiver_control))
    assert not _findings(_report(separate))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_can_aliases_are_bounded_and_uart_roles_are_not_included() -> None:
    fdcan = can_tx_output_netlist(tx_functions=("FDCAN2_TXD", "TXD_FDCAN2"))
    uart = can_tx_output_netlist(tx_functions=("USART1_TX", "USART2_TX"))

    assert len(can_tx_output_sharing_candidates(fdcan)) == 1
    assert not can_tx_output_sharing_candidates(uart)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_duplicate_and_incomplete_pin_inventory_are_skipped() -> None:
    source = can_tx_output_netlist()
    dnp = can_tx_output_netlist(dnp_references=("U2",))
    open_pin = source.model_copy(update={"nets": {"CAN_TX_SHARED": ("U1.1",)}})
    multiply_assigned = source.model_copy(
        update={"nets": {**source.nets, "CAN_TX_OTHER": ("U2.1",)}}
    )
    missing_inventory = source.model_copy(update={"component_pin_numbers": {}})
    incomplete_inventory = source.model_copy(
        update={"component_pin_numbers": {"U1": ("1", "2"), "U2": ("2",)}}
    )
    duplicate_tx = source.model_copy(
        update={
            "nets": {"CAN_TX_SHARED": ("U1.1", "U1.3", "U2.1")},
            "pin_functions": {**source.pin_functions, "U1.3": "CAN1_TX"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.3": "passive"},
            "component_pin_numbers": {"U1": ("1", "2", "3"), "U2": ("1", "2")},
        }
    )

    for case in (
        dnp,
        open_pin,
        multiply_assigned,
        missing_inventory,
        incomplete_inventory,
        duplicate_tx,
    ):
        assert not can_tx_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connectors_unknown_pin_types_and_native_output_conflicts_are_skipped() -> None:
    source = can_tx_output_netlist()
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"], "J2": source.components["U2"]},
            "component_symbols": {"J1": "Connector:Conn_01x02", "J2": "Connector:Conn_01x02"},
            "nets": {"CAN_TX_SHARED": ("J1.1", "J2.1")},
            "pin_functions": {"J1.1": "CAN1_TX", "J2.1": "CAN2_TX"},
            "pin_electrical_types": {"J1.1": "passive", "J2.1": "passive"},
            "component_pin_numbers": {"J1": ("1", "2"), "J2": ("1", "2")},
        }
    )
    unknown = source.model_copy(update={"pin_electrical_types": {"U1.1": "passive"}})
    outputs = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U2.1": "output"}}
    )

    assert not can_tx_output_sharing_candidates(connector)
    assert not can_tx_output_sharing_candidates(unknown)
    assert not can_tx_output_sharing_candidates(outputs)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_supports_block_off_and_exact_finding_ignore() -> None:
    netlist = can_tx_output_netlist()
    finding = _findings(_report(netlist))[0]
    blocked = _findings(_report(netlist, "block"))[0]
    disabled = _findings(_report(netlist, "off"))[0]
    ignored = _findings(
        _report(
            netlist,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic example intentionally shares the TX net",
            ),
        )
    )[0]

    assert _report(netlist, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_order_is_stable_and_separating_one_tx_clears_the_finding() -> None:
    source = can_tx_output_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    separate = source.model_copy(
        update={
            "nets": {
                "CAN_TX1": ("U1.1",),
                "CAN_TX2": ("U2.1",),
                "CAN1_RX": ("U1.2",),
                "CAN2_RX": ("U2.2",),
            }
        }
    )
    first = _findings(_report(source))[0]
    second = _findings(_report(reordered))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert not _findings(_report(separate))
