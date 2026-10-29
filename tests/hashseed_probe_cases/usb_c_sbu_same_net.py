"""Cross-process reports for USB-C SBU pins sharing a net."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_c_sbu_same_net import usb_c_sbu_same_net_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-usb-c-sbu-same-net-fault",
        coach(usb_c_sbu_same_net_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-usb-c-sbu-same-net-control",
        coach(usb_c_sbu_same_net_netlist(shared=False)),
        DesignLintPolicy(),
    )
    return {
        "usb_c_sbu_same_net_fault": fault.model_dump(mode="json"),
        "usb_c_sbu_same_net_control": control.model_dump(mode="json"),
    }
