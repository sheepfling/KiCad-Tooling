"""Typed intermediate records shared by the fabrication artifact parsers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class UnsupportedFabricationFormat(ValueError):
    """Input uses a fabrication feature outside this analyzer's declared subset."""


@dataclass(frozen=True)
class GerberFeature:
    kind: Literal["stroke", "flash", "region"]
    points: tuple[tuple[float, float], ...]
    width_mm: float = 0.0
    aperture: tuple[str, tuple[float, ...]] | None = None


@dataclass(frozen=True)
class GerberLayer:
    name: str
    layer: str
    features: tuple[GerberFeature, ...]


@dataclass(frozen=True)
class Contact:
    net: str
    reference: str
    pin: str
    x_mm: float
    y_mm: float
    layer: Literal["top", "bottom", "through"]
    size_mm: float
    coordinate_resolution_nm: int = 2_540
    size_x_mm: float | None = None
    size_y_mm: float | None = None
    access_code: int | None = None

    @property
    def label(self) -> str:
        return f"{self.reference}-{self.pin}"
