"""Cross-process reports for crossed USB-C connector/controller CC assignments."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_c_cc_endpoint_pairing import (
    usb_c_cc_endpoint_pairing_netlist,
)
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
    fault = evaluate(
        "synthetic-usb-c-cc-endpoint-crossed-fault",
        coach(usb_c_cc_endpoint_pairing_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-usb-c-cc-endpoint-crossed-control",
        coach(usb_c_cc_endpoint_pairing_netlist(crossed=False)),
        DesignLintPolicy(),
    )
    return {
        "usb_c_cc_endpoint_pairing_fault": fault.model_dump(mode="json"),
        "usb_c_cc_endpoint_pairing_control": control.model_dump(mode="json"),
    }
