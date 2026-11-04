"""Typed authored USB path inputs with one canonical map identity."""

from __future__ import annotations

from dataclasses import dataclass

from .usb_data_path_models import UsbDataPathMap, usb_data_path_map_sha256


@dataclass(frozen=True, slots=True)
class UsbDataPathCandidateInputs:
    """Keep the authored topology and its content digest together."""

    authored_map: UsbDataPathMap | None
    map_sha256: str | None = None

    def __post_init__(self) -> None:
        expected = usb_data_path_map_sha256(self.authored_map)
        if self.map_sha256 is not None and self.map_sha256 != expected:
            raise ValueError("USB data-path map digest must match its authored map")
        object.__setattr__(self, "map_sha256", expected)
