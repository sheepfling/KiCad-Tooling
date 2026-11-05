"""Source-binding regressions for protocol signals assigned to named rails."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.bus_ethernet_management_named_rail import (
    ethernet_management_signal_on_named_rail_candidates,
)
from kicad_tooling.hwrepo.bus_ethernet_signal_named_rail import (
    ethernet_signal_on_named_rail_candidates,
)
from kicad_tooling.hwrepo.bus_usb_signal_named_rail import usb_signal_on_named_rail_candidates
from kicad_tooling.hwrepo.can_signal_named_rail import can_signal_on_named_rail_candidates
from kicad_tooling.hwrepo.design_lint_named_rail_candidate_evidence import (
    CanSignalNamedRailEvidence,
    EthernetManagementSignalNamedRailEvidence,
    EthernetSignalNamedRailEvidence,
    I2cSignalNamedRailEvidence,
    I3cSignalNamedRailEvidence,
    NamedRailSignalCandidate,
    Rs485SignalNamedRailEvidence,
    SerialSignalNamedRailEvidence,
    SpiSignalNamedRailEvidence,
    UsbCSbuSignalNamedRailEvidence,
    UsbSignalNamedRailEvidence,
)
from kicad_tooling.hwrepo.i2c_signal_named_rail import i2c_signal_on_named_rail_candidates
from kicad_tooling.hwrepo.i3c_signal_named_rail import i3c_signal_on_named_rail_candidates
from kicad_tooling.hwrepo.named_rail_pin_evidence import NamedRailPinSource
from kicad_tooling.hwrepo.rs485_signal_named_rail import rs485_signal_on_named_rail_candidates
from kicad_tooling.hwrepo.serial_signal_named_rail import serial_signal_on_named_rail_candidates
from kicad_tooling.hwrepo.spi_signal_named_rail import spi_signal_on_named_rail_candidates
from kicad_tooling.hwrepo.usb_c_sbu_named_rail import usb_c_sbu_signal_on_named_rail_candidates
from tests.design_lint_fixtures.can_signal_named_rail import can_signal_on_named_rail_netlist
from tests.design_lint_fixtures.ethernet_management_labels import ethernet_management_netlist
from tests.design_lint_fixtures.ethernet_signal_named_rail import (
    ethernet_signal_on_named_rail_netlist,
)
from tests.design_lint_fixtures.i2c_signal_named_rail import i2c_signal_on_named_rail_netlist
from tests.design_lint_fixtures.i3c_signal_named_rail import i3c_signal_named_rail_netlist
from tests.design_lint_fixtures.rs485_signal_named_rail import rs485_signal_named_rail_netlist
from tests.design_lint_fixtures.serial_signal_named_rail import (
    serial_signal_on_named_rail_netlist,
)
from tests.design_lint_fixtures.spi_signal_named_rail import spi_signal_on_named_rail_netlist
from tests.design_lint_fixtures.usb_c_sbu_named_rail import usb_c_sbu_named_rail_netlist
from tests.design_lint_fixtures.usb_signal_named_rail import usb_signal_on_named_rail_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.evidence_lint,
]


def test_each_protocol_variant_retains_and_rechecks_its_native_pin_source() -> None:
    candidates = (
        can_signal_on_named_rail_candidates(can_signal_on_named_rail_netlist())[0],
        i2c_signal_on_named_rail_candidates(i2c_signal_on_named_rail_netlist())[0],
        i3c_signal_on_named_rail_candidates(i3c_signal_named_rail_netlist())[0],
        spi_signal_on_named_rail_candidates(spi_signal_on_named_rail_netlist())[0],
        serial_signal_on_named_rail_candidates(serial_signal_on_named_rail_netlist())[0],
        ethernet_signal_on_named_rail_candidates(ethernet_signal_on_named_rail_netlist())[0],
        ethernet_management_signal_on_named_rail_candidates(
            ethernet_management_netlist(labels=("GND", "ETH_MDIO"))
        )[0],
        usb_signal_on_named_rail_candidates(usb_signal_on_named_rail_netlist())[0],
        rs485_signal_on_named_rail_candidates(rs485_signal_named_rail_netlist())[0],
        usb_c_sbu_signal_on_named_rail_candidates(usb_c_sbu_named_rail_netlist())[0],
    )
    source_types = (
        CanSignalNamedRailEvidence,
        I2cSignalNamedRailEvidence,
        I3cSignalNamedRailEvidence,
        SpiSignalNamedRailEvidence,
        SerialSignalNamedRailEvidence,
        EthernetSignalNamedRailEvidence,
        EthernetManagementSignalNamedRailEvidence,
        UsbSignalNamedRailEvidence,
        Rs485SignalNamedRailEvidence,
        UsbCSbuSignalNamedRailEvidence,
    )

    for candidate, source_type in zip(candidates, source_types, strict=True):
        assert isinstance(candidate, NamedRailSignalCandidate)
        assert isinstance(candidate.source_evidence, source_type)
        assert isinstance(candidate.source_evidence.pin, NamedRailPinSource)
        assert candidate.evidence
        stale_netlist = candidate.source_evidence.pin.observed.model_copy(update={"nets": {}})
        with pytest.raises(ValueError, match="current native netlist"):
            replace(candidate.source_evidence.pin, observed=stale_netlist)


def test_rs485_source_rechecks_explicit_transceiver_identity() -> None:
    candidate = rs485_signal_on_named_rail_candidates(rs485_signal_named_rail_netlist())[0]
    assert isinstance(candidate, NamedRailSignalCandidate)
    source = candidate.source_evidence
    changed_observed = source.pin.observed.model_copy(update={"component_symbols": {}})
    changed_pin = NamedRailPinSource(observed=changed_observed, evidence=source.pin.evidence)

    with pytest.raises(ValueError, match="current transceiver"):
        replace(source, pin=changed_pin)


def test_usb_c_sbu_source_rechecks_unique_complete_native_pair() -> None:
    candidate = usb_c_sbu_signal_on_named_rail_candidates(usb_c_sbu_named_rail_netlist())[0]
    assert isinstance(candidate, NamedRailSignalCandidate)
    source = candidate.source_evidence
    pin_functions = dict(source.pin.observed.pin_functions)
    pin_functions["U1.3"] = "SBU1"
    changed_observed = source.pin.observed.model_copy(update={"pin_functions": pin_functions})
    changed_pin = NamedRailPinSource(observed=changed_observed, evidence=source.pin.evidence)

    with pytest.raises(ValueError, match="complete native pin pair"):
        replace(source, pin=changed_pin)
