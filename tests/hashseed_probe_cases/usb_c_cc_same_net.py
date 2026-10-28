"""Cross-process report cases for USB-C CC1/CC2 connector pins on one net."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_c_cc_same_net import usb_c_cc_same_net_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-usb-c-cc-same-net-fault",
        coach(usb_c_cc_same_net_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-usb-c-cc-same-net-control",
        coach(usb_c_cc_same_net_netlist(shared=False)),
        DesignLintPolicy(),
    )
    return {
        "usb_c_cc_same_net_fault": fault.model_dump(mode="json"),
        "usb_c_cc_same_net_control": control.model_dump(mode="json"),
    }
