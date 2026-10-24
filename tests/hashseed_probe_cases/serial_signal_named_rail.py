"""Hash-seed report cases for serial signal pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.serial_signal_named_rail import (
    serial_signal_on_named_rail_netlist,
)
from tests.design_lint_fixtures.serial_tx_rx_label_mismatch import serial_tx_rx_label_netlist


def report_cases() -> dict[str, object]:
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
    return {
        "serial_signal_named_rail_fault": fault.model_dump(mode="json"),
        "serial_signal_named_rail_control": control.model_dump(mode="json"),
    }
