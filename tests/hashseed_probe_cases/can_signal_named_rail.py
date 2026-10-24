"""Hash-seed report cases for CAN controller pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.can_signal_named_rail import can_signal_on_named_rail_netlist


def report_cases() -> dict[str, object]:
    fault = evaluate(
        "synthetic-can-signal-named-rail-fault",
        coach(can_signal_on_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-can-signal-named-rail-control",
        coach(can_signal_on_named_rail_netlist(rail_name="CAN_CONTROL")),
        DesignLintPolicy(),
    )
    return {
        "can_signal_named_rail_fault": fault.model_dump(mode="json"),
        "can_signal_named_rail_control": control.model_dump(mode="json"),
    }
