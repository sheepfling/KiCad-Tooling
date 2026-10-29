"""Coordinate theme-specific bus and signal-pair candidate translators."""

from .bus_ethernet_pair_labels import (
    ethernet_data_label_mismatch_candidates,
    ethernet_management_label_mismatch_candidates,
)
from .design_lint_bus_inputs import BusCandidateInputs
from .design_lint_bus_named_rail_candidates import bus_named_rail_candidates
from .design_lint_can_candidates import can_candidates
from .design_lint_ethernet_unconnected_candidates import ethernet_unconnected_pin_candidates
from .design_lint_i2c_candidates import (
    i2c_address_theme_candidates,
    i2c_peer_reference_candidates,
)
from .design_lint_i2c_pullup_candidates import i2c_pullup_theme_candidates
from .design_lint_interfaces_usb_data_polarity import usb_data_polarity_label_candidates
from .design_lint_rs485_candidates import rs485_candidates
from .design_lint_serial_signal_candidates import serial_signal_candidates
from .design_lint_signal_pair_candidates import (
    complementary_signal_candidates,
    named_differential_pair_candidates,
)
from .design_lint_spi_candidates import spi_bias_candidates, spi_peer_reference_candidates
from .design_lint_spi_signal_candidates import spi_signal_candidates
from .design_lint_two_wire_signal_candidates import two_wire_signal_candidates
from .design_lint_types import Candidate
from .design_lint_unconnected_interface_candidates import unconnected_interface_candidates
from .design_lint_usb_c_same_net_candidates import usb_c_same_net_candidates
from .usb_c_cc_endpoint_pairing import crossed_usb_c_cc_endpoint_candidates
from .usb_c_sbu_same_net import usb_c_sbu_same_net_candidates
from .usb_c_superspeed_lane_labels import usb_c_superspeed_lane_label_mismatch_candidates
from .usb_data_same_net import usb_data_same_net_candidates


def bus_candidates(inputs: BusCandidateInputs) -> tuple[Candidate, ...]:
    """Coordinate bus and pair checks while preserving their stable output order."""
    observed = inputs.observed
    component_peer_findings = inputs.component_peer_findings
    return (
        *i2c_pullup_theme_candidates(inputs.i2c_pullup),
        *i2c_peer_reference_candidates(
            observed,
            inputs.i2c_peer_reference_scan,
            component_peer_findings,
        ),
        *two_wire_signal_candidates(observed),
        *serial_signal_candidates(observed),
        *spi_peer_reference_candidates(
            observed,
            inputs.spi_peer_reference_scan,
            component_peer_findings,
        ),
        *spi_bias_candidates(observed, inputs.spi_roster),
        *spi_signal_candidates(observed),
        *unconnected_interface_candidates(observed),
        *can_candidates(observed, inputs.can_peer_reference_scan, component_peer_findings),
        *rs485_candidates(observed, inputs.rs485_peer_reference_scan, component_peer_findings),
        *ethernet_data_label_mismatch_candidates(observed),
        *ethernet_management_label_mismatch_candidates(observed),
        *ethernet_unconnected_pin_candidates(observed),
        *bus_named_rail_candidates(observed),
        *complementary_signal_candidates(observed, inputs.complementary_alias_resolution),
        *usb_data_polarity_label_candidates(observed),
        *usb_c_superspeed_lane_label_mismatch_candidates(observed),
        *usb_data_same_net_candidates(observed),
        *usb_c_same_net_candidates(observed, inputs.reviewed_connector_references),
        *crossed_usb_c_cc_endpoint_candidates(observed),
        *usb_c_sbu_same_net_candidates(observed),
        *named_differential_pair_candidates(observed, inputs.pcb_differential_pair_rule_map),
        *i2c_address_theme_candidates(inputs.i2c_address),
    )
