"""Shared pinned-KiCad invocation for fabrication artifact regressions."""

from __future__ import annotations

from pathlib import Path

from tests.native_kicad_support import execute_kicad_cli


def run_kicad_cli(
    image: str,
    work: Path,
    fixture_directory: Path,
    output_directory: Path,
    board: Path,
    arguments: tuple[str, ...],
) -> None:
    """Run one command in the pinned KiCad lane and require clean completion."""
    command = execute_kicad_cli(
        image,
        ("kicad-cli", *arguments, str(board)),
        work,
        home_directory="fabrication-connectivity-native",
        fixture_directory=fixture_directory,
        output_directory=output_directory,
    )
    assert command.returncode == 0, command.stderr
    assert command.error is None


def export_fabrication_outputs(
    image: str,
    work: Path,
    fixture_directory: Path,
    output_directory: Path,
    board: Path,
    copper_layers: tuple[str, ...],
) -> None:
    """Export the analyzer's Gerber, drill, and IPC-D-356 input set."""
    run_kicad_cli(
        image,
        work,
        fixture_directory,
        output_directory,
        board,
        (
            "pcb",
            "export",
            "gerbers",
            "--layers",
            ",".join(copper_layers),
            "--no-protel-ext",
            "--check-zones",
            "--output",
            str(output_directory),
        ),
    )
    run_kicad_cli(
        image,
        work,
        fixture_directory,
        output_directory,
        board,
        (
            "pcb",
            "export",
            "drill",
            "--format",
            "excellon",
            "--excellon-separate-th",
            "--drill-origin",
            "absolute",
            "--excellon-units",
            "mm",
            "--output",
            str(output_directory),
        ),
    )
    run_kicad_cli(
        image,
        work,
        fixture_directory,
        output_directory,
        board,
        ("pcb", "export", "ipcd356", "--output", str(output_directory / "board.d356")),
    )


def remove_native_gerber_flash(text: str, x_mm: int, y_mm: int) -> str:
    """Remove exactly one KiCad-emitted D03 flash at the given board point."""
    command = f"X{x_mm * 1_000_000}Y{-y_mm * 1_000_000}D03*"
    if text.count(command) != 1:
        raise AssertionError(f"expected one native Gerber contact flash {command!r}")
    return text.replace(command, "", 1)
