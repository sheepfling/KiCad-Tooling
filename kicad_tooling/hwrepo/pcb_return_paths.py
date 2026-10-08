"""Deterministic checks over native KiCad PCB copper-connectivity evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

from .contract_coach import pinned_image, run_command
from .contracts import repo_path, write_model
from .evidence import digest
from .models import (
    CommandEvidence,
    ElectricalCheck,
    PcbAccessProbeRequestSet,
    PcbConnectivitySnapshot,
    PcbNetTieObservation,
    PcbPadConnectivityObservation,
    PcbReturnPathsAnalysis,
    PcbViaObservation,
    ProjectConfig,
)


def native_probe_source() -> Path:
    """Return the packaged script that runs only inside the exact KiCad image."""
    return Path(__file__).with_name("native_pcb_probe.py.in")


def _canonical_groups(groups: tuple[tuple[str, ...], ...]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        sorted(
            (tuple(sorted((pad.casefold() for pad in group))) for group in groups),
        )
    )


class _PadUnion:
    def __init__(self, pads: tuple[PcbPadConnectivityObservation, ...]) -> None:
        self.parent = {item.pad.casefold(): item.pad.casefold() for item in pads}
        for item in pads:
            for other in item.connected_pads:
                self.join(item.pad, other)

    def find(self, pad: str) -> str:
        key = pad.casefold()
        if key not in self.parent:
            return ""
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def join(self, first: str, second: str) -> None:
        a = first.casefold()
        b = second.casefold()
        if a not in self.parent or b not in self.parent:
            return
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a != root_b:
            self.parent[max(root_a, root_b)] = min(root_a, root_b)


def pcb_return_path_checks(
    spec: PcbReturnPathsAnalysis,
    snapshot: PcbConnectivitySnapshot,
    *,
    board_sha256: str,
    kicad_version: str,
    image: str,
    probe_sha256: str,
) -> tuple[ElectricalCheck, ...]:
    """Recompute endpoint, tie, domain and isolation findings from retained evidence."""
    checks: list[ElectricalCheck] = []
    try:
        expected_image = pinned_image(image)
        image_valid = snapshot.image == expected_image
    except ValueError:
        image_valid = False
    provenance = (
        ("board", snapshot.board_sha256 == board_sha256),
        (
            "KiCad version",
            snapshot.kicad_version == kicad_version and kicad_version.startswith("10."),
        ),
        ("digest-pinned image", image_valid),
        ("probe source", snapshot.probe_sha256 == probe_sha256),
        ("refilled zones", snapshot.zones_refilled),
    )
    for label, passed in provenance:
        checks.append(
            ElectricalCheck(
                id=f"pcb-return-paths/evidence/{label.replace(' ', '-')}",
                status="PASS" if passed else "FAIL",
                detail=(
                    f"Native PCB evidence matches the reviewed {label} input."
                    if passed
                    else f"Native PCB evidence does not establish the reviewed {label} input."
                ),
            )
        )

    pads = {item.pad.casefold(): item for item in snapshot.pads}
    ties = {item.reference.casefold(): item for item in snapshot.net_ties}
    zones = {(item.uuid.casefold(), item.layer.casefold()): item for item in snapshot.zones}
    vias = {item.id: item for item in snapshot.vias}
    active_ties = _PadUnion(snapshot.pads)
    for tie in snapshot.net_ties:
        if not tie.dnp:
            for group in tie.pad_groups:
                if group:
                    for pad in group[1:]:
                        active_ties.join(group[0], pad)

    valid_bonds: dict[str, bool] = {}
    domain_pads: list[tuple[str, tuple[str, ...]]] = []
    for domain in spec.domains:
        endpoint_pads: list[str] = []
        for endpoint in domain.endpoints:
            observed = pads.get(endpoint.pad.casefold())
            passed = (
                observed is not None
                and observed.net == endpoint.net
                and observed.footprint == endpoint.footprint
                and not observed.dnp
            )
            if observed is not None:
                endpoint_pads.append(observed.pad)
            checks.append(
                ElectricalCheck(
                    id=f"pcb-return-paths/{domain.id}/pad/{endpoint.pad}",
                    status="PASS" if passed else "FAIL",
                    detail=_endpoint_detail(
                        endpoint.pad, endpoint.net, endpoint.footprint, observed
                    ),
                )
            )

        for bond in domain.bonds:
            observed_tie = ties.get(bond.reference.casefold())
            expected_groups = _canonical_groups(bond.pad_groups)
            actual_groups = (
                _canonical_groups(observed_tie.pad_groups) if observed_tie is not None else ()
            )
            passed = (
                observed_tie is not None
                and observed_tie.footprint == bond.footprint
                and not observed_tie.dnp
                and actual_groups == expected_groups
            )
            valid_bonds[bond.reference.casefold()] = passed
            checks.append(
                ElectricalCheck(
                    id=f"pcb-return-paths/{domain.id}/bond/{bond.reference}",
                    status="PASS" if passed else "FAIL",
                    detail=_bond_detail(
                        bond.reference,
                        bond.footprint,
                        expected_groups,
                        observed_tie,
                    ),
                )
            )

        local = _PadUnion(snapshot.pads)
        bonds_valid = True
        for bond in domain.bonds:
            if not valid_bonds.get(bond.reference.casefold(), False):
                bonds_valid = False
                continue
            actual_tie = ties[bond.reference.casefold()]
            for group in actual_tie.pad_groups:
                if group:
                    for pad in group[1:]:
                        local.join(group[0], pad)
        complete = len(endpoint_pads) == len(domain.endpoints) and bonds_valid
        connected = complete and len({local.find(pad) for pad in endpoint_pads}) == 1
        domain_pads.append((domain.id, tuple(endpoint_pads)))
        components: dict[str, list[str]] = {}
        for endpoint_pad in endpoint_pads:
            components.setdefault(local.find(endpoint_pad), []).append(endpoint_pad)
        observed_groups: list[str] = []
        zone_details: list[str] = []
        via_details: list[str] = []
        for component, endpoints in sorted(components.items()):
            copper_pads = sorted(
                (item.pad for item in snapshot.pads if local.find(item.pad) == component),
                key=str.casefold,
            )
            observed_groups.append(
                f"{', '.join(sorted(endpoints, key=str.casefold))} in copper group "
                f"[{', '.join(copper_pads)}]"
            )
            component_via_ids = sorted(
                {
                    via_id
                    for item in snapshot.pads
                    if local.find(item.pad) == component
                    for via_id in item.connected_vias
                }
            )
            component_vias = [vias[via_id] for via_id in component_via_ids]
            via_details.append(
                f"{', '.join(sorted(endpoints, key=str.casefold))}: "
                + (
                    ", ".join(_via_detail(via) for via in component_vias)
                    if component_vias
                    else "no component vias observed"
                )
            )
            for endpoint_pad in sorted(endpoints, key=str.casefold):
                observed = pads.get(endpoint_pad.casefold())
                if observed is None:
                    continue
                descriptions: list[str] = []
                for identity in observed.connected_zones:
                    zone = zones[(identity.uuid.casefold(), identity.layer.casefold())]
                    island_indices = sorted(
                        island.island_index
                        for island in observed.connected_islands
                        if island.uuid.casefold() == identity.uuid.casefold()
                        and island.layer.casefold() == identity.layer.casefold()
                    )
                    zone_name = zone.name or "unnamed"
                    descriptions.append(
                        f"{zone.layer} zone {zone.uuid} ({zone_name}; net={zone.net!r}; "
                        f"filled islands={zone.filled_island_count}; "
                        f"connected island indexes={island_indices}; "
                        "unanchored to pad indexes="
                        f"{list(zone.unanchored_pad_island_indexes)})"
                    )
                zone_details.append(
                    f"{endpoint_pad}: {', '.join(descriptions) if descriptions else 'no connected copper zone'}"
                )
        zone_evidence = "; ".join(zone_details) or "no endpoint zone observations"
        via_evidence = "; ".join(via_details) or "no endpoint via observations"
        checks.append(
            ElectricalCheck(
                id=f"pcb-return-paths/{domain.id}/connectivity",
                status="PASS" if connected else "FAIL",
                detail=(
                    f"All reviewed return pads share the declared {domain.topology} copper path: "
                    f"{'; '.join(observed_groups)}. Zone observations: {zone_evidence}. "
                    "Native component-via membership (no serial route inferred): "
                    f"{via_evidence}."
                    if connected
                    else (
                        "The exact return pads are not all connected through the declared copper "
                        "and fitted net-tie groups. Observed: "
                        f"{' ; '.join(observed_groups) or 'no complete pad set'}. "
                        f"Zone observations: {zone_evidence}. "
                        "Native component-via membership (no serial route inferred): "
                        f"{via_evidence}."
                    )
                ),
            )
        )

    for left_index, (left_id, left_pads) in enumerate(domain_pads):
        for right_id, right_pads in domain_pads[left_index + 1 :]:
            shared_pair = next(
                (
                    (left, right)
                    for left in left_pads
                    for right in right_pads
                    if active_ties.find(left)
                    and active_ties.find(right)
                    and active_ties.find(left) == active_ties.find(right)
                ),
                None,
            )
            checks.append(
                ElectricalCheck(
                    id=f"pcb-return-paths/isolation/{left_id}/{right_id}",
                    status="FAIL" if shared_pair is not None else "PASS",
                    detail=(
                        f"Separately declared return domains share a physical copper or fitted net-tie path: "
                        f"{shared_pair[0]} and {shared_pair[1]} are connected."
                        if shared_pair is not None
                        else "Separately declared return domains remain physically disconnected in the board evidence."
                    ),
                )
            )
    return tuple(checks)


def _via_detail(via: PcbViaObservation) -> str:
    """Format one stable via observation without implying route order or capacity."""
    x_mm = via.x_nm / 1_000_000
    y_mm = via.y_nm / 1_000_000
    diameter_mm = via.diameter_nm / 1_000_000
    drill_mm = via.drill_nm / 1_000_000
    return (
        f"via {via.id} ({via.kind}, net={via.net!r}, center=({x_mm:g}, {y_mm:g}) mm, "
        f"{via.start_layer} to {via.end_layer}, diameter={diameter_mm:g} mm, "
        f"drill={drill_mm:g} mm, identical-geometry count={via.multiplicity})"
    )


def _endpoint_detail(
    pad: str,
    expected_net: str,
    expected_footprint: str,
    observed: PcbPadConnectivityObservation | None,
) -> str:
    if observed is None:
        return f"{pad} is absent from the native PCB pad inventory."
    if (
        observed.net == expected_net
        and observed.footprint == expected_footprint
        and not observed.dnp
    ):
        return f"{pad} has the reviewed net and footprint and is fitted."
    return (
        f"{pad} observed net={observed.net!r}, footprint={observed.footprint!r}, "
        f"DNP={observed.dnp}; expected net={expected_net!r}, "
        f"footprint={expected_footprint!r}, fitted."
    )


def _bond_detail(
    reference: str,
    expected_footprint: str,
    expected_groups: tuple[tuple[str, ...], ...],
    observed: PcbNetTieObservation | None,
) -> str:
    if observed is None:
        return f"{reference} is absent from the native net-tie inventory."
    actual_groups = _canonical_groups(observed.pad_groups)
    if (
        observed.footprint == expected_footprint
        and not observed.dnp
        and actual_groups == expected_groups
    ):
        return f"{reference} matches the reviewed fitted net-tie footprint and pad groups."
    return (
        f"{reference} observed footprint={observed.footprint!r}, DNP={observed.dnp}, "
        f"groups={actual_groups}; expected footprint={expected_footprint!r}, "
        f"fitted, groups={expected_groups}."
    )


def capture_native_pcb_connectivity(
    root: Path,
    config: ProjectConfig,
    output: Path,
    access_probe_requests: PcbAccessProbeRequestSet | None = None,
) -> tuple[CommandEvidence, PcbConnectivitySnapshot | None]:
    """Run the read-only KiCad 10 pcbnew probe in the project's digest-pinned image."""
    if not config.kicad_version.startswith("10."):
        raise ValueError("PCB return-path evidence currently supports the KiCad 10 Python API only")
    image = pinned_image(config.image)
    root = root.resolve()
    board = repo_path(root, config.project).with_suffix(".kicad_pcb")
    output = output.resolve()
    if not board.is_file():
        raise ValueError(f"PCB return-path analysis requires the authoritative board: {board}")
    if not output.is_relative_to(root):
        raise ValueError("PCB connectivity receipts must remain inside the project checkout")
    relative_board = board.relative_to(root).as_posix()
    source_hash = digest(board)
    output.mkdir(parents=True, exist_ok=False)
    probe = native_probe_source()
    probe_copy = output / "native_pcb_probe.py"
    shutil.copyfile(probe, probe_copy)
    probe_hash = digest(probe_copy)
    snapshot_path = output / "snapshot.json"
    request_path: Path | None = None
    request_hash: str | None = None
    if access_probe_requests is not None:
        request_path = output / "access-probe-requests.json"
        write_model(request_path, access_probe_requests)
        request_hash = digest(request_path)
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        import os

        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    argv = (
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        *user,
        "-e",
        "HOME=/tmp",
        "-v",
        f"{root}:/work:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/work",
        "--entrypoint",
        "/usr/bin/python3",
        image,
        "-I",
        "-B",
        "/output/native_pcb_probe.py",
        f"/work/{relative_board}",
        "/output/snapshot.json",
        *(("/output/access-probe-requests.json",) if request_path is not None else ()),
    )
    command = run_command(root, argv, timeout=600)
    write_model(output / "native.command.json", command)
    if command.returncode != 0 or command.error is not None or not snapshot_path.is_file():
        return command, None
    if digest(board) != source_hash:
        raise ValueError("PCB source changed while native connectivity evidence was captured")
    if request_path is not None and digest(request_path) != request_hash:
        raise ValueError("Native PCB probe request changed while evidence was captured")
    raw = snapshot_path.read_text(encoding="utf-8")
    observed = json.loads(raw)
    if observed.get("board_sha256") != source_hash:
        raise ValueError("Native PCB connectivity evidence is bound to a different board source")
    observed["image"] = image
    observed["probe_sha256"] = probe_hash
    if observed.get("access_probe_requests_sha256") != request_hash:
        raise ValueError("Native PCB probe evidence is bound to different access requests")
    snapshot = PcbConnectivitySnapshot.model_validate_json(
        json.dumps(observed, ensure_ascii=False, sort_keys=True), strict=True
    )
    return command, snapshot


def expected_probe_sha256() -> str:
    return hashlib.sha256(native_probe_source().read_bytes()).hexdigest()


def native_pcb_command_matches(
    command: CommandEvidence,
    config: ProjectConfig,
    *,
    access_probes: bool = False,
) -> bool:
    """Reject retained snapshots detached from the read-only pinned probe invocation."""
    try:
        image = pinned_image(config.image)
    except ValueError:
        return False
    argv = command.argv
    if not argv or argv[0] != "docker" or command.returncode != 0 or command.error:
        return False
    if not all(
        item in argv
        for item in (
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "--entrypoint",
            "/usr/bin/python3",
            image,
            "-I",
            "-B",
            "/output/native_pcb_probe.py",
            "/output/snapshot.json",
        )
    ):
        return False
    try:
        if argv[argv.index("--network") + 1] != "none":
            return False
        if argv[argv.index("--entrypoint") + 1] != "/usr/bin/python3":
            return False
    except (IndexError, ValueError):
        return False
    board_argument = "/work/" + Path(config.project).with_suffix(".kicad_pcb").as_posix()
    expected_tail = (
        (board_argument, "/output/snapshot.json", "/output/access-probe-requests.json")
        if access_probes
        else (board_argument, "/output/snapshot.json")
    )
    if argv[-len(expected_tail) :] != expected_tail:
        return False
    mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
    return (
        len(mounts) == 2
        and sum(mount.endswith(":/work:ro") for mount in mounts) == 1
        and sum(mount.endswith(":/output:rw") for mount in mounts) == 1
    )
