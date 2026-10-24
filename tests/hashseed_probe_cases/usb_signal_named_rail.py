"""Hash-seed report cases for USB signals assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.usb_signal_named_rail import usb_signal_on_named_rail_netlist


def report_cases() -> dict[str, object]:
    fault = evaluate(
        "synthetic-usb-signal-named-rail-fault",
        coach(usb_signal_on_named_rail_netlist()),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-usb-signal-named-rail-control",
        coach(usb_signal_on_named_rail_netlist(rail_name="USB_D+")),
        DesignLintPolicy(),
    )
    return {
        "usb_signal_named_rail_fault": fault.model_dump(mode="json"),
        "usb_signal_named_rail_control": control.model_dump(mode="json"),
    }
