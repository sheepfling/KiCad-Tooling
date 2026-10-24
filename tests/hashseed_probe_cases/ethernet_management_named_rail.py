"""Hash-seed report cases for Ethernet management pins on named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_management_labels import ethernet_management_netlist


def report_cases() -> dict[str, object]:
    fault = evaluate(
        "synthetic-ethernet-management-named-rail-fault",
        coach(ethernet_management_netlist(labels=("GND", "ETH_MDIO"))),
        DesignLintPolicy(),
    )
    control = evaluate(
        "synthetic-ethernet-management-named-rail-control",
        coach(ethernet_management_netlist()),
        DesignLintPolicy(),
    )
    return {
        "ethernet_management_named_rail_fault": fault.model_dump(mode="json"),
        "ethernet_management_named_rail_control": control.model_dump(mode="json"),
    }
