"""Review fitted resistors bridging recognized I2C SDA/SCL nets."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.i2c_sda_scl_resistive_bridge import (
    RULE_ID,
    i2c_sda_scl_resistive_bridge_candidates,
)
from kicad_tooling.hwrepo.models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i2c_sda_scl_resistive_bridge import (
    i2c_sda_scl_resistive_bridge_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


def _report(
    source: NetlistContract,
    *,
    mode: str | None = None,
    ignore: DesignLintIgnore | None = None,
) -> DesignLintReport:
    overrides = (
        ()
        if mode is None
        else (DesignLintRuleOverride(rule_id=RULE_ID, mode=mode, reason="Review I2C topology"),)
    )
    return evaluate(
        "synthetic-i2c-sda-scl-resistive-bridge",
        coach(source),
        DesignLintPolicy(rules=overrides, ignores=() if ignore is None else (ignore,)),
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_direct_resistor_across_separate_i2c_signal_nets_is_reviewed() -> None:
    source = i2c_sda_scl_resistive_bridge_netlist(value="90R")
    (candidate,) = i2c_sda_scl_resistive_bridge_candidates(source)
    finding = next(item for item in _report(source).findings if item.rule_id == RULE_ID)

    assert candidate.subject == ("U1: I2C SDA/SCL nets I2C_SDA and I2C_SCL are bridged by R1")
    assert candidate.evidence == {
        "component": ("U1",),
        "SDA_pin": ("U1.1",),
        "SCL_pin": ("U1.2",),
        "SDA_net": ("I2C_SDA",),
        "SCL_net": ("I2C_SCL",),
        "resistor": ("R1",),
        "resistance_ohms": ("90Ω",),
    }
    assert finding.mode == "review"
    assert finding.disposition == "OPEN"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_absent_or_inapplicable_resistors_are_controls() -> None:
    cases = (
        i2c_sda_scl_resistive_bridge_netlist(bridge="none"),
        i2c_sda_scl_resistive_bridge_netlist(resistor_dnp=True),
        i2c_sda_scl_resistive_bridge_netlist(bridge="capacitor"),
        i2c_sda_scl_resistive_bridge_netlist(bridge="series", value="33R"),
        i2c_sda_scl_resistive_bridge_netlist(bridge="other-net", value="10k"),
    )
    assert all(not i2c_sda_scl_resistive_bridge_candidates(source) for source in cases)

    (zero_ohm,) = i2c_sda_scl_resistive_bridge_candidates(
        i2c_sda_scl_resistive_bridge_netlist(value="0R")
    )
    assert zero_ohm.evidence["resistance_ohms"] == ("0Ω",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_incomplete_or_ambiguous_endpoint_and_resistor_evidence_stays_quiet() -> None:
    source = i2c_sda_scl_resistive_bridge_netlist()
    controls = (
        source.model_copy(update={"nets": {"I2C_SDA": ("R1.1",), "I2C_SCL": ("R1.2",)}}),
        source.model_copy(
            update={
                "component_pin_numbers": {
                    **source.component_pin_numbers,
                    "U1": ("1",),
                }
            }
        ),
        source.model_copy(
            update={
                "pin_functions": {**source.pin_functions, "U1.3": "SDA"},
                "component_pin_numbers": {**source.component_pin_numbers, "U1": ("1", "2", "3")},
                "nets": {**source.nets, "I2C_SDA": (*source.nets["I2C_SDA"], "U1.3")},
            }
        ),
        source.model_copy(
            update={
                "component_pin_numbers": {
                    **source.component_pin_numbers,
                    "R1": ("1",),
                }
            }
        ),
        source.model_copy(
            update={
                "components": {
                    **source.components,
                    "R1": source.components["R1"].model_copy(update={"value": "unknown"}),
                }
            }
        ),
    )
    assert all(not i2c_sda_scl_resistive_bridge_candidates(item) for item in controls)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_result_order_is_stable_and_policy_remains_configurable() -> None:
    source = i2c_sda_scl_resistive_bridge_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
        }
    )
    assert i2c_sda_scl_resistive_bridge_candidates(source) == (
        i2c_sda_scl_resistive_bridge_candidates(reordered)
    )

    report = _report(source)
    default = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert _report(source, mode="block").status == "FAIL"
    off = next(item for item in _report(source, mode="off").findings if item.rule_id == RULE_ID)
    assert off.disposition == "RULE_OFF"
    ignore = DesignLintIgnore(
        rule_id=RULE_ID,
        fingerprint=default.fingerprint,
        reason="Synthetic intentional resistor network",
    )
    ignored = next(
        item for item in _report(source, ignore=ignore).findings if item.rule_id == RULE_ID
    )
    assert ignored.disposition == "IGNORED"
