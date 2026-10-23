"""Focused I2C SDA/SCL same-net review regressions."""

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
from kicad_tooling.hwrepo.i2c_same_net import i2c_sda_scl_same_net_candidates
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i2c_signal_label import (
    i2c_signal_label_netlist,
    i2c_signal_same_net_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

RULE_ID = "bus.i2c_sda_scl_same_net"


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
                reason="Review synthetic I2C signal assignment",
            ),
        ),
        ignores=() if ignore is None else (ignore,),
    )
    return evaluate("synthetic-i2c-sda-scl-same-net", coach(netlist), policy)


def _findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_sda_and_scl_on_one_net_prompt_review_while_distinct_lines_are_control() -> None:
    fault = i2c_signal_same_net_netlist()
    default_finding = _findings(
        evaluate("synthetic-i2c-sda-scl-same-net", coach(fault), DesignLintPolicy())
    )[0]
    reviewed = _findings(_report(fault))[0]

    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    assert reviewed.subject == "U1: I2C SDA/SCL pins share I2C_SHARED"
    assert reviewed.evidence == {
        "component": ("U1",),
        "SDA_pin": ("U1.1",),
        "SCL_pin": ("U1.2",),
        "net": ("I2C_SHARED",),
    }
    assert not _findings(_report(i2c_signal_label_netlist()))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_dnp_open_ambiguous_duplicate_role_and_incomplete_inventory_are_skipped() -> None:
    fault = i2c_signal_same_net_netlist()
    dnp = fault.model_copy(update={"dnp_components": ("U1",)})
    open_scl = fault.model_copy(update={"nets": {"I2C_SHARED": ("U1.1",)}})
    multiply_assigned = fault.model_copy(update={"nets": {**fault.nets, "OTHER": ("U1.1",)}})
    duplicate_sda = fault.model_copy(
        update={
            "pin_functions": {**fault.pin_functions, "U1.3": "SDA"},
            "component_pin_numbers": {"U1": ("1", "2", "3")},
            "nets": {"I2C_SHARED": ("U1.1", "U1.2", "U1.3")},
        }
    )
    missing_inventory = fault.model_copy(update={"component_pin_numbers": {}})
    stale_pin_inventory = fault.model_copy(
        update={"pin_functions": {**fault.pin_functions, "U1.3": "SDA"}}
    )

    for source in (
        dnp,
        open_scl,
        multiply_assigned,
        duplicate_sda,
        missing_inventory,
        stale_pin_inventory,
    ):
        assert i2c_sda_scl_same_net_candidates(source) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unrecognized_and_indexed_i2c_functions_are_not_classified() -> None:
    source = i2c_signal_same_net_netlist()
    vendor_names = source.model_copy(
        update={"pin_functions": {"U1.1": "TWI_DATA", "U1.2": "TWI_CLOCK"}}
    )
    indexed_names = source.model_copy(
        update={"pin_functions": {"U1.1": "I2C1_SDA", "U1.2": "I2C1_SCL"}}
    )
    non_ic_reference = source.model_copy(
        update={
            "components": {"J1": source.components["U1"]},
            "nets": {"I2C_SHARED": ("J1.1", "J1.2")},
            "component_symbols": {"J1": "Synthetic:Controller"},
            "pin_functions": {"J1.1": "SDA", "J1.2": "SCL"},
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )

    assert not _findings(_report(vendor_names))
    assert not _findings(_report(indexed_names))
    assert not _findings(_report(non_ic_reference))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_native_output_pins_are_left_to_the_erc_conflict_check() -> None:
    fault = i2c_signal_same_net_netlist()
    outputs = fault.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U1.2": "output"}}
    )
    one_output = fault.model_copy(
        update={"pin_electrical_types": {"U1.1": "output", "U1.2": "input"}}
    )

    assert not i2c_sda_scl_same_net_candidates(outputs)
    assert _findings(_report(one_output))


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_policy_can_promote_disable_or_exactly_ignore_candidate() -> None:
    fault = i2c_signal_same_net_netlist()
    finding = _findings(_report(fault))[0]
    blocked = _findings(_report(fault, "block"))[0]
    disabled = _findings(_report(fault, "off"))[0]
    ignored = _findings(
        _report(
            fault,
            ignore=DesignLintIgnore(
                rule_id=RULE_ID,
                fingerprint=fingerprint(finding),
                reason="Synthetic controller intentionally uses one signal wire",
            ),
        )
    )[0]

    assert _report(fault, "block").status == "FAIL"
    assert blocked.mode == "block"
    assert disabled.disposition == "RULE_OFF"
    assert ignored.disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ordering_is_stable_and_separating_the_signals_clears_candidate() -> None:
    fault = i2c_signal_same_net_netlist()
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
    assert not _findings(_report(i2c_signal_label_netlist()))
