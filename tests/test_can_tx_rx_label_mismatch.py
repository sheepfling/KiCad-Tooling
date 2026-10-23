"""Focused review regressions for CAN TX/RX pin and net-label mismatches."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.can_tx_rx_label_mismatch import (
    can_tx_rx_label_mismatch_candidates,
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

RULE_ID = "bus.can_tx_rx_label_mismatch"


def _netlist(*, crossed: bool = True) -> NetlistContract:
    source = can_tx_rx_same_net_netlist(shared=False)
    nets = (
        {"CAN1_RX": ("U1.1",), "CAN1_TX": ("U1.2",)}
        if crossed
        else {"CAN1_TX": ("U1.1",), "CAN1_RX": ("U1.2",)}
    )
    return source.model_copy(update={"nets": nets})


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
                reason="Review synthetic CAN direction labels",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-can-tx-rx-labels", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_explicit_can_tx_rx_functions_on_opposite_role_labels_are_reviewed() -> None:
    findings = can_tx_rx_label_mismatch_candidates(_netlist())

    assert tuple(item.subject for item in findings) == (
        "U1.1: CAN1_TX on CAN1_RX",
        "U1.2: CAN1_RX on CAN1_TX",
    )
    assert findings[0].evidence["pin_role"] == ("tx",)
    assert findings[0].evidence["net_role"] == ("rx",)
    assert findings[1].evidence["pin_role"] == ("rx",)
    assert findings[1].evidence["net_role"] == ("tx",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_matching_labels_and_unbounded_generic_names_are_controls() -> None:
    source = _netlist(crossed=False)
    generic_functions = source.model_copy(update={"pin_functions": {"U1.1": "TXD", "U1.2": "RXD"}})
    generic_labels = source.model_copy(update={"nets": {"TX": ("U1.1",), "RX": ("U1.2",)}})
    mixed_protocol = source.model_copy(
        update={"nets": {"UART1_RX": ("U1.1",), "UART1_TX": ("U1.2",)}}
    )

    assert not can_tx_rx_label_mismatch_candidates(source)
    assert not can_tx_rx_label_mismatch_candidates(generic_functions)
    assert not can_tx_rx_label_mismatch_candidates(generic_labels)
    assert not can_tx_rx_label_mismatch_candidates(mixed_protocol)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_aliases_channels_and_native_assignment_boundaries_are_bounded() -> None:
    source = _netlist(crossed=False)
    one_mismatch = source.model_copy(update={"nets": {"CAN1_RX": ("U1.1", "U1.2")}})
    aliases = source.model_copy(
        update={
            "pin_functions": {"U1.1": "TXD_FDCAN1", "U1.2": "RXD_FDCAN1"},
            "nets": {"FDCAN1_RXD": ("U1.1",), "FDCAN1_TXD": ("U1.2",)},
        }
    )
    dnp = one_mismatch.model_copy(update={"dnp_components": ("U1",)})
    missing_inventory = one_mismatch.model_copy(update={"component_pin_numbers": {}})
    inventory_mismatch = one_mismatch.model_copy(update={"component_pin_numbers": {"U1": ("3",)}})
    open_pin = one_mismatch.model_copy(update={"nets": {"CAN1_RX": ("U1.2",)}})
    multiply_assigned = source.model_copy(
        update={"nets": {**one_mismatch.nets, "CAN1_RX_AUX": ("U1.1",)}}
    )
    connector = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "nets": {"CAN1_RX": ("J1.1", "J1.2")},
            "pin_functions": {"J1.1": "CAN1_TX", "J1.2": "CAN1_RX"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )

    assert len(can_tx_rx_label_mismatch_candidates(aliases)) == 2
    for unsupported in (
        dnp,
        missing_inventory,
        inventory_mismatch,
        open_pin,
        multiply_assigned,
        connector,
    ):
        assert not can_tx_rx_label_mismatch_candidates(unsupported)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_review_block_disable_or_ignore_exact_assignments() -> None:
    source = _netlist()
    review_findings = _findings(_report(source))
    blocked = _findings(_report(source, "block"))
    disabled = _findings(_report(source, "off"))
    ignored = _findings(
        _report(
            source,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=review_findings[0].fingerprint,
                reason="Reviewed endpoint naming convention",
            ),
        )
    )

    assert _report(source).status == "REVIEW"
    assert _report(source, "block").status == "FAIL"
    assert all(item.mode == "block" for item in blocked)
    assert all(item.disposition == "RULE_OFF" for item in disabled)
    assert ignored[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_findings_are_order_stable_and_correction_clears_them() -> None:
    source = _netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )

    first = _findings(_report(source))
    second = _findings(_report(reordered))
    assert tuple(item.fingerprint for item in first) == tuple(item.fingerprint for item in second)
    assert not can_tx_rx_label_mismatch_candidates(_netlist(crossed=False))
