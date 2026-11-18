"""Synthetic Gerber, Excellon, and IPC-D-356 inputs for analyzer tests."""

from __future__ import annotations

from pathlib import Path

_FIXTURES = Path(__file__).parent / "fixtures/fabrication-connectivity"
_PTH_DRILL_HEADER = "M48\n; #@! TF.FileFunction,Plated,1,2,PTH\nFMAT,2\nMETRIC\n%\n"


def format_ipc_contact(
    code: str,
    net: str,
    reference: str,
    pin: str,
    access: int,
    x_mm: float,
    size_x_mm: float = 1.0,
    size_y_mm: float = 0.0,
) -> str:
    x = round(x_mm / 0.00254)
    y = round(5.0 / 0.00254)
    size_x = round(size_x_mm / 0.00254)
    size_y = round(size_y_mm / 0.00254)
    return (
        f"{code}{net:<14}   {reference:<6} {pin:<4} "
        f"A{access:02d}X{x:+07d}Y{-y:+07d}X{size_x:04d}Y{size_y:04d}R000S2"
    )


def _gerber(side: str, features: str) -> str:
    level, label = ("L1", "Top") if side == "top" else ("L2", "Bot")
    return (
        f"%TF.FileFunction,Copper,{level},{label}*%\n"
        "%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\n"
        "%ADD10C,0.500000*%\n%ADD11C,0.300000*%\n%ADD14C,0.600000*%\n"
        "%ADD15C,1.000000*%\n"
        f"{features}M02*\n"
    )


def write_pth_drill_artifact(fabrication: Path, body: str) -> Path:
    """Write one minimal plated Excellon artifact with a caller-supplied body."""
    path = fabrication / "board-PTH.drl"
    path.write_text(_PTH_DRILL_HEADER + body + "M30\n", encoding="utf-8")
    return path


def write_synthetic_fabrication(
    directory: Path,
    *,
    connected: bool = True,
    second_net: str = "SIGNAL",
    through: bool = False,
    plated_drill: bool = True,
    inner_layer: bool = False,
) -> tuple[Path, Path]:
    """Write one minimal source board with matching synthetic export artifacts."""
    board = directory / "board.kicad_pcb"
    fixture = "via-only.kicad_pcb" if through else "clean.kicad_pcb"
    board.write_bytes((_FIXTURES / fixture).read_bytes())
    if not through and second_net != "SIGNAL":
        board.write_text(
            board.read_text(encoding="utf-8").replace(
                '(pad "2" smd circle (at 2 0) (size 1 1) (layers "F.Cu" "F.Mask") (net 1 "SIGNAL"))',
                f'(pad "2" smd circle (at 2 0) (size 1 1) (layers "F.Cu" "F.Mask") (net 2 "{second_net}"))',
            ),
            encoding="utf-8",
        )
    fabrication = directory / "fabrication"
    fabrication.mkdir()
    if through:
        top_features = "D14*X6000000Y-5000000D03*\n"
        bottom_features = "D14*X6000000Y-5000000D03*\n"
        contacts = (format_ipc_contact("317", "SIGNAL", "VIA", "", 0, 6.0, size_x_mm=0.6),)
    else:
        top_features = "D15*X5000000Y-5000000D03*X7000000Y-5000000D03*\n"
        top_features += "D10*X5000000Y-5000000D03*X7000000Y-5000000D03*\n" + (
            "D11*X5000000Y-5000000D02*X7000000Y-5000000D01*\n" if connected else ""
        )
        bottom_features = ""
        contacts = (
            format_ipc_contact("327", "SIGNAL", "J1", "1", 1, 5.0),
            format_ipc_contact("327", second_net, "J1", "2", 1, 7.0),
        )
    (fabrication / "board-F_Cu.gbr").write_text(_gerber("top", top_features), encoding="utf-8")
    (fabrication / "board-B_Cu.gbr").write_text(
        _gerber("bottom", bottom_features), encoding="utf-8"
    )
    (fabrication / "board.d356").write_text(
        "P  UNITS CUST 0\n" + "\n".join(contacts) + "\n999\n", encoding="utf-8"
    )
    if through and plated_drill:
        write_pth_drill_artifact(
            fabrication,
            "G90\nG05\nT1C0.3\nT1\nX6.0Y-5.0\n",
        )
    elif not through:
        write_pth_drill_artifact(fabrication, "")
    if inner_layer:
        (fabrication / "board-In1_Cu.gbr").write_text(
            "%TF.FileFunction,Copper,L2,Inr*%\nM02*\n", encoding="utf-8"
        )
    return board, fabrication
