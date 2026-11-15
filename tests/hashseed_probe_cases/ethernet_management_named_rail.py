"""Hash-seed report cases for Ethernet management pins on named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.ethernet_management_labels import ethernet_management_netlist
from tests.json_types import JsonObject


def report_cases() -> JsonObject:
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
    connector_fault = evaluate(
        "synthetic-ethernet-management-connector-named-rail-fault",
        coach(ethernet_management_netlist(reference="J1", labels=("GND", "+3V3"))),
        DesignLintPolicy(),
    )
    connector_control = evaluate(
        "synthetic-ethernet-management-connector-named-rail-control",
        coach(ethernet_management_netlist(reference="J1")),
        DesignLintPolicy(),
    )
    return {
        "ethernet_management_named_rail_fault": fault.model_dump(mode="json"),
        "ethernet_management_named_rail_control": control.model_dump(mode="json"),
        "ethernet_management_named_rail_connector_fault": connector_fault.model_dump(mode="json"),
        "ethernet_management_named_rail_connector_control": connector_control.model_dump(
            mode="json"
        ),
    }
