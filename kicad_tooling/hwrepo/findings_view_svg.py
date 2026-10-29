"""Constrain retained KiCad SVGs and identify the supported coordinate frame."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
_NUMBER_MM = re.compile(r"^([0-9]+(?:\.[0-9]+)?)mm$")
_URL = re.compile(r"url\(\s*['\"]?([^)'\"]+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DrawingSvg:
    content: bytes
    width: float
    height: float
    can_map_mm: bool


def prepare_drawing(data: bytes, kind: str) -> DrawingSvg:
    """Strip the document type and reject active/external content before embedding."""
    try:
        document = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Retained SVG must be UTF-8") from exc
    if "<!ENTITY" in document.upper():
        raise ValueError("SVG entity declarations are not supported")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("Retained drawing is not valid SVG") from exc
    if root.tag != f"{{{SVG}}}svg":
        raise ValueError("Retained drawing is not an SVG document")
    for element in root.iter():
        tag = str(element.tag).rsplit("}", 1)[-1].lower()
        if tag in {"script", "foreignobject", "iframe", "audio", "video"}:
            raise ValueError("Retained SVG contains active content")
        for name, value in element.attrib.items():
            local = name.rsplit("}", 1)[-1].lower()
            lowered = value.lower()
            if local.startswith("on"):
                raise ValueError("Retained SVG contains event handlers")
            if local == "href" and not (
                value.startswith("#")
                or lowered.startswith(("data:image/png;base64,", "data:image/jpeg;base64,"))
            ):
                raise ValueError("Retained SVG contains an external reference")
            if local == "style" and "\\" in value:
                raise ValueError("Retained SVG contains unsupported CSS escapes")
            if "@import" in lowered or any(
                not match.startswith("#") for match in _URL.findall(value)
            ):
                raise ValueError("Retained SVG contains external CSS references")
        if (
            tag == "style"
            and element.text
            and (
                "\\" in element.text
                or "@import" in element.text.lower()
                or any(not match.startswith("#") for match in _URL.findall(element.text))
            )
        ):
            raise ValueError("Retained SVG contains external CSS references")
    fields = root.attrib.get("viewBox", "").replace(",", " ").split()
    if len(fields) != 4:
        raise ValueError("Retained SVG lacks a usable viewBox")
    try:
        x, y, width, height = (float(field) for field in fields)
    except ValueError as exc:
        raise ValueError("Retained SVG has an invalid viewBox") from exc
    if not all(math.isfinite(value) for value in (x, y, width, height)) or not (
        0 < width <= 10000 and 0 < height <= 10000
    ):
        raise ValueError("Retained SVG has an invalid viewBox")
    width_attr = _NUMBER_MM.fullmatch(root.attrib.get("width", ""))
    height_attr = _NUMBER_MM.fullmatch(root.attrib.get("height", ""))
    desc = " ".join((item.text or "") for item in root if item.tag == f"{{{SVG}}}desc")
    producer = "Eeschema-SVG" if kind == "schematic" else "PCBNEW"
    supported = (
        x == 0
        and y == 0
        and width_attr is not None
        and height_attr is not None
        and abs(float(width_attr.group(1)) - width) < 1e-6
        and abs(float(height_attr.group(1)) - height) < 1e-6
        and "transform" not in root.attrib
        and producer in desc
    )
    return DrawingSvg(
        ET.tostring(root, encoding="utf-8", xml_declaration=True), width, height, supported
    )
