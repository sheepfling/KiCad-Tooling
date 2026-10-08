"""Generate small synthetic pad-to-pad boards for native KiCad DRC testing."""

from __future__ import annotations

import sys
from pathlib import Path

import pcbnew

_FOOTPRINT_LIBRARY = Path("/usr/share/kicad/footprints/Connector_PinHeader_2.54mm.pretty")
_FOOTPRINT_NAME = "PinHeader_1x02_P2.54mm_Vertical"


def _edge(board: pcbnew.BOARD, start: tuple[float, float], end: tuple[float, float]) -> None:
    shape = pcbnew.PCB_SHAPE()
    shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
    shape.SetLayer(pcbnew.Edge_Cuts)
    shape.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(start[0]), pcbnew.FromMM(start[1])))
    shape.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(end[0]), pcbnew.FromMM(end[1])))
    shape.SetWidth(pcbnew.FromMM(0.05))
    board.Add(shape)


def _add_footprint(
    board: pcbnew.BOARD,
    reference: str,
    x_mm: float,
    y_mm: float,
    nets: dict[str, pcbnew.NETINFO_ITEM],
) -> dict[str, pcbnew.PAD]:
    footprint = pcbnew.FootprintLoad(str(_FOOTPRINT_LIBRARY), _FOOTPRINT_NAME)
    if footprint is None:
        raise RuntimeError(f"Could not load synthetic test footprint {_FOOTPRINT_NAME}")
    footprint.SetReference(reference)
    footprint.SetValue("SYNTHETIC")
    footprint.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm)))
    board.Add(footprint)
    pads = {pad.GetNumber(): pad for pad in footprint.Pads()}
    if set(pads) != {"1", "2"}:
        raise RuntimeError(f"Synthetic footprint pads changed unexpectedly: {sorted(pads)}")
    pads["1"].SetNet(nets["SYNTH_CLK"])
    pads["2"].SetNet(nets["SYNTH_DATA"])
    return pads


def _add_track(
    board: pcbnew.BOARD,
    start: pcbnew.VECTOR2I,
    end: pcbnew.VECTOR2I,
    net: pcbnew.NETINFO_ITEM,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetWidth(pcbnew.FromMM(0.25))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(net)
    board.Add(track)


def _rules(
    directory: Path,
    name: str,
    maximum_mm: float,
    skew_mm: float,
    *,
    ignore_severity: bool = False,
) -> None:
    severity = "(severity ignore)\n  " if ignore_severity else ""
    source = f"""(version 1)
(rule \"synthetic-clock-length\"
  {severity}(condition \"A.fromTo('J1-1', 'U1-1')\")
  (constraint length (max {maximum_mm:g}mm)))
(rule \"synthetic-data-length\"
  {severity}(condition \"A.fromTo('J1-2', 'U1-2')\")
  (constraint length (max {maximum_mm:g}mm)))
(rule \"synthetic-data-skew\"
  {severity}(condition \"A.fromTo('J1-*', 'U1-*')\")
  (constraint skew (max {skew_mm:g}mm)))
"""
    (directory / f"{name}.kicad_dru").write_text(source, encoding="utf-8")


def create(directory: Path, expected_version: str) -> None:
    version = pcbnew.GetBuildVersion()
    if version != expected_version:
        raise RuntimeError(f"pcbnew version {version} differs from {expected_version}")
    if not _FOOTPRINT_LIBRARY.is_dir():
        raise RuntimeError(f"Pinned KiCad image has no footprint library: {_FOOTPRINT_LIBRARY}")

    for case, maximum_mm, skew_mm, ignore_severity in (
        ("control", 50.0, 30.0, False),
        ("fault", 22.0, 1.0, False),
        ("ignored", 22.0, 1.0, True),
    ):
        board = pcbnew.BOARD()
        nets = {name: pcbnew.NETINFO_ITEM(board, name) for name in ("SYNTH_CLK", "SYNTH_DATA")}
        for net in nets.values():
            board.Add(net)
        source_pads = _add_footprint(board, "J1", 10.0, 10.0, nets)
        receiver_pads = _add_footprint(board, "U1", 30.0, 10.0, nets)

        _add_track(
            board,
            source_pads["1"].GetPosition(),
            receiver_pads["1"].GetPosition(),
            nets["SYNTH_CLK"],
        )
        start = source_pads["2"].GetPosition()
        end = receiver_pads["2"].GetPosition()
        midpoint_x = pcbnew.FromMM(20.0)
        offset_y = pcbnew.FromMM(12.0)
        _add_track(
            board,
            start,
            pcbnew.VECTOR2I(midpoint_x, start.y + offset_y),
            nets["SYNTH_DATA"],
        )
        _add_track(
            board,
            pcbnew.VECTOR2I(midpoint_x, end.y + offset_y),
            end,
            nets["SYNTH_DATA"],
        )

        outline = ((5.0, 5.0), (35.0, 5.0), (35.0, 30.0), (5.0, 30.0))
        for start_point, end_point in zip(outline, (*outline[1:], outline[0]), strict=True):
            _edge(board, start_point, end_point)

        board_path = directory / f"{case}.kicad_pcb"
        if not pcbnew.SaveBoard(str(board_path), board):
            raise RuntimeError(f"KiCad could not save {board_path.name}")
        _rules(directory, case, maximum_mm, skew_mm, ignore_severity=ignore_severity)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: create.py OUTPUT_DIR KICAD_VERSION")
    output_directory = Path(sys.argv[1])
    output_directory.mkdir(parents=True, exist_ok=True)
    create(output_directory, sys.argv[2])
