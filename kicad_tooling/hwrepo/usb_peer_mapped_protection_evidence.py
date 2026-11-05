"""Serialize exact project-mapped USB protection-pin evidence for peer paths."""

from __future__ import annotations

from .usb_data_path_models import UsbDataInterfaceRequirement
from .usb_peer_reference_types import (
    UsbPeerDataProtectionShunt,
    UsbPeerDataProtectionShuntPin,
)


def mapped_protection_shunt_evidence(
    interface: UsbDataInterfaceRequirement,
) -> tuple[UsbPeerDataProtectionShunt, ...]:
    """Convert an authored shunt map to deterministic path evidence."""
    return tuple(
        sorted(
            (
                UsbPeerDataProtectionShunt(
                    reference=shunt.reference,
                    symbol=shunt.expected_symbol,
                    footprint=shunt.expected_footprint,
                    data_pins=tuple(
                        UsbPeerDataProtectionShuntPin(
                            line=item.line,
                            pin=item.pin,
                            net=item.net,
                        )
                        for item in sorted(
                            shunt.data_pins,
                            key=lambda item: (item.line, item.pin.casefold(), item.pin),
                        )
                    ),
                    pin_assignments=tuple(
                        sorted(
                            (
                                f"{item.pin}={item.net}"
                                if item.disposition == "net"
                                else f"{item.pin}=<unconnected>"
                                for item in shunt.pins
                            ),
                            key=lambda item: (item.casefold(), item),
                        )
                    ),
                )
                for shunt in interface.protection_shunts
            ),
            key=lambda item: (item.reference.casefold(), item.reference),
        )
    )
