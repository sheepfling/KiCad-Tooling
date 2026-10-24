"""Keep named-rail protocol heuristics in focused interface modules."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]


def test_named_rail_protocol_rules_use_focused_predicate_owners() -> None:
    owner_functions = {
        "bus.i2c_signal_on_named_rail": (
            "i2c_signal_named_rail.py",
            "kicad_tooling/hwrepo/i2c_signal_named_rail.py#i2c_signal_on_named_rail_candidates",
        ),
        "bus.serial_signal_on_named_rail": (
            "serial_signal_named_rail.py",
            "kicad_tooling/hwrepo/serial_signal_named_rail.py#serial_signal_on_named_rail_candidates",
        ),
        "bus.spi_signal_on_named_rail": (
            "spi_signal_named_rail.py",
            "kicad_tooling/hwrepo/spi_signal_named_rail.py#spi_signal_on_named_rail_candidates",
        ),
        "bus.can_signal_on_named_rail": (
            "can_signal_named_rail.py",
            "kicad_tooling/hwrepo/can_signal_named_rail.py#can_signal_on_named_rail_candidates",
        ),
        "bus.can_line_on_named_rail": (
            "can_line_named_rail.py",
            "kicad_tooling/hwrepo/can_line_named_rail.py#can_line_on_named_rail_candidates",
        ),
        "bus.ethernet_signal_on_named_rail": (
            "bus_ethernet_signal_named_rail.py",
            "kicad_tooling/hwrepo/bus_ethernet_signal_named_rail.py#ethernet_signal_on_named_rail_candidates",
        ),
        "bus.ethernet_management_signal_on_named_rail": (
            "bus_ethernet_management_named_rail.py",
            "kicad_tooling/hwrepo/bus_ethernet_management_named_rail.py#ethernet_management_signal_on_named_rail_candidates",
        ),
        "bus.usb_signal_on_named_rail": (
            "bus_usb_signal_named_rail.py",
            "kicad_tooling/hwrepo/bus_usb_signal_named_rail.py#usb_signal_on_named_rail_candidates",
        ),
        "bus.rs485_signal_on_named_rail": (
            "rs485_signal_named_rail.py",
            "kicad_tooling/hwrepo/rs485_signal_named_rail.py#rs485_signal_on_named_rail_candidates",
        ),
        "bus.rs485_line_on_named_rail": (
            "rs485_line_named_rail.py",
            "kicad_tooling/hwrepo/rs485_line_named_rail.py#rs485_line_on_named_rail_candidates",
        ),
    }
    catalog = {item.rule_id: item for item in rule_catalog().rules}
    for shared_name in ("named_rail_roles.py", "named_rail_pin_evidence.py"):
        assert line_count(HWREPO / shared_name) < IMPLEMENTATION_MAX_LINES

    for rule_id, (filename, owner_reference) in owner_functions.items():
        rule = catalog[rule_id]
        assert line_count(HWREPO / filename) < IMPLEMENTATION_MAX_LINES
        assert rule.theme == "interfaces"
        assert rule.implementation_owner == owner_reference
        assert owner_reference in rule.implementation_refs
