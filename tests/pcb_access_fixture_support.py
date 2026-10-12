"""Build source-bound mock evidence from the synthetic PCB access fixture."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    PcbAccessProbeRequestSet,
    PcbConnectivitySnapshot,
    ProjectConfig,
)
from kicad_tooling.hwrepo.pcb_return_path_capture import expected_probe_sha256

_SNAPSHOT_FIXTURE = Path(__file__).parent / "fixtures/pcb-access-probe/snapshot.json"


def capture_synthetic_access_probe(
    root: Path,
    selected: ProjectConfig,
    output: Path,
    requests: PcbAccessProbeRequestSet,
) -> tuple[CommandEvidence, PcbConnectivitySnapshot, Path]:
    """Bind the typed fixture to a temporary project and exact probe requests."""
    board = root / Path(selected.project).with_suffix(".kicad_pcb")
    if not board.is_file():
        raise FileNotFoundError(board)
    output.mkdir()
    request_path = output / "access-probe-requests.json"
    write_model(request_path, requests)
    snapshot = PcbConnectivitySnapshot.model_validate_json(
        _SNAPSHOT_FIXTURE.read_text(encoding="utf-8")
    ).model_copy(
        update={
            "board_sha256": digest(board),
            "kicad_version": selected.kicad_version,
            "image": selected.image,
            "probe_sha256": expected_probe_sha256(),
            "access_probe_requests_sha256": digest(request_path),
        }
    )
    board_argument = "/work/" + Path(selected.project).with_suffix(".kicad_pcb").as_posix()
    command = CommandEvidence(
        argv=(
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
            "-v",
            f"{root}:/work:ro",
            "-v",
            f"{output}:/output:rw",
            "-w",
            "/work",
            "--entrypoint",
            "/usr/bin/python3",
            selected.image,
            "-I",
            "-B",
            "/output/native_pcb_probe.py",
            board_argument,
            "/output/snapshot.json",
            "/output/access-probe-requests.json",
        ),
        started_utc="2026-01-01T00:00:00Z",
        returncode=0,
    )
    return command, snapshot, board
