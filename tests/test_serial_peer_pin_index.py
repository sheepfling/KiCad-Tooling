"""Named, single-source indexes for serial-peer review scans."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.serial_peer_reference_domains import pin_index
from kicad_tooling.hwrepo.serial_peer_reference_types import SerialPeerPinIndex
from tests.serial_peer_reference_support import serial_reference_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def test_pin_index_keeps_all_native_indexes_in_one_named_record() -> None:
    observed = serial_reference_netlist(dnp=("U2",))

    index = pin_index(observed)

    assert isinstance(index, SerialPeerPinIndex)
    assert index.pin_nets["u1.1"] == frozenset({"UART_A"})
    assert index.references == {"u1": "U1", "u2": "U2"}
    assert index.symbols["u1"] == "Synthetic:UartTransmitter"
    assert index.footprints["u1"] == "Package:UART-TX"
    assert index.pin_numbers["u1"] == ("1", "2", "8", "9")
    assert index.dnp_references == frozenset({"u2"})
    with pytest.raises(TypeError):
        index.references["u1"] = "U99"  # type: ignore[index]
