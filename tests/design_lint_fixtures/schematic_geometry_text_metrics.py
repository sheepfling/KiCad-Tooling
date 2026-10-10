"""Synthetic schematic content for text-metric parity tests."""

from __future__ import annotations

from tests.design_lint_fixtures.schematic_geometry_fixtures import CONTROL


def calibrated_stroke_text_metrics_fixture() -> bytes:
    """Render every calibrated standard-stroke glyph from one synthetic source."""
    source = CONTROL.read_text(encoding="utf-8")
    characters = " " + "".join(chr(code) for code in range(33, 127)) + "—µΩ°±×"

    def quoted(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    nodes = "\n".join(
        f"  (text {quoted(character)} (at 30 30 0) "
        f"(effects (font (size 1.27 1.27))) "
        f'(uuid "e0000000-0000-4000-8000-{index + 1:012x}"))'
        for index, character in enumerate(characters)
    )
    marker = "  (sheet_instances"
    if marker not in source:
        raise AssertionError("synthetic schematic fixture has no sheet_instances node")
    return source.replace(marker, f"{nodes}\n{marker}", 1).encode("utf-8")
