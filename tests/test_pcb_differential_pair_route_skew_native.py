"""Digest-pinned native PCB geometry controls for mapped pair route skew."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from kicad_tooling.hwrepo.design_lint_pcb_requirement_candidates import (
    pcb_requirement_coverage_candidates,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.pcb_connectivity_snapshot import PcbConnectivitySnapshot
from kicad_tooling.hwrepo.pcb_differential_pair_route_skew import (
    measure_differential_pair_route_skew,
)
from kicad_tooling.hwrepo.pcb_differential_pair_skew_models import (
    PcbDifferentialPairRouteSkewReport,
)
from kicad_tooling.hwrepo.pcb_drc_models import PcbSignalPathRuleCoverageReport
from kicad_tooling.hwrepo.pcb_return_path_capture import (
    expected_probe_sha256,
    native_probe_source,
)
from tests.design_lint_fixtures.pcb_differential_pair_route_skew import (
    route_map,
    source_netlist,
)
from tests.synthetic_design_lint_project import PINNED_NATIVE_KICAD_IMAGES

SOURCE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = SOURCE_ROOT / "tests/fixtures/design_lint/differential-pair-route-skew-native"
RULE_ID = "pcb.differential_pair_route_skew"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="native PCB fixtures run in the digest-pinned package acceptance lane",
    ),
]


def _container_python(
    image: str,
    work: Path,
    arguments: tuple[str, ...],
) -> CommandEvidence:
    user = () if os.name == "nt" else ("--user", f"{os.getuid()}:{os.getgid()}")
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
        "HOME=/tmp/kicad-pair-route-skew",
        "-v",
        f"{FIXTURE_ROOT.resolve()}:/fixtures:ro",
        "-v",
        f"{work.resolve()}:/work:rw",
        "--entrypoint",
        "/usr/bin/python3",
        image,
        "-I",
        "-B",
        *arguments,
    )
    started_utc = datetime.now(UTC).isoformat()
    try:
        result = subprocess.run(
            argv,
            cwd=work,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandEvidence(
            argv=_portable_argv(argv),
            started_utc=started_utc,
            returncode=127,
            error=str(exc),
        )
    return CommandEvidence(
        argv=_portable_argv(argv),
        started_utc=started_utc,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _portable_argv(argv: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        item.replace(str(FIXTURE_ROOT.resolve()), "<fixture-root>").replace(
            str(
                SOURCE_ROOT.resolve() / "build/ci/native-fixtures/pcb-differential-pair-route-skew"
            ),
            "<output-root>",
        )
        for item in argv
    )


def _prepare_output(version: str) -> Path:
    output = SOURCE_ROOT / "build/ci/native-fixtures/pcb-differential-pair-route-skew" / version
    if output.is_symlink():
        raise ValueError("Native pair route-skew output cannot be a symlink")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    return output


@pytest.mark.parametrize(("version", "image"), tuple(PINNED_NATIVE_KICAD_IMAGES.items()))
def test_native_pair_route_skew_fault_and_control_use_exact_board_snapshots(
    version: str,
    image: str,
) -> None:
    work = _prepare_output(version)
    (work / "native_pcb_probe.py").write_text(native_probe_source(), encoding="utf-8")

    generated = _container_python(
        image,
        work,
        ("/fixtures/create.py", "/work/boards", version),
    )
    assert generated.error is None, generated.model_dump_json(indent=2)
    assert generated.returncode == 0, generated.model_dump_json(indent=2)
    assert (work / "boards/kicad-version.txt").read_text(encoding="utf-8").strip() == version
    write_model(work / "generator.command.json", generated)

    source = source_netlist()
    netlist_sha256 = hashlib.sha256(source.model_dump_json().encode("utf-8")).hexdigest()
    probe_sha256 = expected_probe_sha256()
    reports: dict[str, PcbDifferentialPairRouteSkewReport] = {}
    for case in ("control", "fault"):
        board = work / f"boards/{case}.kicad_pcb"
        raw_snapshot_path = work / f"boards/{case}.native.json"
        command = _container_python(
            image,
            work,
            (
                "/work/native_pcb_probe.py",
                f"/work/boards/{case}.kicad_pcb",
                f"/work/boards/{case}.native.json",
            ),
        )
        assert command.error is None, command.model_dump_json(indent=2)
        assert command.returncode == 0, command.model_dump_json(indent=2)
        write_model(work / f"boards/{case}.command.json", command)

        observed = json.loads(raw_snapshot_path.read_text(encoding="utf-8"))
        board_sha256 = digest(board)
        assert observed["board_sha256"] == board_sha256
        assert observed["kicad_version"] == version
        observed["image"] = image
        observed["probe_sha256"] = probe_sha256
        snapshot = PcbConnectivitySnapshot.model_validate_json(
            json.dumps(observed, ensure_ascii=False, sort_keys=True), strict=True
        )
        snapshot_path = work / f"boards/{case}.snapshot.json"
        snapshot_path.write_text(
            json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        relative_board = board.relative_to(SOURCE_ROOT).as_posix()
        command_path = work / f"boards/{case}.command.json"
        evidence = PcbGeometrySourceEvidence(
            board_path=relative_board,
            board_sha256=board_sha256,
            snapshot_relative_path=snapshot_path.relative_to(SOURCE_ROOT).as_posix(),
            snapshot_path=snapshot_path,
            snapshot_sha256=digest(snapshot_path),
            probe_sha256=probe_sha256,
            snapshot=snapshot,
            command=command,
            command_path=command_path,
            command_sha256=digest(command_path),
        )
        coverage = measure_differential_pair_route_skew(
            route_map(maximum_skew_nm=500_000),
            source,
            evidence,
            {relative_board: board_sha256},
            netlist_sha256,
            "review",
        )
        repeated = measure_differential_pair_route_skew(
            route_map(maximum_skew_nm=500_000),
            source,
            evidence,
            {relative_board: board_sha256},
            netlist_sha256,
            "review",
        )
        assert repeated == coverage
        write_model(work / f"boards/{case}.route-skew.json", coverage)
        reports[case] = coverage

    control = reports["control"]
    assert control.status == "COMPLETE"
    control_paths = {item.path_id: item.length_nm for item in control.entries[0].paths}
    assert control_paths == {"positive-path": 30_000_000, "negative-path": 30_000_000}
    assert not pcb_requirement_coverage_candidates(
        pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(route_skew=control)
    )

    fault = reports["fault"]
    assert fault.status == "INCOMPLETE"
    fault_entry = fault.entries[0]
    assert fault_entry.status == "EXCEEDS_LIMIT"
    assert fault_entry.measured_skew_nm == 20_000_000
    fault_paths = {item.path_id: item.length_nm for item in fault_entry.paths}
    assert fault_paths == {"positive-path": 30_000_000, "negative-path": 50_000_000}
    findings = pcb_requirement_coverage_candidates(
        pcb_signal_path_coverage=PcbSignalPathRuleCoverageReport(route_skew=fault)
    )
    assert len(findings) == 1
    assert findings[0].rule_id == RULE_ID
    assert findings[0].evidence["maximum_skew_nm"] == ("500000",)

    manifest: dict[str, str | int | None] = {
        "kicad_version": version,
        "image": image,
        "generator_command_sha256": digest(work / "generator.command.json"),
        "native_probe_sha256": probe_sha256,
        "control_board_sha256": digest(work / "boards/control.kicad_pcb"),
        "control_snapshot_sha256": digest(work / "boards/control.snapshot.json"),
        "control_command_sha256": digest(work / "boards/control.command.json"),
        "control_route_skew_sha256": digest(work / "boards/control.route-skew.json"),
        "fault_board_sha256": digest(work / "boards/fault.kicad_pcb"),
        "fault_snapshot_sha256": digest(work / "boards/fault.snapshot.json"),
        "fault_command_sha256": digest(work / "boards/fault.command.json"),
        "fault_route_skew_sha256": digest(work / "boards/fault.route-skew.json"),
        "measured_skew_nm": fault_entry.measured_skew_nm,
        "maximum_skew_nm": fault_entry.max_skew_nm,
    }
    (work / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
