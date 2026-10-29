"""Create a synthetic native PCB with one explicitly stored assembly variant."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, cast

import pcbnew as _pcbnew  # type: ignore[import-not-found]


class FootprintVariant(Protocol):
    def SetDNP(self, value: bool) -> None: ...

    def SetFieldValue(self, name: str, value: str) -> None: ...


class BoardFootprint(Protocol):
    def GetReference(self) -> str: ...

    def AddVariant(self, variant: str) -> FootprintVariant: ...


class Board(Protocol):
    def AddVariant(self, variant: str) -> object: ...

    def GetFootprints(self) -> Sequence[BoardFootprint]: ...


class NativePcbnew(Protocol):
    def LoadBoard(self, path: str) -> Board | None: ...

    def SaveBoard(self, path: str, board: Board) -> None: ...


native_pcbnew = cast(NativePcbnew, _pcbnew)


def main(arguments: Sequence[str] | None = None) -> None:
    """Copy one synthetic board and set the named variant DNP state for U1."""
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) not in {4, 5}:
        raise SystemExit(
            "usage: build_variant_board.py INPUT OUTPUT VARIANT U1_DNP [U1_VARIANT_VALUE]"
        )
    input_path, output_path = (Path(value) for value in values[:2])
    variant, raw_dnp = values[2:4]
    variant_value = values[4] if len(values) == 5 else None
    if not variant.strip() or raw_dnp not in {"true", "false"}:
        raise ValueError("Variant name and DNP state must be explicit")

    board = native_pcbnew.LoadBoard(str(input_path))
    if board is None:
        raise ValueError("KiCad could not load the synthetic PCB fixture")
    board.AddVariant(variant)
    target_found = False
    for footprint in board.GetFootprints():
        if footprint.GetReference().casefold() == "u1":
            footprint_variant = footprint.AddVariant(variant)
            footprint_variant.SetDNP(raw_dnp == "true")
            if variant_value is not None:
                footprint_variant.SetFieldValue("Value", variant_value)
            target_found = True
        else:
            footprint.AddVariant(variant).SetDNP(False)
    if not target_found:
        raise ValueError("Synthetic PCB fixture is missing U1")
    native_pcbnew.SaveBoard(str(output_path), board)
    if not output_path.is_file():
        raise ValueError("KiCad did not save the synthetic variant PCB")


if __name__ == "__main__":
    main()
