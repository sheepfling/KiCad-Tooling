"""Cross-process report cases for I2S named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i2s_signal_named_rail import i2s_signal_named_rail_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-i2s-signal-named-rail-fault",
        coach(i2s_signal_named_rail_netlist(rail_pins={"1": "GND", "3": "+3V3"})),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-i2s-signal-named-rail-control",
        coach(i2s_signal_named_rail_netlist()),
        DesignLintPolicy(),
    )
    connector_fault = evaluate(
        "synthetic-i2s-signal-named-rail-connector-fault",
        coach(
            i2s_signal_named_rail_netlist(
                reference="J1",
                functions=("BCLK", "LRCLK", "SDOUT", "MCLK"),
                rail_pins={"1": "GND", "3": "+3V3"},
            )
        ),
        DesignLintPolicy(),
    )
    connector_control = evaluate(
        "synthetic-i2s-signal-named-rail-connector-control",
        coach(
            i2s_signal_named_rail_netlist(
                reference="J1",
                functions=("BCLK", "LRCLK", "SDOUT", "MCLK"),
            )
        ),
        DesignLintPolicy(),
    )
    return {
        "i2s_signal_named_rail_fault": fault.model_dump(mode="json"),
        "i2s_signal_named_rail_control": control.model_dump(mode="json"),
        "i2s_signal_named_rail_connector_fault": connector_fault.model_dump(mode="json"),
        "i2s_signal_named_rail_connector_control": connector_control.model_dump(mode="json"),
    }
