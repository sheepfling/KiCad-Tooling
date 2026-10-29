"""Cross-process cases for a one-sided open I3C signal pair."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.i3c_same_net import i3c_same_net_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    pair = i3c_same_net_netlist()
    fault = pair.model_copy(update={"nets": {"I3C_SCL": ("U1.2",)}})
    control = pair.model_copy(update={"nets": {"I3C_SDA": ("U1.1",), "I3C_SCL": ("U1.2",)}})
    return {
        "i3c_unconnected_pin_fault": evaluate(
            "synthetic-i3c-open-fault", coach(fault), DesignLintPolicy()
        ).model_dump(mode="json"),
        "i3c_unconnected_pin_control": evaluate(
            "synthetic-i3c-open-control", coach(control), DesignLintPolicy()
        ).model_dump(mode="json"),
    }
