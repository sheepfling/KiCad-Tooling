"""Hash-seed report cases for serial signal pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.serial_signal_named_rail import (
    serial_signal_on_named_rail_netlist,
)
from tests.design_lint_fixtures.serial_tx_rx_label_mismatch import serial_tx_rx_label_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-serial-signal-named-rail-fault",
        coach(serial_signal_on_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-serial-signal-named-rail-control",
        coach(serial_tx_rx_label_netlist(crossed=False)),
        DesignLintPolicy(),
    )
    flow_control = serial_signal_on_named_rail_netlist()
    flow_functions = dict(flow_control.pin_functions)
    flow_functions["U1.1"] = "USART1_CTS"
    flow_control = flow_control.model_copy(
        update={
            "pin_functions": flow_functions,
            "nets": {"0V PWM 2": ("U1.1",), "USART1_RX": ("U1.2",)},
        }
    )
    flow_control_fault = evaluate(
        "synthetic-serial-flow-control-named-rail-fault",
        coach(flow_control),
        DesignLintPolicy(),
    )
    return {
        "serial_signal_named_rail_fault": fault.model_dump(mode="json"),
        "serial_signal_named_rail_control": control.model_dump(mode="json"),
        "serial_flow_control_named_rail_fault": flow_control_fault.model_dump(mode="json"),
    }
