"""Hash-seed report cases for an RS-485 A/B shared-net review."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.rs485_ab_same_net import rs485_ab_same_net_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-rs485-ab-same-net-fault",
        coach(rs485_ab_same_net_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-rs485-ab-same-net-control",
        coach(rs485_ab_same_net_netlist(shared=False)),
        DesignLintPolicy(),
    )
    return {
        "rs485_ab_same_net_fault": fault.model_dump(mode="json"),
        "rs485_ab_same_net_control": control.model_dump(mode="json"),
    }
