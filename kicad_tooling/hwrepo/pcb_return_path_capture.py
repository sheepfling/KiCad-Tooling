"""Capture source-bound native PCB connectivity evidence."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from .contract_coach import pinned_image, run_command
from .contracts import repo_path, write_model
from .evidence import digest
from .models import CommandEvidence, PcbAccessProbeRequestSet, ProjectConfig
from .native_container_context import (
    NATIVE_CONTAINER_IMAGE_ENV,
    native_container_image_marker,
)
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceRequestSet

NATIVE_PROBE_SOURCE_PARTS = (
    "native_pcb_probe.py.in",
    "native_pcb_probe_access.py.in",
    "native_pcb_probe_geometry.py.in",
    "native_pcb_probe_touch_clearance.py.in",
    "native_pcb_probe_scan.py.in",
)


def native_probe_source() -> str:
    """Assemble the standalone script used inside the exact KiCad image."""
    source_directory = Path(__file__).parent
    return (
        "\n\n".join(
            (source_directory / name).read_text(encoding="utf-8").rstrip()
            for name in NATIVE_PROBE_SOURCE_PARTS
        )
        + "\n"
    )


def capture_native_pcb_connectivity(
    root: Path,
    config: ProjectConfig,
    output: Path,
    access_probe_requests: PcbAccessProbeRequestSet | None = None,
    touch_pad_clearance_requests: PcbTouchPadClearanceRequestSet | None = None,
) -> tuple[CommandEvidence, PcbConnectivitySnapshot | None]:
    """Run the read-only KiCad 10 pcbnew probe in the project's digest-pinned image."""
    if not config.kicad_version.startswith("10."):
        raise ValueError("PCB return-path evidence currently supports the KiCad 10 Python API only")
    image = pinned_image(config.image)
    in_container_image = native_container_image_marker()
    if in_container_image is not None and in_container_image != image:
        raise ValueError("Native container image marker differs from the project's pinned image")
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
    probe_copy.write_bytes(probe.encode("utf-8"))
    probe_hash = digest(probe_copy)
    snapshot_path = output / "snapshot.json"
    request_path: Path | None = None
    request_hash: str | None = None
    if access_probe_requests is not None:
        request_path = output / "access-probe-requests.json"
        write_model(request_path, access_probe_requests)
        request_hash = digest(request_path)
    touch_request_path: Path | None = None
    touch_request_hash: str | None = None
    if touch_pad_clearance_requests is not None:
        touch_request_path = output / "touch-pad-clearance-requests.json"
        write_model(touch_request_path, touch_pad_clearance_requests)
        touch_request_hash = digest(touch_request_path)
    if in_container_image is not None:

        def work_path(path: Path) -> str:
            return f"/work/{path.relative_to(root).as_posix()}"

        if touch_request_path is not None:
            probe_arguments = (
                work_path(request_path) if request_path is not None else "-",
                work_path(touch_request_path),
            )
        elif request_path is not None:
            probe_arguments = (work_path(request_path),)
        else:
            probe_arguments = ()
        argv = (
            "/usr/bin/env",
            f"{NATIVE_CONTAINER_IMAGE_ENV}={image}",
            "/usr/bin/python3",
            "-I",
            "-B",
            work_path(probe_copy),
            f"/work/{relative_board}",
            work_path(snapshot_path),
            *probe_arguments,
        )
    else:
        if touch_request_path is not None:
            probe_arguments = (
                "/output/access-probe-requests.json" if request_path is not None else "-",
                "/output/touch-pad-clearance-requests.json",
            )
        elif request_path is not None:
            probe_arguments = ("/output/access-probe-requests.json",)
        else:
            probe_arguments = ()
        user: tuple[str, ...] = ()
        if sys.platform != "win32":
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
            *probe_arguments,
        )
    command = run_command(root, argv, timeout=600)
    write_model(output / "native.command.json", command)
    if command.returncode != 0 or command.error is not None or not snapshot_path.is_file():
        return command, None
    if digest(board) != source_hash:
        raise ValueError("PCB source changed while native connectivity evidence was captured")
    if request_path is not None and digest(request_path) != request_hash:
        raise ValueError("Native PCB probe request changed while evidence was captured")
    if touch_request_path is not None and digest(touch_request_path) != touch_request_hash:
        raise ValueError("Native touch-pad probe request changed while evidence was captured")
    raw = snapshot_path.read_text(encoding="utf-8")
    observed = json.loads(raw)
    if observed.get("board_sha256") != source_hash:
        raise ValueError("Native PCB connectivity evidence is bound to a different board source")
    observed["image"] = image
    observed["probe_sha256"] = probe_hash
    if observed.get("access_probe_requests_sha256") != request_hash:
        raise ValueError("Native PCB probe evidence is bound to different access requests")
    if observed.get("touch_pad_clearance_requests_sha256") != touch_request_hash:
        raise ValueError("Native PCB probe evidence is bound to different touch-pad requests")
    snapshot = PcbConnectivitySnapshot.model_validate_json(
        json.dumps(observed, ensure_ascii=False, sort_keys=True), strict=True
    )
    return command, snapshot


def expected_probe_sha256() -> str:
    return hashlib.sha256(native_probe_source().encode("utf-8")).hexdigest()


def native_pcb_command_matches(
    command: CommandEvidence,
    config: ProjectConfig,
    *,
    access_probes: bool = False,
    touch_pad_clearance_probes: bool = False,
) -> bool:
    """Reject retained snapshots detached from the read-only pinned probe invocation."""
    try:
        image = pinned_image(config.image)
    except ValueError:
        return False
    argv = command.argv
    if not argv or command.returncode != 0 or command.error:
        return False
    if argv[0] == "/usr/bin/env":
        prefix = (
            "/usr/bin/env",
            f"{NATIVE_CONTAINER_IMAGE_ENV}={image}",
            "/usr/bin/python3",
            "-I",
            "-B",
        )
        if argv[:5] != prefix or len(argv) < 8:
            return False
        probe_path = Path(argv[5])
        snapshot_path = Path(argv[7])
        if (
            probe_path.name != "native_pcb_probe.py"
            or snapshot_path.name != "snapshot.json"
            or probe_path.parent != snapshot_path.parent
            or not probe_path.parent.is_relative_to(Path("/work/build/design-lint"))
        ):
            return False
        board_argument = "/work/" + Path(config.project).with_suffix(".kicad_pcb").as_posix()
        expected_tail = [board_argument, str(snapshot_path)]
        if touch_pad_clearance_probes:
            expected_tail.extend(
                (
                    str(probe_path.parent / "access-probe-requests.json") if access_probes else "-",
                    str(probe_path.parent / "touch-pad-clearance-requests.json"),
                )
            )
        elif access_probes:
            expected_tail.append(str(probe_path.parent / "access-probe-requests.json"))
        return len(argv) == 6 + len(expected_tail) and list(argv[6:]) == expected_tail
    if argv[0] != "docker":
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
    if touch_pad_clearance_probes:
        expected_tail = (
            board_argument,
            "/output/snapshot.json",
            "/output/access-probe-requests.json" if access_probes else "-",
            "/output/touch-pad-clearance-requests.json",
        )
    elif access_probes:
        expected_tail = (
            board_argument,
            "/output/snapshot.json",
            "/output/access-probe-requests.json",
        )
    else:
        expected_tail = (board_argument, "/output/snapshot.json")
    if argv[-len(expected_tail) :] != expected_tail:
        return False
    mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
    return (
        len(mounts) == 2
        and sum(mount.endswith(":/work:ro") for mount in mounts) == 1
        and sum(mount.endswith(":/output:rw") for mount in mounts) == 1
    )
