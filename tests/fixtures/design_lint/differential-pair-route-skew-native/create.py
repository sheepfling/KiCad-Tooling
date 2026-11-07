"""Generate synthetic pair boards with matched and excessive routed skew."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from itertools import pairwise
from pathlib import Path

import pcbnew

_FOOTPRINT_LIBRARY = Path("/usr/share/kicad/footprints/Connector_PinHeader_2.54mm.pretty")
_FOOTPRINT_NAME = "PinHeader_1x02_P2.54mm_Vertical"


def _add_footprint(
    board: pcbnew.BOARD,
    reference: str,
    position_mm: tuple[float, float],
    nets: dict[str, pcbnew.NETINFO_ITEM],
) -> dict[str, pcbnew.PAD]:
    footprint = pcbnew.FootprintLoad(str(_FOOTPRINT_LIBRARY), _FOOTPRINT_NAME)
    if footprint is None:
        raise RuntimeError(f"Could not load synthetic footprint {_FOOTPRINT_NAME}")
    footprint.SetReference(reference)
    footprint.SetValue("SYNTHETIC")
    footprint.Reference().SetVisible(False)
    footprint.Value().SetVisible(False)
    footprint.SetPosition(
        pcbnew.VECTOR2I(pcbnew.FromMM(position_mm[0]), pcbnew.FromMM(position_mm[1]))
    )
    board.Add(footprint)
    pads = {str(pad.GetNumber()): pad for pad in footprint.Pads()}
    if set(pads) != {"1", "2"}:
        raise RuntimeError(f"Synthetic footprint pad inventory changed: {sorted(pads)}")
    pads["1"].SetNet(nets["USB_DP"])
    pads["2"].SetNet(nets["USB_DN"])
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
    track.SetWidth(pcbnew.FromMM(0.18))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(net)
    board.Add(track)


def _points_on_grid(
    coordinates_mm: Iterable[tuple[float, float]],
) -> tuple[pcbnew.VECTOR2I, ...]:
    return tuple(
        pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm)) for x_mm, y_mm in coordinates_mm
    )


def create(output: Path, expected_version: str) -> None:
    actual = pcbnew.GetBuildVersion()
    if actual != expected_version:
        raise RuntimeError(f"pcbnew version {actual} differs from {expected_version}")
    if not _FOOTPRINT_LIBRARY.is_dir():
        raise RuntimeError(f"Pinned KiCad image has no footprint library: {_FOOTPRINT_LIBRARY}")
    (output / "kicad-version.txt").write_text(f"{actual}\n", encoding="utf-8")
    for case in ("control", "fault"):
        board = pcbnew.BOARD()
        nets = {name: pcbnew.NETINFO_ITEM(board, name) for name in ("USB_DP", "USB_DN")}
        for net in nets.values():
            board.Add(net)
        source_pads = _add_footprint(board, "J1", (10.0, 10.0), nets)
        receiver_pads = _add_footprint(board, "U1", (40.0, 10.0), nets)
        _add_track(
            board,
            source_pads["1"].GetPosition(),
            receiver_pads["1"].GetPosition(),
            nets["USB_DP"],
        )
        if case == "control":
            midpoint = pcbnew.VECTOR2I(pcbnew.FromMM(25.0), pcbnew.FromMM(12.54))
            spur_end = pcbnew.VECTOR2I(pcbnew.FromMM(25.0), pcbnew.FromMM(14.54))
            _add_track(
                board,
                source_pads["2"].GetPosition(),
                midpoint,
                nets["USB_DN"],
            )
            _add_track(
                board,
                midpoint,
                receiver_pads["2"].GetPosition(),
                nets["USB_DN"],
            )
            _add_track(
                board,
                midpoint,
                spur_end,
                nets["USB_DN"],
            )
        else:
            start_y_mm = 12.54
            points = _points_on_grid(
                (
                    (10.0, start_y_mm),
                    (15.0, start_y_mm),
                    (15.0, 22.54),
                    (35.0, 22.54),
                    (35.0, start_y_mm),
                    (40.0, start_y_mm),
                )
            )
            if (
                points[0] != source_pads["2"].GetPosition()
                or points[-1] != receiver_pads["2"].GetPosition()
            ):
                raise RuntimeError("Synthetic footprint pin positions changed")
            for first, second in pairwise(points):
                _add_track(board, first, second, nets["USB_DN"])
        board_path = output / f"{case}.kicad_pcb"
        if not pcbnew.SaveBoard(str(board_path), board):
            raise RuntimeError(f"KiCad could not save {board_path.name}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: create.py OUTPUT_DIR KICAD_VERSION")
    output_directory = Path(sys.argv[1])
    output_directory.mkdir(parents=True, exist_ok=True)
    create(output_directory, sys.argv[2])
