"""Cross-process report cases for JTAG named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.jtag_signal_named_rail import jtag_signal_named_rail_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-jtag-signal-named-rail-fault",
        coach(jtag_signal_named_rail_netlist(rail_pins={"1": "GND", "3": "+3V3"})),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-jtag-signal-named-rail-control",
        coach(jtag_signal_named_rail_netlist()),
        DesignLintPolicy(),
    )
    connector_fault = evaluate(
        "synthetic-jtag-signal-named-rail-connector-fault",
        coach(
            jtag_signal_named_rail_netlist(
                reference="J1",
                functions=("TCK", "TMS", "TDI", "TDO"),
                rail_pins={"3": "GND"},
            )
        ),
        DesignLintPolicy(),
    )
    connector_control = evaluate(
        "synthetic-jtag-signal-named-rail-connector-control",
        coach(
            jtag_signal_named_rail_netlist(reference="J1", functions=("TCK", "TMS", "TDI", "TDO"))
        ),
        DesignLintPolicy(),
    )
    return {
        "jtag_signal_named_rail_fault": fault.model_dump(mode="json"),
        "jtag_signal_named_rail_control": control.model_dump(mode="json"),
        "jtag_signal_named_rail_connector_fault": connector_fault.model_dump(mode="json"),
        "jtag_signal_named_rail_connector_control": connector_control.model_dump(mode="json"),
    }
