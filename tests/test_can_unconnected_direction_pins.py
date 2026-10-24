"""Focused regressions for partially assigned CAN/FDCAN direction channels."""

from __future__ import annotations

from typing import Literal

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.models import (
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.can_unconnected_direction_pins import (
    can_unconnected_direction_netlist,
)

RULE_ID = "bus.can_unconnected_direction_pin"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _report(
    source: NetlistContract | None = None,
    mode: Literal["review", "block", "off"] | None = None,
    ignores: tuple[DesignLintIgnore, ...] = (),
) -> DesignLintReport:
    selected = can_unconnected_direction_netlist() if source is None else source
    overrides = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="test policy"),)
    )
    return evaluate(
        "synthetic-can-unconnected-direction-pin",
        coach(selected),
        DesignLintPolicy(rules=overrides, ignores=ignores),
    )


def test_open_can_direction_pin_emits_exact_pair_and_net_evidence_when_enabled() -> None:
    report = _report(mode="review")
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)

    assert finding.subject == "U1.2: CAN1_RX"
    assert finding.evidence == {
        "U1.2": (),
        "function": ("CAN1_RX",),
        "can_role": ("RX",),
        "can_channel": ("can:index1",),
        "paired_pin": ("U1.1",),
        "paired_net": ("CAN1_TX_NET",),
    }
    assert "one-way" in finding.message
    assert "do not establish channel use or PCB routing" in finding.message


def test_rule_defaults_off_and_supports_review_block_off_and_exact_ignore() -> None:
    default = next(item for item in _report().findings if item.rule_id == RULE_ID)
    assert (default.mode, default.disposition) == ("off", "RULE_OFF")
    assert _report(mode="review").status == "REVIEW"
    assert _report(mode="block").status == "FAIL"
    assert _report(mode="off").status == _report().status
    ignored = _report(
        mode="review",
        ignores=(
            DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=default.fingerprint,
                reason="reviewed one-way CAN channel",
            ),
        ),
    )
    ignored_findings = [item for item in ignored.findings if item.rule_id == RULE_ID]
    assert len(ignored_findings) == 1
    assert ignored_findings[0].disposition == "IGNORED"


@pytest.mark.parametrize(
    ("functions", "open_pin", "role", "channel"),
    (
        pytest.param(
            {"U1.1": "CAN_TXD", "U1.2": "CAN_RXD"},
            "U1.2",
            "RX",
            "can:default",
            id="can-txd-rxd",
        ),
        pytest.param(
            {"U1.1": "FDCAN2_TXD", "U1.2": "FDCAN2_RXD"},
            "U1.2",
            "RX",
            "fdcan:index2",
            id="fdcan-indexed",
        ),
        pytest.param(
            {"U1.1": "TX_CAN1", "U1.2": "RX_CAN1"},
            "U1.1",
            "TX",
            "can:index1",
            id="can-suffix-aliases",
        ),
    ),
)
def test_bounded_can_direction_aliases_keep_role_and_channel_evidence(
    functions: dict[str, str], open_pin: str, role: str, channel: str
) -> None:
    source = can_unconnected_direction_netlist(open_pins=(open_pin,), functions=functions)
    finding = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )

    assert finding.evidence["can_role"] == (role,)
    assert finding.evidence["can_channel"] == (channel,)


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(can_unconnected_direction_netlist(open_pins=()), id="connected-control"),
        pytest.param(
            can_unconnected_direction_netlist(open_pins=("U1.1", "U1.2")),
            id="entire-channel-open",
        ),
        pytest.param(
            can_unconnected_direction_netlist(functions={"U1.1": "CAN1_TX", "U1.2": "CAN2_RX"}),
            id="different-channels",
        ),
        pytest.param(
            can_unconnected_direction_netlist(dnp_components=("U1",)),
            id="dnp-component",
        ),
        pytest.param(
            can_unconnected_direction_netlist(functions={"U1.1": "TX", "U1.2": "RX"}),
            id="generic-serial-aliases",
        ),
        pytest.param(
            can_unconnected_direction_netlist().model_copy(update={"component_pin_numbers": {}}),
            id="missing-native-pin-inventory",
        ),
        pytest.param(
            can_unconnected_direction_netlist().model_copy(
                update={"component_pin_numbers": {"U1": ("1",)}}
            ),
            id="inventory-missing-open-pin",
        ),
        pytest.param(
            can_unconnected_direction_netlist().model_copy(
                update={"component_pin_numbers": {"U1": ("1", "2", "3")}}
            ),
            id="inventory-with-missing-function-metadata",
        ),
        pytest.param(
            can_unconnected_direction_netlist(
                functions={"U1.1": "CAN1_TX", "U1.2": "CAN1_RX", "U1.3": "CAN1_RX"},
                pin_numbers=("1", "2", "3"),
            ),
            id="ambiguous-repeated-role",
        ),
    ),
)
def test_connected_unused_dnp_ambiguous_or_unsupported_shapes_are_quiet(
    source: NetlistContract,
) -> None:
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_multi_net_pair_assignment_is_ambiguous_and_quiet() -> None:
    source = can_unconnected_direction_netlist().model_copy(
        update={
            "nets": {
                "CAN1_TX_NET": ("U1.1",),
                "OTHER": ("U1.1",),
            }
        }
    )
    assert not any(item.rule_id == RULE_ID for item in _report(source, mode="review").findings)


def test_ordering_is_stable_and_assigning_open_pin_clears_candidate() -> None:
    source = can_unconnected_direction_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "components": dict(reversed(tuple(source.components.items()))),
        }
    )
    original = next(
        item for item in _report(source, mode="review").findings if item.rule_id == RULE_ID
    )
    repeated = next(
        item for item in _report(reordered, mode="review").findings if item.rule_id == RULE_ID
    )
    repaired = source.model_copy(update={"nets": {**source.nets, "CAN1_RX_NET": ("U1.2",)}})

    assert (repeated.fingerprint, repeated.evidence) == (original.fingerprint, original.evidence)
    assert not any(item.rule_id == RULE_ID for item in _report(repaired, mode="review").findings)
