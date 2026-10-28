"""Cross-process report cases for CANH/CANL pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.can_line_named_rail import can_line_named_rail_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-can-line-named-rail-fault",
        coach(can_line_named_rail_netlist(high_net="GND", low_net="+3V3")),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-can-line-named-rail-control",
        coach(can_line_named_rail_netlist(high_net="CANH_BUS", low_net="CANL_BUS")),
        DesignLintPolicy(),
    )
    return {
        "can_line_named_rail_fault": fault.model_dump(mode="json"),
        "can_line_named_rail_control": control.model_dump(mode="json"),
    }
