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

TYPED_SIGNAL_RULES = frozenset(
    {
        "bus.i2c_signal_on_named_rail",
        "bus.i2s_signal_on_named_rail",
        "bus.jtag_signal_on_named_rail",
        "bus.i3c_signal_on_named_rail",
        "bus.spi_signal_on_named_rail",
        "bus.serial_signal_on_named_rail",
        "bus.can_signal_on_named_rail",
        "bus.ethernet_signal_on_named_rail",
        "bus.ethernet_management_signal_on_named_rail",
        "bus.usb_signal_on_named_rail",
        "bus.rs485_signal_on_named_rail",
        "bus.usb_c_sbu_signal_on_named_rail",
    }
)
TYPED_SIGNAL_OWNER = (
    "kicad_tooling/hwrepo/design_lint_named_rail_candidate_evidence.py#NamedRailSignalCandidate"
)
CONNECTOR_PIN_EVIDENCE = (
    "kicad_tooling/hwrepo/named_rail_pin_evidence.py#assigned_named_rail_connector_pins"
)
CONNECTOR_CANDIDATE_REFERENCES = (
    "kicad_tooling/hwrepo/connector_identity.py#connector_candidate_references"
)
CAN_MODULE_DATA_ROLE = "kicad_tooling/hwrepo/can_signal_functions.py#can_module_data_role"
CAN_MODULE_IDENTITY = "kicad_tooling/hwrepo/can_signal_functions.py#explicit_can_module_identity"
TYPED_LINE_RULES = frozenset({"bus.can_line_on_named_rail", "bus.rs485_line_on_named_rail"})
TYPED_LINE_OWNER = (
    "kicad_tooling/hwrepo/design_lint_named_rail_line_candidate_evidence.py#NamedRailLineCandidate"
)


def test_named_rail_protocol_rules_use_focused_predicate_owners() -> None:
    owner_functions = {
        "bus.i2c_signal_on_named_rail": (
            "i2c_signal_named_rail.py",
            "kicad_tooling/hwrepo/i2c_signal_named_rail.py#i2c_signal_on_named_rail_candidates",
        ),
        "bus.i2s_signal_on_named_rail": (
            "i2s_signal_named_rail.py",
            "kicad_tooling/hwrepo/i2s_signal_named_rail.py#i2s_signal_on_named_rail_candidates",
        ),
        "bus.jtag_signal_on_named_rail": (
            "jtag_signal_inventory.py",
            "kicad_tooling/hwrepo/jtag_signal_inventory.py#jtag_named_rail_signal_pins",
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
        "bus.usb_c_cc_signal_on_named_rail": (
            "usb_c_cc_named_rail.py",
            "kicad_tooling/hwrepo/usb_c_cc_named_rail.py#usb_c_cc_signal_on_named_rail_candidates",
        ),
        "bus.usb_c_sbu_signal_on_named_rail": (
            "usb_c_sbu_named_rail.py",
            "kicad_tooling/hwrepo/usb_c_sbu_named_rail.py#usb_c_sbu_signal_on_named_rail_candidates",
        ),
        "bus.i3c_signal_on_named_rail": (
            "i3c_signal_named_rail.py",
            "kicad_tooling/hwrepo/i3c_signal_named_rail.py#i3c_signal_on_named_rail_candidates",
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
    assert line_count(HWREPO / "design_lint_named_rail_candidate_evidence.py") < (
        IMPLEMENTATION_MAX_LINES
    )
    assert line_count(HWREPO / "can_signal_functions.py") < IMPLEMENTATION_MAX_LINES
    assert line_count(HWREPO / "i2s_endpoint_inventory.py") < IMPLEMENTATION_MAX_LINES
    assert line_count(HWREPO / "jtag_signal_inventory.py") < IMPLEMENTATION_MAX_LINES
    assert line_count(HWREPO / "design_lint_named_rail_line_candidate_evidence.py") < (
        IMPLEMENTATION_MAX_LINES
    )

    for rule_id, (filename, owner_reference) in owner_functions.items():
        rule = catalog[rule_id]
        assert line_count(HWREPO / filename) < IMPLEMENTATION_MAX_LINES
        assert rule.theme == "interfaces"
        assert rule.implementation_owner == owner_reference
        assert owner_reference in rule.implementation_refs

    for rule_id in TYPED_SIGNAL_RULES:
        assert TYPED_SIGNAL_OWNER in catalog[rule_id].implementation_refs

    i2s_refs = catalog["bus.i2s_signal_on_named_rail"].implementation_refs
    assert (
        "kicad_tooling/hwrepo/i2s_endpoint_inventory.py#I2sEndpointInventory.named_rail_signal_pins"
        in i2s_refs
    )
    assert CONNECTOR_PIN_EVIDENCE in i2s_refs
    assert CONNECTOR_CANDIDATE_REFERENCES in i2s_refs

    jtag_refs = catalog["bus.jtag_signal_on_named_rail"].implementation_refs
    assert (
        "kicad_tooling/hwrepo/jtag_signal_inventory.py#JtagEndpointInventory.named_rail_signal_pins"
        in jtag_refs
    )
    assert "kicad_tooling/hwrepo/jtag_signal_inventory.py#jtag_signal_roles" in jtag_refs
    assert CONNECTOR_PIN_EVIDENCE in jtag_refs
    assert CONNECTOR_CANDIDATE_REFERENCES in jtag_refs

    assert CONNECTOR_PIN_EVIDENCE in catalog["bus.i2c_signal_on_named_rail"].implementation_refs
    assert (
        CONNECTOR_CANDIDATE_REFERENCES
        in catalog["bus.i2c_signal_on_named_rail"].implementation_refs
    )
    assert CONNECTOR_PIN_EVIDENCE in catalog["bus.spi_signal_on_named_rail"].implementation_refs
    assert (
        CONNECTOR_CANDIDATE_REFERENCES
        in catalog["bus.spi_signal_on_named_rail"].implementation_refs
    )
    assert CONNECTOR_PIN_EVIDENCE in catalog["bus.can_signal_on_named_rail"].implementation_refs
    assert (
        CONNECTOR_CANDIDATE_REFERENCES
        in catalog["bus.can_signal_on_named_rail"].implementation_refs
    )
    assert CAN_MODULE_DATA_ROLE in catalog["bus.can_signal_on_named_rail"].implementation_refs
    assert CAN_MODULE_IDENTITY in catalog["bus.can_signal_on_named_rail"].implementation_refs
    assert (
        CONNECTOR_PIN_EVIDENCE
        in catalog["bus.ethernet_management_signal_on_named_rail"].implementation_refs
    )
    assert (
        CONNECTOR_CANDIDATE_REFERENCES
        in catalog["bus.ethernet_management_signal_on_named_rail"].implementation_refs
    )
    sbu_refs = catalog["bus.usb_c_sbu_signal_on_named_rail"].implementation_refs
    assert CONNECTOR_PIN_EVIDENCE in sbu_refs
    assert CONNECTOR_CANDIDATE_REFERENCES in sbu_refs
    i3c_refs = catalog["bus.i3c_signal_on_named_rail"].implementation_refs
    assert CONNECTOR_PIN_EVIDENCE in i3c_refs
    assert CONNECTOR_CANDIDATE_REFERENCES in i3c_refs
    rs485_refs = catalog["bus.rs485_signal_on_named_rail"].implementation_refs
    assert CONNECTOR_PIN_EVIDENCE in rs485_refs
    assert CONNECTOR_CANDIDATE_REFERENCES in rs485_refs

    for rule_id in TYPED_LINE_RULES:
        assert TYPED_LINE_OWNER in catalog[rule_id].implementation_refs
    can_line_refs = catalog["bus.can_line_on_named_rail"].implementation_refs
    assert CONNECTOR_PIN_EVIDENCE in can_line_refs
    assert CONNECTOR_CANDIDATE_REFERENCES in can_line_refs
    usb_signal_refs = catalog["bus.usb_signal_on_named_rail"].implementation_refs
    assert CONNECTOR_PIN_EVIDENCE in usb_signal_refs
    assert CONNECTOR_CANDIDATE_REFERENCES in usb_signal_refs
    usb_c_cc_refs = catalog["bus.usb_c_cc_signal_on_named_rail"].implementation_refs
    assert CONNECTOR_PIN_EVIDENCE in usb_c_cc_refs
    assert CONNECTOR_CANDIDATE_REFERENCES in usb_c_cc_refs
    ethernet_signal_refs = catalog["bus.ethernet_signal_on_named_rail"].implementation_refs
    assert CONNECTOR_PIN_EVIDENCE in ethernet_signal_refs
    assert CONNECTOR_CANDIDATE_REFERENCES in ethernet_signal_refs
    rs485_line_refs = catalog["bus.rs485_line_on_named_rail"].implementation_refs
    assert CONNECTOR_PIN_EVIDENCE in rs485_line_refs
    assert CONNECTOR_CANDIDATE_REFERENCES in rs485_line_refs
