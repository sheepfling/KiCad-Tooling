"""Hash-seed report cases for RS-485 data pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_signal_named_rail import rs485_signal_named_rail_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-rs485-signal-named-rail-fault",
        coach(rs485_signal_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-rs485-signal-named-rail-control",
        coach(rs485_signal_named_rail_netlist(rail_name="HOST_TX")),
        DesignLintPolicy(),
    )
    return {
        "rs485_signal_named_rail_fault": fault.model_dump(mode="json"),
        "rs485_signal_named_rail_control": control.model_dump(mode="json"),
    }
