"""Cross-process report cases for I3C SDA/SCL pins sharing one net."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i3c_same_net import (
    i3c_distinct_lines_netlist,
    i3c_same_net_netlist,
)


def report_cases() -> dict[str, object]:
    fault = evaluate(
        "synthetic-i3c-same-net-fault",
        coach(i3c_same_net_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-i3c-same-net-control",
        coach(i3c_distinct_lines_netlist()),
        DesignLintPolicy(),
    )
    return {
        "i3c_same_net_fault": fault.model_dump(mode="json"),
        "i3c_same_net_control": control.model_dump(mode="json"),
    }
