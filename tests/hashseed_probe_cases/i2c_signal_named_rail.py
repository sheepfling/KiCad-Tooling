"""Focused hash-seed reports for I2C signal pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i2c_signal_label import i2c_signal_label_netlist
from tests.design_lint_fixtures.i2c_signal_named_rail import i2c_signal_on_named_rail_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-i2c-signal-named-rail-fault",
        coach(i2c_signal_on_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-i2c-signal-named-rail-control",
        coach(i2c_signal_label_netlist()),
        DesignLintPolicy(),
    )
    return {
        "i2c_signal_named_rail_fault": fault.model_dump(mode="json"),
        "i2c_signal_named_rail_control": control.model_dump(mode="json"),
    }
