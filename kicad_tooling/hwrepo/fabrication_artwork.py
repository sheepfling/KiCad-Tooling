"""Strict parsers for the supported Gerber and IPC-D-356 subset.

The initial geometry subset was adapted from studio-edul's MIT-licensed
``gerber_check.py`` (commit 62921624db3dffdb0afa097f6b270f68acde3c4d).
Unsupported constructs fail closed instead of being approximated silently.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from .fabrication_artwork_models import (
    Contact,
    GerberFeature,
    GerberLayer,
    UnsupportedFabricationFormat,
)
from .fabrication_gerber_codes import parse_gerber_aperture_number
from .fabrication_gerber_regions import gerber_region_issue

_GERBER_LINEAR_COMMAND = re.compile(
    r"(?:(?P<interpolation>G01))?"
    r"(?P<x>X[+-]?[0-9]+)?"
    r"(?P<y>Y[+-]?[0-9]+)?"
    r"(?P<operation>D0[123])?"
)
_GERBER_APERTURE_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")


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
        self.scale = 1.0
        self.units_seen = False
        self.format: dict[str, tuple[int, int]] | None = None
        self.operations_started = False
        self.x = 0.0
        self.y = 0.0
        self.aperture: int | None = None
        self.region: list[tuple[float, float]] | None = None
        self._parse(text)

    def _coordinate(self, raw: str, axis: str) -> float:
        if self.format is None:
            raise UnsupportedFabricationFormat(f"Gerber coordinate has no FS format in {self.name}")
        integer, decimals = self.format[axis]
        sign = -1 if raw.startswith("-") else 1
        digits = raw.lstrip("+-")
        width = integer + decimals
        if len(digits) > width:
            raise UnsupportedFabricationFormat(
                f"Gerber {axis} coordinate exceeds its declared FS precision in {self.name}"
            )
        digits = digits.rjust(width, "0")
        value = sign * int(digits or "0") / 10**decimals
        return value * self.scale

    def _aperture_mm(
        self, aperture: tuple[str, tuple[float, ...]]
    ) -> tuple[str, tuple[float, ...]]:
        kind, sizes = aperture
        if kind == "P":
            return kind, (sizes[0] * self.scale, *sizes[1:])
        return kind, tuple(size * self.scale for size in sizes)

    def _require_coordinate_header(self) -> None:
        if not self.units_seen:
            raise UnsupportedFabricationFormat(
                f"Gerber operation precedes its MO unit declaration in {self.name}"
            )
        if self.format is None:
            raise UnsupportedFabricationFormat(
                f"Gerber operation precedes its FS format declaration in {self.name}"
            )

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

        offset = 0
        for match in tokens:
            if text[offset : match.start()].strip():
                raise UnsupportedFabricationFormat(
                    f"Gerber contains unparsed data before a command in {self.name}"
                )
            offset = match.end()

        for match in tokens:
            parameter, command = match.groups()
            if parameter is not None:
                self._parameter(parameter.strip().rstrip("*"))
            else:
                self._command(command.strip())
        if not self.units_seen:
            raise UnsupportedFabricationFormat(
                f"Gerber is missing its MO unit declaration in {self.name}"
            )
        if self.format is None:
            raise UnsupportedFabricationFormat(
                f"Gerber is missing its FS format declaration in {self.name}"
            )
        if self.region is not None:
            raise UnsupportedFabricationFormat(f"unterminated region in {self.name}")

    def _parameter(self, raw: str) -> None:
        if raw.startswith("FS"):
            if self.format is not None:
                raise UnsupportedFabricationFormat(
                    f"Gerber has multiple FS format declarations in {self.name}"
                )
            if self.operations_started:
                raise UnsupportedFabricationFormat(
                    f"Gerber FS format declaration follows an operation in {self.name}"
                )
            match = re.fullmatch(r"FSLAX([0-9])6Y([0-9])6", raw)
            if match is None:
                raise UnsupportedFabricationFormat(
                    f"unsupported Gerber coordinate format in {self.name}"
                )
            xi, yi = (int(value) for value in match.groups())
            if not 1 <= xi <= 6 or not 1 <= yi <= 6:
                raise UnsupportedFabricationFormat(
                    f"unsupported Gerber coordinate precision in {self.name}"
                )
            if xi != yi:
                raise UnsupportedFabricationFormat(f"different X/Y precision in {self.name}")
            self.format = {"X": (xi, 6), "Y": (yi, 6)}
        elif raw.startswith("MO"):
            if self.units_seen:
                raise UnsupportedFabricationFormat(
                    f"Gerber has multiple MO unit declarations in {self.name}"
                )
            if self.operations_started:
                raise UnsupportedFabricationFormat(
                    f"Gerber MO unit declaration follows an operation in {self.name}"
                )
            if raw not in {"MOMM", "MOIN"}:
                raise UnsupportedFabricationFormat(f"unknown Gerber units in {self.name}")
            self.units_seen = True
            self.scale = 25.4 if raw == "MOIN" else 1.0
        elif raw.startswith("AD"):
            match = re.fullmatch(r"ADD([0-9]+)([A-Z]),?(.*)", raw)
            if not match:
                raise UnsupportedFabricationFormat(
                    f"invalid Gerber aperture definition or D-code in {self.name}"
                )
            number_text, kind, raw_sizes = match.groups()
            number = parse_gerber_aperture_number(number_text)
            if number is None:
                raise UnsupportedFabricationFormat(
                    f"invalid Gerber aperture D-code {number_text!r} in {self.name}"
                )
            if number in self.apertures:
                raise UnsupportedFabricationFormat(
                    f"Gerber aperture D{number} cannot be reassigned in {self.name}"
                )
            if kind not in {"C", "R", "O", "P"}:
                raise UnsupportedFabricationFormat(f"unsupported {kind} aperture in {self.name}")
            raw_values = re.split(r"[Xx]", raw_sizes)
            if not raw_values or any(
                _GERBER_APERTURE_DECIMAL.fullmatch(value) is None for value in raw_values
            ):
                raise UnsupportedFabricationFormat(
                    f"Gerber aperture parameters must be finite decimals in {self.name}"
                )
            sizes = tuple(float(value) for value in raw_values)
            if any(not math.isfinite(value) for value in sizes):
                raise UnsupportedFabricationFormat(
                    f"Gerber aperture parameters must be finite decimals in {self.name}"
                )
            if kind == "C" and (len(sizes) != 1 or sizes[0] < 0):
                raise UnsupportedFabricationFormat(
                    f"invalid {kind} aperture parameters in {self.name}"
                )
            if kind in {"R", "O"} and (len(sizes) != 2 or any(size <= 0 for size in sizes)):
                raise UnsupportedFabricationFormat(
                    f"invalid {kind} aperture parameters in {self.name}"
                )
            if kind == "P":
                if len(sizes) not in {2, 3} or sizes[0] <= 0:
                    raise UnsupportedFabricationFormat(
                        f"invalid {kind} aperture parameters in {self.name}"
                    )
                vertex_token = raw_values[1]
                if re.fullmatch(r"[0-9]+", vertex_token) is None:
                    raise UnsupportedFabricationFormat(
                        f"invalid {kind} aperture parameters in {self.name}"
                    )
                vertex_count_text = vertex_token.lstrip("0") or "0"
                if len(vertex_count_text) > 2 or not 3 <= int(vertex_count_text) <= 12:
                    raise UnsupportedFabricationFormat(
                        f"invalid {kind} aperture parameters in {self.name}"
                    )
            self.apertures[number] = (kind, sizes)
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
        if re.match(r"G0?(?:[234]|7[45])(?=$|[XYIJD])", raw):
            raise UnsupportedFabricationFormat(f"arc or quadrant interpolation in {self.name}")
        if raw == "G01":
            return
        if raw in {"G70", "G71", "MOIN", "MOMM"}:
            raise UnsupportedFabricationFormat(
                f"legacy Gerber unit command requires an MO header declaration in {self.name}"
            )
        if raw in {"G36", "G036"}:
            self._require_coordinate_header()
            self.operations_started = True
            if self.region is not None:
                raise UnsupportedFabricationFormat(f"nested Gerber region in {self.name}")
            self.region = []
            return
        if raw in {"G37", "G037"}:
            issue = gerber_region_issue(self.region)
            if issue is not None:
                raise UnsupportedFabricationFormat(f"{issue} in {self.name}")
            assert self.region is not None
            self.features.append(GerberFeature("region", tuple(self.region)))
            self.region = None
            return
        if raw.startswith("D") and raw[1:].isdigit():
            number = parse_gerber_aperture_number(raw[1:])
            if number is None:
                raise UnsupportedFabricationFormat(
                    f"invalid Gerber aperture D-code {raw[1:]!r} in {self.name}"
                )
            if number not in self.apertures:
                raise UnsupportedFabricationFormat(f"undefined aperture D{number} in {self.name}")
            self.aperture = number
            return
        if raw == "M02":
            return
        command = _GERBER_LINEAR_COMMAND.fullmatch(raw)
        if command is None:
            raise UnsupportedFabricationFormat(
                f"unsupported Gerber coordinate command {raw!r} in {self.name}"
            )
        x_coordinate = command.group("x")
        y_coordinate = command.group("y")
        operation = command.group("operation")
        if x_coordinate is not None or y_coordinate is not None or operation is not None:
            self._require_coordinate_header()
            self.operations_started = True
        if (x_coordinate is not None or y_coordinate is not None) and operation is None:
            raise UnsupportedFabricationFormat(
                f"Gerber coordinate command {raw!r} is missing a D01/D02/D03 operation in {self.name}"
            )
        nx = self._coordinate(x_coordinate[1:], "X") if x_coordinate else self.x
        ny = self._coordinate(y_coordinate[1:], "Y") if y_coordinate else self.y
        code = int(operation[-1]) if operation else 1
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
                    GerberFeature("stroke", ((self.x, self.y), (nx, ny)), sizes[0] * self.scale)
                )
            self.x, self.y = nx, ny
        elif code == 3:
            if self.region is not None or self.aperture is None:
                raise UnsupportedFabricationFormat(f"invalid flash in {self.name}")
            self.features.append(
                GerberFeature(
                    "flash",
                    ((nx, ny),),
                    aperture=self._aperture_mm(self.apertures[self.aperture]),
                )
            )
            self.x, self.y = nx, ny


def parse_gerber(path: Path, layer: str) -> GerberLayer:
    text = path.read_text(encoding="utf-8", errors="replace")
    parser = GerberParser(text, path.name)
    if not layer.casefold().endswith(".cu"):
        raise UnsupportedFabricationFormat(f"unknown copper layer for {path.name}")
    return GerberLayer(path.name, layer, tuple(parser.features))


def parse_ipc356(text: str) -> tuple[Contact, ...]:
    """Read IPC-D-356 through the focused contact parser."""
    from .fabrication_ipc356 import parse_ipc356 as parse_contacts

    return parse_contacts(text)
