"""Cross-process report cases for SWD named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.swd_signal_named_rail import swd_signal_named_rail_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-swd-signal-named-rail-fault",
        coach(swd_signal_named_rail_netlist(rail_pins={"1": "GND", "2": "+3V3"})),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-swd-signal-named-rail-control",
        coach(swd_signal_named_rail_netlist()),
        DesignLintPolicy(),
    )
    return {
        "swd_signal_named_rail_fault": fault.model_dump(mode="json"),
        "swd_signal_named_rail_control": control.model_dump(mode="json"),
    }
