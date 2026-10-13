"""Create a synthetic native PCB with one explicitly stored assembly variant."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pcbnew as _pcbnew  # type: ignore[import-not-found]

native_pcbnew: Any = cast(Any, _pcbnew)


def main(arguments: list[str] | None = None) -> None:
    """Copy one synthetic board and set the named variant DNP state for U1."""
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 4:
        raise SystemExit("usage: build_variant_board.py INPUT OUTPUT VARIANT U1_DNP")
    input_path, output_path = (Path(value) for value in values[:2])
    variant, raw_dnp = values[2:]
    if not variant.strip() or raw_dnp not in {"true", "false"}:
        raise ValueError("Variant name and DNP state must be explicit")

    board = native_pcbnew.LoadBoard(str(input_path))
    if board is None:
        raise ValueError("KiCad could not load the synthetic PCB fixture")
    board.AddVariant(variant)
    target_found = False
    for footprint in board.GetFootprints():
        if footprint.GetReference().casefold() == "u1":
            footprint.AddVariant(variant).SetDNP(raw_dnp == "true")
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
