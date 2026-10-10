"""Hosted native serial peer reference-bond fixture lane."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def serial_peer_reference_bond_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify an authored serial reference bond against repeated pinned exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.contracts import read_model
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ElectricalCheck, SerialPeerAnalysis
    from .hwrepo.serial_heuristics import serial_peer_checks
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Serial reference-bond fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)

    repository = Path(__file__).resolve().parents[1]
    fixture_root = repository / "tests/fixtures/design_lint/serial-peer-reference-bond-native"
    fixtures = {
        "control": fixture_root / "serial-reference-bond-control.kicad_sch",
        "fault": fixture_root / "serial-reference-bond-fault.kicad_sch",
    }
    fixture_hashes = {case: digest(path) for case, path in fixtures.items()}
    map_fixture = fixture_root / "serial-peer-map.json"
    map_hash = digest(map_fixture)
    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"serial-peer-reference-bond-{project}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    input_fixtures = {case: inputs / path.name for case, path in fixtures.items()}
    for case, path in fixtures.items():
        shutil.copyfile(path, input_fixtures[case])
        if digest(input_fixtures[case]) != fixture_hashes[case]:
            raise ValueError(
                f"Synthetic serial reference-bond {case} fixture changed while copying"
            )
    map_input = inputs / map_fixture.name
    shutil.copyfile(map_fixture, map_input)
    if digest(map_input) != map_hash:
        raise ValueError("Synthetic serial reference-bond map changed while copying")

    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{config.kicad_version}"\n'
        "for case in control fault; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
        '      "/fixtures/serial-reference-bond-${case}.kicad_sch"\n'
        "  done\n"
        "done\n"
    )
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
        "HOME=/tmp/kicad-serial-peer-reference-bond-fixtures",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned,
        "-ec",
        script,
    )
    log.event(
        "serial-peer-reference-bond-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "serial-peer-reference-bond-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            "Native serial reference-bond fixture failed: "
            f"{command.stderr or command.error or command.returncode}"
        )
    if (
        any(digest(fixtures[case]) != fixture_hashes[case] for case in fixtures)
        or any(digest(input_fixtures[case]) != fixture_hashes[case] for case in fixtures)
        or digest(map_fixture) != map_hash
        or digest(map_input) != map_hash
    ):
        raise ValueError("Synthetic serial reference-bond inputs changed during native export")

    requirement = read_model(map_input, SerialPeerAnalysis)
    if len(requirement.links) != 1 or requirement.links[0].reference_policy != "bonded":
        raise ValueError("Synthetic serial reference-bond map no longer declares one bonded link")
    netlist_hashes: dict[tuple[str, str], str] = {}
    normalized_hashes: dict[tuple[str, str], str] = {}
    check_reports: dict[tuple[str, str], tuple[ElectricalCheck, ...]] = {}
    for case in ("control", "fault"):
        for run in ("first", "repeat"):
            path = output / f"{case}.{run}.netlist.xml"
            if not path.is_file():
                raise ValueError(f"Native serial reference-bond fixture omitted {path.name}")
            netlist_hashes[(case, run)] = digest(path)
            observed = read_netlist(path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            check_reports[(case, run)] = serial_peer_checks(requirement, observed)
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(
                f"Native serial reference-bond {case} exports differ after normalization"
            )
        first = check_reports[(case, "first")]
        repeated = check_reports[(case, "repeat")]
        first_signature = tuple((item.id, item.status, item.detail) for item in first)
        repeated_signature = tuple((item.id, item.status, item.detail) for item in repeated)
        if first_signature != repeated_signature:
            raise ValueError(
                f"Native serial reference-bond {case} checks differ on repeated export"
            )
        by_id = {item.id: item for item in first}
        reference = by_id.get("serial/serial-bond/reference")
        if reference is None:
            raise ValueError(f"Native serial reference-bond {case} omitted its reference check")
        failed = tuple(sorted(item.id for item in first if item.status == "FAIL"))
        expected_failed = ("serial/serial-bond/reference",) if case == "fault" else ()
        if failed != expected_failed or reference.status != ("FAIL" if case == "fault" else "PASS"):
            raise ValueError(
                f"Native serial reference-bond {case} mismatch: failed={failed}; "
                f"reference={reference.status}: {reference.detail}"
            )
        if case == "fault" and "R3.2 is on FLOATING_GND; expected GND_B" not in reference.detail:
            raise ValueError(
                "Native serial reference-bond fault lost the exact floating-pin evidence"
            )
        report_bytes = json.dumps(
            [item.model_dump(mode="json") for item in first],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        report_hash = hashlib.sha256(report_bytes).hexdigest()
        log.event(
            f"serial-peer-reference-bond-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=fixture_hashes[case],
            authored_map_sha256=map_hash,
            netlist_sha256=netlist_hashes[(case, "first")],
            repeat_netlist_sha256=netlist_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            check_report_sha256=report_hash,
            reference_status=reference.status,
            reference_detail=reference.detail,
            failed_checks=";".join(failed) or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_typed_serial_peer_checks",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "serial-peer-reference-bond-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{fixture_hashes[case]}" for case in ("control", "fault")),
        authored_map_sha256=map_hash,
        normalized_netlist_sha256=";".join(
            f"{case}:{normalized_hashes[(case, 'first')]}" for case in ("control", "fault")
        ),
        repeatable="true",
        repeatability_basis="normalized_native_netlist_contract",
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
