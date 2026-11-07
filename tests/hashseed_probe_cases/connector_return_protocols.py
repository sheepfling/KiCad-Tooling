"""Complete fault/control reports for protocol connector-return hash-seed probes."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256

from kicad_tooling.ci_hosted_spi_generic_connector_cases import spi_connector_role_map
from kicad_tooling.hwrepo.contracts import model_json_bytes
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.can_generic_connector_pair import can_connector_return_netlist
from tests.design_lint_fixtures.i2c_connector_return import two_pin_i2c_connector_netlist
from tests.design_lint_fixtures.i3c_connector_return import two_pin_i3c_connector_netlist
from tests.design_lint_fixtures.rs485_connector_return import two_pin_rs485_connector_netlist
from tests.design_lint_fixtures.serial_connector_return import two_pin_uart_connector_netlist
from tests.design_lint_fixtures.spi_generic_connector_triad import (
    generic_spi_connector_triad_netlist,
)
from tests.design_lint_fixtures.swd_generic_connector_pair import generic_swd_connector_netlist
from tests.design_lint_fixtures.usb2_connector_return import two_pin_usb2_connector_netlist
from tests.design_lint_fixtures.usb_superspeed_connector_return import (
    two_pin_usb_superspeed_connector_netlist,
)
from tests.json_types import JsonObject

_PROTOCOLS = (
    "serial",
    "i2c",
    "i3c",
    "swd",
    "can",
    "rs485",
    "usb2",
    "usb_superspeed",
    "spi",
)


def _report(
    protocol: str,
    observed: NetlistContract,
    *,
    has_return_role: bool,
) -> JsonObject:
    project_id = f"synthetic-{protocol}-connector-return-{has_return_role}"
    digest = sha256(model_json_bytes(observed)).hexdigest()
    coverage = (
        spi_connector_role_map(observed, has_return_role=has_return_role)
        if protocol == "spi"
        else None
    )
    report = evaluate(
        project_id,
        coach(observed, digest, project_id=project_id),
        DesignLintPolicy(),
        coverage,
    )
    return report.model_dump(mode="json")


def report_cases() -> dict[str, JsonObject]:
    """Return complete synthetic reports for each protocol's fault and control."""
    builders: dict[str, tuple[Callable[[], NetlistContract], Callable[[], NetlistContract]]] = {
        "serial": (
            two_pin_uart_connector_netlist,
            lambda: two_pin_uart_connector_netlist(return_pin="GND"),
        ),
        "i2c": (
            two_pin_i2c_connector_netlist,
            lambda: two_pin_i2c_connector_netlist(connected_return_contact=True),
        ),
        "i3c": (
            two_pin_i3c_connector_netlist,
            lambda: two_pin_i3c_connector_netlist(connected_return_contact=True),
        ),
        "swd": (
            lambda: generic_swd_connector_netlist(
                connector_functions=tuple(f"Pin_{number}" for number in range(1, 6))
            ),
            lambda: generic_swd_connector_netlist(
                connector_functions=("Pin_1", "Pin_2", "Pin_3", "Pin_4", "GND")
            ),
        ),
        "can": (
            can_connector_return_netlist,
            lambda: can_connector_return_netlist(with_return_contact=True),
        ),
        "rs485": (
            two_pin_rs485_connector_netlist,
            lambda: two_pin_rs485_connector_netlist(connector_functions=("Pin_1", "Pin_2", "GND")),
        ),
        "usb2": (
            two_pin_usb2_connector_netlist,
            lambda: two_pin_usb2_connector_netlist(connected_return_contact=True),
        ),
        "usb_superspeed": (
            two_pin_usb_superspeed_connector_netlist,
            lambda: two_pin_usb_superspeed_connector_netlist(include_return_contact=True),
        ),
        "spi": (generic_spi_connector_triad_netlist, generic_spi_connector_triad_netlist),
    }
    reports: dict[str, JsonObject] = {}
    for protocol in _PROTOCOLS:
        fault_builder, control_builder = builders[protocol]
        reports[f"{protocol}_connector_return_fault"] = _report(
            protocol, fault_builder(), has_return_role=False
        )
        reports[f"{protocol}_connector_return_control"] = _report(
            protocol, control_builder(), has_return_role=True
        )
    return reports
