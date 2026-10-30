"""Read placed footprint anchors from one hash-checked KiCad board source."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from .model_inventory import _atoms, _children  # pyright: ignore[reportPrivateUsage]


@dataclass(frozen=True, slots=True)
class BoardFootprintAnchor:
    reference: str
    footprint: str
    x_mm: float | None
    y_mm: float | None
    side: Literal["F.Cu", "B.Cu"] | None
    issue: str | None = None


def board_footprint_anchors(source: bytes) -> dict[str, tuple[BoardFootprintAnchor, ...]]:
    """Keep malformed and duplicate references visible without assigning a location."""
    try:
        text = source.decode("utf-8")
        roots = _children(text, 0, len(text))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Malformed KiCad PCB source") from exc
    if len(roots) != 1 or _atoms(text, roots[0])[:1] != ("kicad_pcb",):
        raise ValueError("Expected one kicad_pcb root")
    found: dict[str, list[BoardFootprintAnchor]] = defaultdict(list)
    for node in _children(text, roots[0].start + 1, roots[0].end - 1):
        header = _atoms(text, node)
        if not header or header[0] not in {"footprint", "module"}:
            continue
        footprint = header[1] if len(header) > 1 else ""
        children = _children(text, node.start + 1, node.end - 1)
        atoms = tuple(_atoms(text, child) for child in children)
        references = [
            item[2] for item in atoms if len(item) == 3 and item[:2] == ("property", "Reference")
        ]
        if not references:
            references = [
                item[2] for item in atoms if len(item) >= 3 and item[:2] == ("fp_text", "reference")
            ]
        if not references or not references[0]:
            continue
        reference = references[0]
        issue: str | None = None
        if len(references) != 1:
            issue = "Footprint has multiple reference fields"
        positions = [item for item in atoms if item[:1] == ("at",)]
        layers = [item for item in atoms if item[:1] == ("layer",)]
        x_mm: float | None = None
        y_mm: float | None = None
        side: Literal["F.Cu", "B.Cu"] | None = None
        if len(positions) != 1 or len(positions[0]) not in {3, 4}:
            issue = "Footprint has no unique position"
        else:
            try:
                x_mm, y_mm = float(positions[0][1]), float(positions[0][2])
            except ValueError:
                issue = "Footprint position is not numeric"
            else:
                if not math.isfinite(x_mm) or not math.isfinite(y_mm):
                    issue = "Footprint position is not finite"
        if len(layers) != 1 or len(layers[0]) != 2 or layers[0][1] not in {"F.Cu", "B.Cu"}:
            issue = "Footprint side is unsupported"
        else:
            side = layers[0][1]  # pyright: ignore[reportAssignmentType]
        found[reference.casefold()].append(
            BoardFootprintAnchor(reference, footprint, x_mm, y_mm, side, issue)
        )
    return {key: tuple(values) for key, values in found.items()}
