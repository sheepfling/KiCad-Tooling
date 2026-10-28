"""Cross-process report cases for USB-C CC pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_c_cc_named_rail import usb_c_cc_named_rail_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-usb-c-cc-named-rail-fault",
        coach(usb_c_cc_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-usb-c-cc-named-rail-control",
        coach(usb_c_cc_named_rail_netlist(cc1_net="CC1_BUS", cc2_net="CC2_BUS")),
        DesignLintPolicy(),
    )
    return {
        "usb_c_cc_named_rail_fault": fault.model_dump(mode="json"),
        "usb_c_cc_named_rail_control": control.model_dump(mode="json"),
    }
