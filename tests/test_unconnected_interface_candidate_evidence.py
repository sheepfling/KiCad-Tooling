"""Protocol-pin candidates retain typed scan records at the report boundary."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.bus_signal_roles import UnconnectedInterfacePin
from kicad_tooling.hwrepo.can_unconnected_direction_pins import UnconnectedCanDirectionPin
from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.design_lint_unconnected_interface_candidate_evidence import (
    UnconnectedInterfaceCandidate,
    UnconnectedInterfaceEvidence,
)
from kicad_tooling.hwrepo.design_lint_unconnected_interface_candidates import (
    unconnected_interface_candidates,
)
from kicad_tooling.hwrepo.i2c_unconnected_pins import UnconnectedI2cSignalPin
from kicad_tooling.hwrepo.serial_unconnected_pins import UnconnectedSerialFunctionPin
from kicad_tooling.hwrepo.spi_unconnected_clock_pin import UnconnectedSpiClockPin
from kicad_tooling.hwrepo.spi_unconnected_data_pins import UnconnectedSpiDataPin
from kicad_tooling.hwrepo.usb_unconnected_data import UnconnectedUsbDataPin
from tests.design_lint_fixtures import unconnected_protocol_pins

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]


@pytest.mark.parametrize(
    ("source", "rule_id", "evidence"),
    (
        pytest.param(
            UnconnectedI2cSignalPin("U1.1", "SDA", "SDA", "U1.2", "I2C_CLOCK"),
            "bus.i2c_unconnected_pin",
            {
                "U1.1": (),
                "function": ("SDA",),
                "i2c_role": ("SDA",),
                "paired_pin": ("U1.2",),
                "paired_net": ("I2C_CLOCK",),
            },
            id="i2c",
        ),
        pytest.param(
            UnconnectedCanDirectionPin("U1.1", "CAN1_RX", "rx", "can:index1", "U1.2", "CAN1_TX"),
            "bus.can_unconnected_direction_pin",
            {
                "U1.1": (),
                "function": ("CAN1_RX",),
                "can_role": ("RX",),
                "can_channel": ("can:index1",),
                "paired_pin": ("U1.2",),
                "paired_net": ("CAN1_TX",),
            },
            id="can-direction",
        ),
        pytest.param(
            UnconnectedInterfacePin("spi", "U1.1", "CS_N"),
            "bus.spi_unconnected_chip_select",
            {"U1.1": (), "function": ("CS_N",)},
            id="spi-chip-select",
        ),
        pytest.param(
            UnconnectedInterfacePin("usb_c", "J1.1", "CC1"),
            "bus.usb_c_unconnected_cc_pin",
            {"J1.1": (), "function": ("CC1",)},
            id="usb-c-cc",
        ),
        pytest.param(
            UnconnectedInterfacePin("can", "J1.1", "CANH"),
            "bus.can_unconnected_line",
            {"J1.1": (), "function": ("CANH",)},
            id="can-line",
        ),
        pytest.param(
            UnconnectedUsbDataPin("J1.1", "DP1", "1", "positive", "J1.2", "DM1", "USB_DM"),
            "bus.usb_unconnected_data_pin",
            {
                "J1.1": (),
                "function": ("DP1",),
                "USB_data_side": ("D+",),
                "paired_pin": ("J1.2",),
                "paired_function": ("DM1",),
                "paired_net": ("USB_DM",),
                "USB_data_port_index": ("1",),
            },
            id="usb-data-with-port",
        ),
        pytest.param(
            UnconnectedUsbDataPin("J1.1", "USBDM", None, "negative", "J1.2", "USBDP", "USB_DP"),
            "bus.usb_unconnected_data_pin",
            {
                "J1.1": (),
                "function": ("USBDM",),
                "USB_data_side": ("D−",),
                "paired_pin": ("J1.2",),
                "paired_function": ("USBDP",),
                "paired_net": ("USB_DP",),
            },
            id="usb-data-no-port",
        ),
        pytest.param(
            UnconnectedSpiDataPin("U1.1", "MOSI", "input", "default"),
            "bus.spi_unconnected_data_pin",
            {
                "U1.1": (),
                "function": ("MOSI",),
                "spi_data_family": ("MOSI-family",),
                "spi_channel": ("default",),
            },
            id="spi-data",
        ),
        pytest.param(
            UnconnectedSpiClockPin("U1.1", "SCK", "default", ("U1.2",)),
            "bus.spi_unconnected_clock_pin",
            {
                "U1.1": (),
                "function": ("SCK",),
                "spi_channel": ("default",),
                "active_peer_pins": ("U1.2",),
            },
            id="spi-clock",
        ),
        pytest.param(
            UnconnectedSerialFunctionPin("U1.1", "UART_TX", "tx", "uart:default"),
            "bus.serial_unconnected_pin",
            {
                "U1.1": (),
                "function": ("UART_TX",),
                "serial_role": ("TX",),
                "serial_channel": ("uart:default",),
            },
            id="serial",
        ),
    ),
)
def test_projection_retains_each_typed_protocol_pin_source(
    source: UnconnectedInterfaceEvidence,
    rule_id: str,
    evidence: dict[str, tuple[str, ...]],
) -> None:
    candidate = UnconnectedInterfaceCandidate.from_source_evidence(
        source,
        subject=f"{source.pin}: {source.function}",
        message="synthetic review",
    )

    assert candidate.source_evidence is source
    assert candidate.rule_id == rule_id
    assert candidate.evidence == evidence
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_protocol_pin_scanner_returns_candidates_with_their_source_records() -> None:
    candidates = unconnected_interface_candidates(unconnected_protocol_pins())
    report_candidates = tuple(
        item
        for item in candidates
        if isinstance(item, UnconnectedInterfaceCandidate)
        and item.rule_id
        in {
            "bus.i2c_unconnected_pin",
            "bus.spi_unconnected_chip_select",
            "bus.usb_c_unconnected_cc_pin",
        }
    )

    assert len(report_candidates) == 4
    assert {type(item.source_evidence) for item in report_candidates} == {
        UnconnectedI2cSignalPin,
        UnconnectedInterfacePin,
    }
