"""Hash-seed report cases for RS-485 A/B line pins on named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_line_named_rail import rs485_line_named_rail_netlist


def report_cases() -> dict[str, object]:
    fault = evaluate(
        "synthetic-rs485-line-named-rail-fault",
        coach(rs485_line_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-rs485-line-named-rail-control",
        coach(rs485_line_named_rail_netlist(rail_name="RS485_A")),
        DesignLintPolicy(),
    )
    return {
        "rs485_line_named_rail_fault": fault.model_dump(mode="json"),
        "rs485_line_named_rail_control": control.model_dump(mode="json"),
    }
