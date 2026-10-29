"""Coordinate theme-specific bus and signal-pair candidate translators."""

from __future__ import annotations

from .bus_ethernet_pair_labels import (
    ethernet_data_label_mismatch_candidates,
    ethernet_management_label_mismatch_candidates,
)
from .bus_ethernet_unconnected_management import (
    ethernet_management_unconnected_pin_candidates,
)
from .bus_signal_pairs import ComplementaryPinFunctionAliasResolution
from .can_peer_reference_scan import CanPeerReferenceScan
from .design_lint_bus_named_rail_candidates import bus_named_rail_candidates
from .design_lint_can_candidates import can_candidates
from .design_lint_i2c_candidates import (
    i2c_address_candidates,
    i2c_peer_reference_candidates,
    i2c_pullup_candidates,
    i2c_responder_coverage_candidates,
)
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
from .i2c_address_models import I2cAddressCoverageReport, I2cAddressMap
from .i2c_peer_reference_scan import I2cPeerReferenceScan
from .i2c_pullup_models import I2cPullupHeuristicCoverage
from .models import NetlistContract
from .pcb_drc_models import PcbDifferentialPairRuleMap
from .rs485_peer_reference_types import Rs485PeerReferenceScan
from .spi_participants import SpiRosterContext
from .spi_peer_reference_scan import SpiPeerReferenceScan
from .usb_c_cc_endpoint_pairing import crossed_usb_c_cc_endpoint_candidates
from .usb_c_sbu_same_net import usb_c_sbu_same_net_candidates
from .usb_c_superspeed_lane_labels import usb_c_superspeed_lane_label_mismatch_candidates
from .usb_data_same_net import usb_data_same_net_candidates


def bus_candidates(
    observed: NetlistContract,
    *,
    complementary_alias_resolution: ComplementaryPinFunctionAliasResolution | None = None,
    i2c_address_coverage: I2cAddressCoverageReport | None = None,
    i2c_address_map: I2cAddressMap | None = None,
    i2c_pullup_heuristic_coverage: I2cPullupHeuristicCoverage | None = None,
    i2c_peer_reference_scan: I2cPeerReferenceScan | None = None,
    spi_roster: SpiRosterContext | None = None,
    spi_peer_reference_scan: SpiPeerReferenceScan | None = None,
    can_peer_reference_scan: CanPeerReferenceScan | None = None,
    rs485_peer_reference_scan: Rs485PeerReferenceScan | None = None,
    component_peer_findings: tuple[Candidate, ...] = (),
    pcb_differential_pair_rule_map: PcbDifferentialPairRuleMap | None = None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Coordinate bus and pair checks while preserving their stable output order."""
    return (
        *i2c_pullup_candidates(observed, i2c_pullup_heuristic_coverage),
        *i2c_peer_reference_candidates(
            observed,
            i2c_peer_reference_scan,
            component_peer_findings,
        ),
        *two_wire_signal_candidates(observed),
        *serial_signal_candidates(observed),
        *spi_peer_reference_candidates(
            observed,
            spi_peer_reference_scan,
            component_peer_findings,
        ),
        *spi_bias_candidates(observed, spi_roster),
        *spi_signal_candidates(observed),
        *unconnected_interface_candidates(observed),
        *can_candidates(observed, can_peer_reference_scan, component_peer_findings),
        *rs485_candidates(observed, rs485_peer_reference_scan, component_peer_findings),
        *ethernet_data_label_mismatch_candidates(observed),
        *ethernet_management_label_mismatch_candidates(observed),
        *ethernet_management_unconnected_pin_candidates(observed),
        *bus_named_rail_candidates(observed),
        *complementary_signal_candidates(observed, complementary_alias_resolution),
        *usb_data_polarity_label_candidates(observed),
        *usb_c_superspeed_lane_label_mismatch_candidates(observed),
        *usb_data_same_net_candidates(observed),
        *usb_c_same_net_candidates(observed, reviewed_connector_references),
        *crossed_usb_c_cc_endpoint_candidates(observed),
        *usb_c_sbu_same_net_candidates(observed),
        *named_differential_pair_candidates(observed, pcb_differential_pair_rule_map),
        *i2c_address_candidates(i2c_address_coverage),
        *i2c_responder_coverage_candidates(observed, i2c_address_map),
    )
