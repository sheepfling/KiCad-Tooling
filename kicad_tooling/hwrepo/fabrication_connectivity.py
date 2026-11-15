"""Source-bound analysis of exported copper connectivity and IPC-D-356 contacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .fabrication_artwork import (
    Contact,
    DrillHit,
    UnsupportedFabricationFormat,
    classify_copper_files,
    drill_file_is_plated,
    parse_excellon,
    parse_gerber,
    parse_ipc356,
)
from .fabrication_connectivity_models import (
    FabricationConnectivityFinding,
    FabricationConnectivitySettings,
    FabricationConnectivitySummary,
)
from .kicad_sexpr import sexpr_atoms, sexpr_children, sexpr_nodes, sexpr_root
from .pcb_board_net_inventory import pcb_board_net_names


def _require_supported_board(board_text: str, contacts: tuple[Contact, ...]) -> None:
    root = sexpr_root(board_text, "kicad_pcb")
    layers = sexpr_nodes(board_text, root, "layers")
    if len(layers) != 1:
        raise UnsupportedFabricationFormat("board source has no unique copper-layer stack")
    copper_layers = tuple(
        atoms[1]
        for child in sexpr_children(board_text, layers[0].start + 1, layers[0].end - 1)
        if len(atoms := sexpr_atoms(board_text, child)) >= 3
        and atoms[2] == "signal"
        and atoms[1].casefold().endswith(".cu")
    )
    if copper_layers != ("F.Cu", "B.Cu"):
        raise UnsupportedFabricationFormat(
            "connectivity v1 requires a source board with only F.Cu and B.Cu"
        )
    net_names = pcb_board_net_names(board_text)
    if net_names is None:
        raise UnsupportedFabricationFormat("board source has an incomplete named-net inventory")
    if any(len(name) > 14 for name in net_names):
        raise UnsupportedFabricationFormat("IPC-D-356 net-name width is too short for board nets")
    declared = set(net_names)
    if any(
        contact.net not in declared and not contact.net.startswith("N/C:") for contact in contacts
    ):
        raise UnsupportedFabricationFormat("IPC-D-356 net names do not match the board source")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fingerprint(code: str, net: str | None, contacts: tuple[str, ...]) -> str:
    payload = json.dumps(
        {"code": code, "net": net, "contacts": sorted(contacts)},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _finding(
    code: str,
    contact_labels: tuple[str, ...],
    net: str | None = None,
    location: tuple[float, float] | None = None,
) -> FabricationConnectivityFinding:
    contacts = tuple(sorted(contact_labels))
    return FabricationConnectivityFinding(
        code=code,  # type: ignore[arg-type]
        fingerprint=_fingerprint(code, net, contacts),
        net=net,
        contacts=contacts,
        location_mm=location,
    )


def _source_inputs(fabrication_dir: Path) -> tuple[tuple[Path, ...], Path, tuple[Path, ...]]:
    gerbers = tuple(sorted(fabrication_dir.glob("*.gbr")))
    drill_files = tuple(sorted(fabrication_dir.glob("*.drl")))
    ipc = fabrication_dir / "board.d356"
    if not gerbers:
        raise UnsupportedFabricationFormat("no exported Gerber copper files found")
    if not ipc.is_file():
        raise UnsupportedFabricationFormat("the configured IPC-D-356 artifact is missing")
    return gerbers, ipc, drill_files


def analyze_fabrication_connectivity(
    board_path: Path,
    fabrication_dir: Path,
    settings: FabricationConnectivitySettings,
) -> FabricationConnectivitySummary:
    """Compare supported exported copper with IPC-D-356 without inferring intent."""
    board_bytes = board_path.read_bytes()
    board_hash = _digest(board_bytes)
    reasons: list[str] = []
    findings: list[FabricationConnectivityFinding] = []
    try:
        board_text = board_bytes.decode("utf-8")
        gerber_paths, ipc_path, drill_paths = _source_inputs(fabrication_dir)
        copper_paths = classify_copper_files(gerber_paths)
        layers = tuple(parse_gerber(path, side) for path, side in copper_paths)
        contacts = parse_ipc356(ipc_path.read_text(encoding="utf-8", errors="replace"))
        _require_supported_board(board_text, contacts)
        plated: list[DrillHit] = []
        for path in drill_paths:
            if drill_file_is_plated(path):
                plated.extend(parse_excellon(path.read_text(encoding="utf-8", errors="replace")))
        try:
            from .fabrication_connectivity_raster import analyze_raster
        except ImportError as exc:
            raise UnsupportedFabricationFormat(
                "install the optional fabrication-connectivity dependencies to enable analysis"
            ) from exc
        raster = analyze_raster(
            layers,
            contacts,
            tuple(plated),
            settings.pixel_density,
        )
        for net, endpoints in raster.opens:
            findings.append(_finding("OPEN", endpoints, net))
        for endpoints in raster.shorts:
            findings.append(_finding("SHORT", endpoints))
        for contact in raster.no_copper:
            findings.append(
                _finding(
                    "NO_COPPER",
                    (contact.label,),
                    contact.net,
                    (contact.x_mm, contact.y_mm),
                )
            )
        for contact in raster.no_drill:
            findings.append(
                _finding(
                    "NO_DRILL",
                    (contact.label,),
                    contact.net,
                    (contact.x_mm, contact.y_mm),
                )
            )
    except (OSError, UnicodeError, UnsupportedFabricationFormat, ValueError) as exc:
        reasons.append(str(exc))

    try:
        gerber_paths, ipc_path, drill_paths = _source_inputs(fabrication_dir)
        inputs = (*gerber_paths, *drill_paths, ipc_path)
    except (OSError, UnsupportedFabricationFormat):
        inputs = ()
    artifact_hashes = {
        (Path("fabrication") / path.name).as_posix(): _digest(path.read_bytes())
        for path in inputs
        if path.is_file()
    }

    fingerprinted = {finding.fingerprint: finding for finding in findings}
    ignore_map = {item.fingerprint: item for item in settings.ignores}
    ignored = tuple(fingerprinted[key] for key in sorted(fingerprinted.keys() & ignore_map.keys()))
    active = tuple(fingerprinted[key] for key in sorted(fingerprinted.keys() - ignore_map.keys()))
    stale = tuple(sorted(ignore_map.keys() - fingerprinted.keys()))
    if reasons:
        status = "UNSUPPORTED"
    elif stale or (active and settings.mode == "block"):
        status = "FAIL"
    elif active:
        status = "REVIEW"
    else:
        status = "PASS"
    return FabricationConnectivitySummary(
        status=status,
        board_sha256=board_hash,
        artifact_sha256=artifact_hashes,
        pixel_density=settings.pixel_density,
        findings=active,
        ignored_findings=ignored,
        stale_ignore_fingerprints=stale,
        unsupported_reasons=tuple(reasons),
    )
