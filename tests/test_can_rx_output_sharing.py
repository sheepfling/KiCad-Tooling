"""Review regressions for explicitly identified CAN receiver outputs on one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.can_rx_output_sharing import can_rx_output_sharing_candidates
from kicad_tooling.hwrepo.design_lint import evaluate, rule_catalog
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.can_rx_output_sharing import can_rx_output_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.can_rx_outputs_share_net"


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
                reason="Review synthetic CAN receiver-output sharing",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-can-rx-output-sharing", coach(netlist), policy)


def _findings(report) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.architecture
def test_catalog_owns_can_rx_rule_in_its_theme_module() -> None:
    rule = next(item for item in rule_catalog().rules if item.rule_id == RULE_ID)

    assert rule.theme == "interfaces"
    assert rule.implementation_owner == (
        "kicad_tooling/hwrepo/can_rx_output_sharing.py#can_rx_output_sharing_candidates"
    )
    assert rule.implementation_owner in rule.implementation_refs
    assert (
        "kicad_tooling/hwrepo/signal_pair_output_sharing.py#signal_output_sharing_groups"
        in rule.implementation_refs
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_fitted_can_receiver_outputs_on_one_net_are_reviewed() -> None:
    netlist = can_rx_output_netlist()
    finding = _findings(_report(netlist))[0]

    assert finding.subject == "U1, U2: CAN receiver outputs share CAN_RX_SHARED"
    assert finding.evidence == {
        "components": ("U1", "U2"),
        "channels": ("CAN module", "CAN module"),
        "functions": ("RXD", "RXD"),
        "pins": ("U1.1", "U2.1"),
        "pin_types": ("passive", "passive"),
        "net": ("CAN_RX_SHARED",),
        "identity_basis": ("Synthetic:CAN_Transceiver CAN transceiver module",),
    }
    assert _findings(
        evaluate("synthetic-can-rx-output-sharing", coach(netlist), DesignLintPolicy())
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_protocol_aliases_are_bounded_and_split_receivers_are_valid_controls() -> None:
    aliases = can_rx_output_netlist(receiver_functions=("CAN1_RXD", "RXD_FDCAN2"))
    separate = can_rx_output_netlist(shared=False)
    unrelated = can_rx_output_netlist().model_copy(
        update={
            "components": {
                reference: component.model_copy(update={"value": "UART bridge"})
                for reference, component in can_rx_output_netlist().components.items()
            },
            "component_symbols": {"U1": "Synthetic:UART_Module", "U2": "Synthetic:UART_Module"},
            "pin_functions": {"U1.1": "UART_RX", "U2.1": "UART_RX", "U1.2": "TXD", "U2.2": "TXD"},
        }
    )

    assert len(can_rx_output_sharing_candidates(aliases)) == 1
    assert not can_rx_output_sharing_candidates(separate)
    assert not can_rx_output_sharing_candidates(unrelated)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_and_incomplete_peer_evidence_suppress_the_shared_net() -> None:
    source = can_rx_output_netlist(references=("U1", "U2", "U3"))
    dnp = can_rx_output_netlist(dnp_references=("U2",))
    open_pin = source.model_copy(
        update={
            "nets": {key: value for key, value in source.nets.items() if key != "CAN_RX_SHARED"}
        }
    )
    multiply_assigned = source.model_copy(
        update={
            "nets": {
                **source.nets,
                "OTHER_RX": ("U3.1",),
            }
        }
    )
    missing_inventory = can_rx_output_netlist().model_copy(
        update={"component_pin_numbers": {"U1": ("1", "2")}}
    )
    duplicate_inventory = can_rx_output_netlist().model_copy(
        update={"component_pin_numbers": {"U1": ("1", "1", "2")}}
    )
    duplicate_role = source.model_copy(
        update={
            "nets": {**source.nets, "CAN_RX_SHARED": ("U1.1", "U1.3", "U2.1", "U3.1")},
            "pin_functions": {**source.pin_functions, "U1.3": "CAN1_RXD"},
            "pin_electrical_types": {**source.pin_electrical_types, "U1.3": "passive"},
            "component_pin_numbers": {**source.component_pin_numbers, "U1": ("1", "2", "3")},
        }
    )

    for case in (
        dnp,
        open_pin,
        multiply_assigned,
        missing_inventory,
        duplicate_inventory,
        duplicate_role,
    ):
        assert not can_rx_output_sharing_candidates(case)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_native_output_conflicts_return_nets_and_unsupported_pin_types_are_skipped() -> None:
    source = can_rx_output_netlist()
    native_conflict = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U2.1": "output"}}
    )
    return_net = source.model_copy(
        update={
            "nets": {
                "GND": source.nets["CAN_RX_SHARED"],
                **{key: value for key, value in source.nets.items() if key != "CAN_RX_SHARED"},
            }
        }
    )
    unknown_type = source.model_copy(
        update={"pin_electrical_types": {"U1.1": "input", "U2.1": "input"}}
    )

    assert not can_rx_output_sharing_candidates(native_conflict)
    assert not can_rx_output_sharing_candidates(return_net)
    assert not can_rx_output_sharing_candidates(unknown_type)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_ignore_the_exact_finding() -> None:
    netlist = can_rx_output_netlist()
    finding = _findings(_report(netlist))[0]
    blocked = _findings(_report(netlist, "block"))[0]
    disabled = _findings(_report(netlist, "off"))[0]
    ignored = _findings(
        _report(
            netlist,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=finding.fingerprint,
                reason="Synthetic example intentionally shares the receiver output net",
            ),
        )
    )[0]

    assert _report(netlist, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_fingerprint_is_order_stable_and_separating_outputs_clears_the_finding() -> None:
    source = can_rx_output_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    separate = source.model_copy(
        update={
            "nets": {
                "CAN1_RX": ("U1.1",),
                "CAN2_RX": ("U2.1",),
                "CAN1_TX": ("U1.2",),
                "CAN2_TX": ("U2.2",),
            }
        }
    )
    first = _findings(_report(source))[0]
    second = _findings(_report(reordered))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert not _findings(_report(separate))
