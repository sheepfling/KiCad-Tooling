"""Cross-process report cases for USB-C SBU pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_c_sbu_named_rail import usb_c_sbu_named_rail_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-usb-c-sbu-named-rail-fault",
        coach(usb_c_sbu_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-usb-c-sbu-named-rail-control",
        coach(usb_c_sbu_named_rail_netlist(sbu1_net="SBU1_BUS", sbu2_net="SBU2_BUS")),
        DesignLintPolicy(),
    )
    return {
        "usb_c_sbu_named_rail_fault": fault.model_dump(mode="json"),
        "usb_c_sbu_named_rail_control": control.model_dump(mode="json"),
    }
