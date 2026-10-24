"""Focused regressions for I3C SDA/SCL assigned to one net."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate, fingerprint
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.i3c_same_net import i3c_sda_scl_same_net_candidates
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i3c_same_net import (
    i3c_distinct_lines_netlist,
    i3c_same_net_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.i3c_sda_scl_same_net"


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
                reason="Review synthetic I3C signal assignment",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-i3c-sda-scl-same-net", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_same_net_i3c_pair_prompts_while_distinct_lines_are_control() -> None:
    fault = i3c_same_net_netlist()
    default_finding = _findings(
        evaluate("synthetic-i3c-sda-scl-same-net", coach(fault), DesignLintPolicy())
    )[0]
    finding = _findings(_report(fault))[0]

    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    assert finding.subject == "U1: I3C1 SDA/SCL pins share I3C_SHARED"
    assert finding.evidence == {
        "component": ("U1",),
        "channel": ("1",),
        "SDA_pin": ("U1.1",),
        "SCL_pin": ("U1.2",),
        "net": ("I3C_SHARED",),
    }
    assert "not prove the part implements I3C" in finding.message
    assert not _findings(_report(i3c_distinct_lines_netlist()))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_duplicate_mismatched_channel_and_incomplete_inventory_are_skipped() -> None:
    fault = i3c_same_net_netlist()
    dnp = fault.model_copy(update={"dnp_components": ("U1",)})
    open_scl = fault.model_copy(update={"nets": {"I3C_SHARED": ("U1.1",)}})
    multiply_assigned = fault.model_copy(update={"nets": {**fault.nets, "OTHER": ("U1.1",)}})
    duplicate_sda = fault.model_copy(
        update={
            "pin_functions": {**fault.pin_functions, "U1.3": "I3C1_SDA"},
            "component_pin_numbers": {"U1": ("1", "2", "3")},
            "nets": {"I3C_SHARED": ("U1.1", "U1.2", "U1.3")},
        }
    )
    mismatched_channel = fault.model_copy(
        update={"pin_functions": {"U1.1": "I3C1_SDA", "U1.2": "I3C2_SCL"}}
    )
    missing_inventory = fault.model_copy(update={"component_pin_numbers": {}})
    stale_inventory = fault.model_copy(
        update={"pin_functions": {**fault.pin_functions, "U1.3": "I3C1_SDA"}}
    )

    for source in (
        dnp,
        open_scl,
        multiply_assigned,
        duplicate_sda,
        mismatched_channel,
        missing_inventory,
        stale_inventory,
    ):
        assert not _findings(_report(source))
        assert i3c_sda_scl_same_net_candidates(source) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_multiple_unique_channels_are_checked_independently() -> None:
    source = i3c_same_net_netlist().model_copy(
        update={
            "pin_functions": {
                "U1.1": "I3C1_SDA",
                "U1.2": "I3C1_SCL",
                "U1.3": "I3C2_SDA",
                "U1.4": "I3C2_SCL",
            },
            "component_pin_numbers": {"U1": ("1", "2", "3", "4")},
            "nets": {
                "I3C_SHARED": ("U1.1", "U1.2"),
                "I3C2_SDA": ("U1.3",),
                "I3C2_SCL": ("U1.4",),
            },
        }
    )

    findings = _findings(_report(source))
    assert tuple(item.subject for item in findings) == ("U1: I3C1 SDA/SCL pins share I3C_SHARED",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_native_output_pins_are_left_to_the_erc_conflict_check() -> None:
    fault = i3c_same_net_netlist()
    outputs = fault.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U1.2": "output"}}
    )
    one_output = fault.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U1.2": "input"}}
    )

    assert not i3c_sda_scl_same_net_candidates(outputs)
    assert _findings(_report(one_output))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_policy_can_block_disable_or_exactly_ignore_candidate() -> None:
    fault = i3c_same_net_netlist()
    finding = _findings(_report(fault))[0]
    blocked = _findings(_report(fault, "block"))[0]
    disabled = _findings(_report(fault, "off"))[0]
    ignored = _findings(
        _report(
            fault,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=fingerprint(finding),
                reason="Synthetic interface intentionally shares one net",
            ),
        )
    )[0]

    assert _report(fault, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mapping_order_is_stable_and_separating_lines_clears_candidate() -> None:
    fault = i3c_same_net_netlist()
    reordered = fault.model_copy(
        update={
            "components": dict(reversed(tuple(fault.components.items()))),
            "nets": dict(reversed(tuple(fault.nets.items()))),
            "pin_functions": dict(reversed(tuple(fault.pin_functions.items()))),
        }
    )
    first = _findings(_report(fault))[0]
    second = _findings(_report(reordered))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)
    assert not _findings(_report(i3c_distinct_lines_netlist()))
