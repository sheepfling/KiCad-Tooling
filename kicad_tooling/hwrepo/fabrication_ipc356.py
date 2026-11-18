"""Parse the supported IPC-D-356A contact-record subset."""

from __future__ import annotations

import math
import re
from typing import Literal

from .fabrication_artwork_models import Contact, UnsupportedFabricationFormat


def _ipc356_scaled_integer(raw: str, unit_mm: float, field: str) -> float:
    try:
        value = int(raw.replace(" ", "")) * unit_mm
    except (OverflowError, ValueError) as exc:
        raise UnsupportedFabricationFormat(
            f"IPC-D-356 numeric field {field} is unrepresentable"
        ) from exc
    if not math.isfinite(value):
        raise UnsupportedFabricationFormat(f"IPC-D-356 numeric field {field} is non-finite")
    return value


def parse_ipc356(text: str) -> tuple[Contact, ...]:
    """Read the KiCad-exported IPC-D-356A contact records and declared units."""
    unit_mm = 0.00254  # CUST 0: 0.0001 inch
    contacts: list[Contact] = []
    for line in text.splitlines():
        if line.startswith("P") and "UNITS" in line:
            if re.search(r"CUST\s+1|\bSI\b", line):
                unit_mm = 0.001
            elif re.search(r"CUST\s+0", line):
                unit_mm = 0.00254
            else:
                raise UnsupportedFabricationFormat("unsupported IPC-D-356 units")
            continue
        if line.startswith("999"):
            break
        if not line.startswith(("317", "327")):
            continue
        if len(line) < 48:
            raise UnsupportedFabricationFormat("truncated IPC-D-356 contact record")
        net = line[3:17].strip()
        reference = line[20:26].strip()
        pin = line[27:31].strip()
        coords = re.search(
            r"A([0-9]{2})X([ +-]?[0-9]+)Y([ +-]?[0-9]+)"
            r"(?:X([0-9]+)Y([0-9]+)R[0-9]{3}S[0-9])?",
            line[31:],
        )
        if not coords or not reference or (not pin and reference != "VIA"):
            raise UnsupportedFabricationFormat("unrecognized IPC-D-356 contact record")
        pin = pin or "via"
        access, x, y, size_x, size_y = coords.groups()
        access_code = int(access)
        size_x_mm = _ipc356_scaled_integer(size_x, unit_mm, "X pad size") if size_x else None
        size_y_mm = _ipc356_scaled_integer(size_y, unit_mm, "Y pad size") if size_y else None
        size_mm = max(size_x_mm or 0.0, size_y_mm or 0.0)
        if not net or net == "N/C":
            net = f"N/C:{reference}:{pin}"
        layer: Literal["top", "bottom", "through"]
        if line.startswith("317") or access_code == 0:
            layer = "through"
        elif access_code == 1:
            layer = "top"
        else:
            layer = "bottom"
        contacts.append(
            Contact(
                net=net,
                reference=reference,
                pin=pin,
                x_mm=_ipc356_scaled_integer(x, unit_mm, "X coordinate"),
                y_mm=_ipc356_scaled_integer(y, unit_mm, "Y coordinate"),
                layer=layer,
                size_mm=size_mm,
                coordinate_resolution_nm=round(unit_mm * 1_000_000),
                size_x_mm=size_x_mm,
                size_y_mm=size_y_mm,
                access_code=access_code,
            )
        )
    if not contacts:
        raise UnsupportedFabricationFormat("IPC-D-356 has no 317/327 contact records")
    return tuple(contacts)
