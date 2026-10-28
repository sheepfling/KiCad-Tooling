"""Cross-process report cases for USB 2.0 D+/D- pins sharing one net."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_data_same_net import usb_data_same_net_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-usb-dp-dm-same-net-fault",
        coach(usb_data_same_net_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-usb-dp-dm-same-net-control",
        coach(usb_data_same_net_netlist(shared=False)),
        DesignLintPolicy(),
    )
    return {
        "usb_dp_dm_same_net_fault": fault.model_dump(mode="json"),
        "usb_dp_dm_same_net_control": control.model_dump(mode="json"),
    }
