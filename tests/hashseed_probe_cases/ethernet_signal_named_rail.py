"""Hash-seed report cases for Ethernet pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_signal_named_rail import (
    ethernet_signal_on_named_rail_netlist,
)
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-ethernet-signal-named-rail-fault",
        coach(ethernet_signal_on_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-ethernet-signal-named-rail-control",
        coach(ethernet_signal_on_named_rail_netlist(rail_name="ETH_TX_P")),
        DesignLintPolicy(),
    )
    return {
        "ethernet_signal_named_rail_fault": fault.model_dump(mode="json"),
        "ethernet_signal_named_rail_control": control.model_dump(mode="json"),
    }
