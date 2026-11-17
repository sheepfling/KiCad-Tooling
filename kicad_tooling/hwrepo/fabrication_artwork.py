"""Strict parsers for the supported Gerber and IPC-D-356 subset.

The initial geometry subset was adapted from studio-edul's MIT-licensed
``gerber_check.py`` (commit 62921624db3dffdb0afa097f6b270f68acde3c4d).
Unsupported constructs fail closed instead of being approximated silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
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

    @property
    def label(self) -> str:
        return f"{self.reference}-{self.pin}"


def classify_copper_files(
    paths: tuple[Path, ...], copper_layers: tuple[str, ...]
) -> tuple[tuple[Path, str], ...]:
    """Match every copper Gerber to the source board's ordered copper stack."""
    if len(copper_layers) < 2:
        raise UnsupportedFabricationFormat("source board has fewer than two copper layers")
    expected = {name.casefold(): name for name in copper_layers}
    found: dict[str, Path] = {}
    for path in paths:
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
        function = re.search(r"%TF\.FileFunction,([^*]*)\*%", head)
        layer_name: str | None = None
        if function:
            fields = [field.strip().casefold() for field in function.group(1).split(",")]
            if fields and fields[0] == "copper":
                layer_number = next(
                    (
                        int(match.group(1))
                        for field in fields
                        if (match := re.fullmatch(r"l(\d+)", field))
                    ),
                    None,
                )
                if layer_number is None or not 1 <= layer_number <= len(copper_layers):
                    raise UnsupportedFabricationFormat(
                        f"unknown copper layer number in {path.name}"
                    )
                layer_name = copper_layers[layer_number - 1]
                if layer_number == 1 and "top" not in fields:
                    raise UnsupportedFabricationFormat(
                        f"top copper function mismatch in {path.name}"
                    )
                if layer_number == len(copper_layers) and not ({"bot", "bottom"} & set(fields)):
                    raise UnsupportedFabricationFormat(
                        f"bottom copper function mismatch in {path.name}"
                    )
                if 1 < layer_number < len(copper_layers) and (
                    {"top", "bot", "bottom"} & set(fields)
                ):
                    raise UnsupportedFabricationFormat(
                        f"inner copper function mismatch in {path.name}"
                    )
        else:
            name = path.name.casefold()
            normalized = re.sub(r"[_-]", ".", name)
            for key, source_name in expected.items():
                if re.search(rf"(?:^|[._]){re.escape(key)}(?:[._]|$)", normalized):
                    if layer_name is not None:
                        raise UnsupportedFabricationFormat(f"ambiguous copper layer in {path.name}")
                    layer_name = source_name
        if layer_name is None:
            continue
        key = layer_name.casefold()
        if key in found:
            raise UnsupportedFabricationFormat(f"multiple Gerbers for {layer_name}")
        found[key] = path
    if set(found) != set(expected):
        raise UnsupportedFabricationFormat(
            "fabrication connectivity requires one Gerber for every source copper layer"
        )
    return tuple((found[name.casefold()], name) for name in copper_layers)


class GerberParser:
    """Parse a bounded, positive-polarity RS-274X subset into copper features."""

    x: float
    y: float

    def __init__(self, text: str, name: str) -> None:
        self.name = name
        self.features: list[GerberFeature] = []
        self.apertures: dict[int, tuple[str, tuple[float, ...]]] = {}
        self.zero_mode = "L"
        self.scale = 1.0
        self.format = {"X": (2, 6), "Y": (2, 6)}
        self.x = 0.0
        self.y = 0.0
        self.aperture: int | None = None
        self.region: list[tuple[float, float]] | None = None
        self._parse(text)

    def _coordinate(self, raw: str, axis: str) -> float:
        if "." in raw:
            value = float(raw)
        else:
            integer, decimals = self.format[axis]
            sign = -1 if raw.startswith("-") else 1
            digits = raw.lstrip("+-")
            width = integer + decimals
            digits = digits.rjust(width, "0") if self.zero_mode == "L" else digits.ljust(width, "0")
            value = sign * int(digits or "0") / 10**decimals
        return value * self.scale

    def _parse(self, text: str) -> None:
        tokens = tuple(re.finditer(r"%([^%]*)%|([^%*]*)\*", text))
        end_markers: list[int] = [
            index
            for index, match in enumerate(tokens)
            if match.group(1) is None and match.group(2).strip() == "M02"
        ]
        if not end_markers:
            raise UnsupportedFabricationFormat(
                f"Gerber is missing terminal M02 end-of-file marker in {self.name}"
            )
        if len(end_markers) > 1:
            raise UnsupportedFabricationFormat(
                f"Gerber has multiple M02 end-of-file markers in {self.name}"
            )
        marker = tokens[end_markers[0]]
        if end_markers[0] != len(tokens) - 1:
            raise UnsupportedFabricationFormat(
                f"Gerber contains a command after M02 end-of-file marker in {self.name}"
            )
        if text[marker.end() :].strip():
            raise UnsupportedFabricationFormat(
                f"Gerber contains data after the M02 end-of-file marker in {self.name}"
            )

        for match in tokens:
            parameter, command = match.groups()
            if parameter is not None:
                self._parameter(parameter.strip().rstrip("*"))
            else:
                self._command(command.strip())
        if self.region is not None:
            raise UnsupportedFabricationFormat(f"unterminated region in {self.name}")

    def _parameter(self, raw: str) -> None:
        if raw.startswith("FS"):
            match = re.fullmatch(r"FS([LT])([AI])X(\d)(\d)Y(\d)(\d)", raw)
            if not match:
                raise UnsupportedFabricationFormat(f"unsupported coordinate format in {self.name}")
            zero, mode, xi, xd, yi, yd = match.groups()
            if mode != "A":
                raise UnsupportedFabricationFormat(f"incremental Gerber coordinates in {self.name}")
            self.zero_mode = zero
            if (xi, xd) != (yi, yd):
                raise UnsupportedFabricationFormat(f"different X/Y precision in {self.name}")
            self.format = {"X": (int(xi), int(xd)), "Y": (int(yi), int(yd))}
        elif raw.startswith("MO"):
            if raw not in {"MOMM", "MOIN"}:
                raise UnsupportedFabricationFormat(f"unknown Gerber units in {self.name}")
            self.scale = 25.4 if raw == "MOIN" else 1.0
        elif raw.startswith("AD"):
            match = re.fullmatch(r"ADD(\d+)([A-Z]),?(.*)", raw)
            if not match:
                raise UnsupportedFabricationFormat(f"invalid aperture definition in {self.name}")
            number, kind, raw_sizes = match.groups()
            if kind not in {"C", "R", "O", "P"}:
                raise UnsupportedFabricationFormat(f"unsupported {kind} aperture in {self.name}")
            sizes = tuple(float(value) for value in re.split(r"[Xx]", raw_sizes) if value)
            maximum_sizes = {"C": 1, "R": 2, "O": 2, "P": 3}[kind]
            if not sizes or len(sizes) > maximum_sizes:
                raise UnsupportedFabricationFormat(
                    f"unsupported aperture parameters in {self.name}"
                )
            if kind == "P" and len(sizes) < 2:
                raise UnsupportedFabricationFormat(f"incomplete polygon aperture in {self.name}")
            self.apertures[int(number)] = (kind, sizes)
        elif raw.startswith(("IPNEG", "LPC")):
            raise UnsupportedFabricationFormat(f"negative Gerber polarity in {self.name}")
        elif raw.startswith("SR") and re.search(r"(?:X|Y)[2-9]", raw):
            raise UnsupportedFabricationFormat(f"step-and-repeat in {self.name}")
        elif raw.startswith(("LM", "LR", "LS")) and raw not in {"LMN", "LR0", "LS1"}:
            raise UnsupportedFabricationFormat(f"Gerber aperture transform in {self.name}")
        elif raw.startswith(("TF", "TA", "TO", "TD", "LPD")):
            return
        elif raw:
            raise UnsupportedFabricationFormat(
                f"unsupported Gerber parameter %{raw}% in {self.name}"
            )

    def _command(self, raw: str) -> None:
        if not raw or raw.startswith("G04"):
            return
        if re.search(r"G0?[234]|G0?7[45]", raw):
            raise UnsupportedFabricationFormat(f"arc or quadrant interpolation in {self.name}")
        if raw in {"G01", "G1"}:
            return
        if raw in {"G70", "MOIN"}:
            self.scale = 25.4
            return
        if raw in {"G71", "MOMM"}:
            self.scale = 1.0
            return
        if raw in {"G36", "G036"}:
            if self.region is not None:
                raise UnsupportedFabricationFormat(f"nested Gerber region in {self.name}")
            self.region = []
            return
        if raw in {"G37", "G037"}:
            if self.region is None or len(self.region) < 3:
                raise UnsupportedFabricationFormat(f"invalid Gerber region in {self.name}")
            self.features.append(GerberFeature("region", tuple(self.region)))
            self.region = None
            return
        if raw.startswith("D") and raw[1:].isdigit() and int(raw[1:]) >= 10:
            number = int(raw[1:])
            if number not in self.apertures:
                raise UnsupportedFabricationFormat(f"undefined aperture D{number} in {self.name}")
            self.aperture = number
            return
        if raw == "M02":
            return
        matches = {axis: value for axis, value in re.findall(r"([XY])([+-]?[\d.]+)", raw)}
        operation = re.search(r"D0*([123])(?:$|[^\d])", raw)
        if not matches and operation is None:
            raise UnsupportedFabricationFormat(f"unsupported Gerber command {raw!r} in {self.name}")
        nx = self._coordinate(matches["X"], "X") if "X" in matches else self.x
        ny = self._coordinate(matches["Y"], "Y") if "Y" in matches else self.y
        code = int(operation.group(1)) if operation else 1
        if code == 2:
            self.x, self.y = nx, ny
            if self.region is not None:
                if self.region:
                    raise UnsupportedFabricationFormat(
                        f"multiple contours or holes in region in {self.name}"
                    )
                self.region.append((nx, ny))
        elif code == 1:
            if self.region is not None:
                self.region.append((nx, ny))
            else:
                if self.aperture is None:
                    raise UnsupportedFabricationFormat(f"draw without aperture in {self.name}")
                kind, sizes = self.apertures[self.aperture]
                if kind != "C":
                    raise UnsupportedFabricationFormat(
                        f"non-circular stroke aperture in {self.name}"
                    )
                self.features.append(
                    GerberFeature("stroke", ((self.x, self.y), (nx, ny)), sizes[0])
                )
            self.x, self.y = nx, ny
        elif code == 3:
            if self.region is not None or self.aperture is None:
                raise UnsupportedFabricationFormat(f"invalid flash in {self.name}")
            self.features.append(
                GerberFeature("flash", ((nx, ny),), aperture=self.apertures[self.aperture])
            )
            self.x, self.y = nx, ny


def parse_gerber(path: Path, layer: str) -> GerberLayer:
    text = path.read_text(encoding="utf-8", errors="replace")
    parser = GerberParser(text, path.name)
    if not layer.casefold().endswith(".cu"):
        raise UnsupportedFabricationFormat(f"unknown copper layer for {path.name}")
    return GerberLayer(path.name, layer, tuple(parser.features))


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
        coords = re.search(r"A(\d\d)X([ +-]?\d+)Y([ +-]?\d+)(?:X(\d+))?", line[31:])
        if not coords or not reference or (not pin and reference != "VIA"):
            raise UnsupportedFabricationFormat("unrecognized IPC-D-356 contact record")
        pin = pin or "via"
        access, x, y, size = coords.groups()
        if not net or net == "N/C":
            net = f"N/C:{reference}:{pin}"
        layer: Literal["top", "bottom", "through"]
        if line.startswith("317"):
            layer = "through"
        else:
            layer = "top" if int(access) <= 1 else "bottom"
        contacts.append(
            Contact(
                net=net,
                reference=reference,
                pin=pin,
                x_mm=int(x.replace(" ", "")) * unit_mm,
                y_mm=int(y.replace(" ", "")) * unit_mm,
                layer=layer,
                size_mm=int(size) * unit_mm if size else 0.0,
                coordinate_resolution_nm=round(unit_mm * 1_000_000),
            )
        )
    if not contacts:
        raise UnsupportedFabricationFormat("IPC-D-356 has no 317/327 contact records")
    return tuple(contacts)


def drill_file_is_plated(path: Path) -> bool:
    """Classify KiCad PTH/NPTH drill outputs without relying on file order."""
    name = path.name.casefold()
    text = path.read_text(encoding="utf-8", errors="replace")[:4000].casefold()
    function = drill_file_function(path)
    if function is not None:
        if function[0] == "plated":
            return True
        if function[0] == "nonplated":
            return False
        raise UnsupportedFabricationFormat(f"unknown drill plating in {path.name} FileFunction")
    if "nonplated" in text or "non-plated" in text or "npth" in name:
        return False
    if "plated" in text or "pth" in name:
        return True
    raise UnsupportedFabricationFormat(f"cannot determine drill plating for {path.name}")


def drill_file_function(path: Path) -> tuple[str, ...] | None:
    """Read one KiCad X2 drill FileFunction attribute when present."""
    text = path.read_text(encoding="utf-8", errors="replace")[:4000]
    matches = re.findall(r"TF\.FileFunction,([^*%\r\n]+)", text, flags=re.IGNORECASE)
    if not matches:
        return None
    if len(matches) != 1:
        raise UnsupportedFabricationFormat(
            f"drill file has multiple FileFunction attributes in {path.name}"
        )
    fields = tuple(field.strip().casefold() for field in matches[0].split(","))
    if not fields or any(not field for field in fields):
        raise UnsupportedFabricationFormat(f"malformed drill FileFunction in {path.name}")
    return fields
