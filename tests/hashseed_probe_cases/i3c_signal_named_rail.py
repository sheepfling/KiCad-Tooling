"""Cross-process report cases for I3C signals assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i3c_signal_named_rail import i3c_signal_named_rail_netlist


def report_cases() -> dict[str, object]:
    fault = evaluate(
        "synthetic-i3c-signal-named-rail-fault",
        coach(i3c_signal_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-i3c-signal-named-rail-control",
        coach(i3c_signal_named_rail_netlist(sda_net="I3C1_SDA_BUS", scl_net="I3C1_SCL_BUS")),
        DesignLintPolicy(),
    )
    return {
        "i3c_signal_named_rail_fault": fault.model_dump(mode="json"),
        "i3c_signal_named_rail_control": control.model_dump(mode="json"),
    }
