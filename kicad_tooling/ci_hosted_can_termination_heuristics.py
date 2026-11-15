"""Hosted native fixture lane for CAN termination review heuristics."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import write_model
from .hwrepo.design_lint_can_candidates import can_candidates
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.native_report_parsing import read_netlist
from .hwrepo.netlist_contract_models import NetlistContract


def can_termination_heuristics_native_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Check termination review heuristics against exact-version native exports."""

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"CAN termination heuristic fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)

    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/can-termination-heuristics-native"
    )
    fixtures = {
        case: fixture_root / f"{case}.kicad_sch" for case in ("control", "fault", "missing")
    }
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    expected_source_hashes = {
        "missing": "b60b3cde1767d6b44c4995b6683b711bbd74941094818187653a203710cf5a96",
        "control": "3baa84f1494dc7cdd8b4bef63aa1df792adccfbc8b429410895b6d8fc1c45ed7",
        "fault": "97f8f0b2feaff11d2a8dd73e6ccb0f4e8f745b5a550813728b703a7216d28756",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("CAN termination heuristic fixture sources differ from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"native-can-termination-heuristics-{project}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        shutil.copyfile(fixture, inputs / fixture.name)
        if digest(inputs / fixture.name) != source_hashes[case]:
            raise ValueError(f"Synthetic CAN {case} fixture changed while preparing native input")
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
        "for case in control fault missing; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml \\\n"
        '      --output "/output/${case}.${run}.netlist.xml" \\\n'
        '      "/fixtures/${case}.kicad_sch"\n'
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
        "HOME=/tmp/kicad-can-termination-heuristics-fixtures",
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
        "can-termination-heuristics-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    command_receipt = (scratch / "native.command.json").relative_to(root).as_posix()
    if command.returncode != 0 or command.error is not None:
        log.event(
            "can-termination-heuristics-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=command_receipt,
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native CAN termination-heuristic export failed: {command.stderr or command.error}"
        )
    log.event(
        "can-termination-heuristics-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in fixtures),
        command_receipt=command_receipt,
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    observations: dict[tuple[str, str], NetlistContract] = {}
    for case, fixture in fixtures.items():
        if digest(fixture) != source_hashes[case]:
            log.event(
                f"can-termination-heuristics-fixture/{case}",
                "FAIL",
                project=project,
                kicad_version=config.kicad_version,
                image=pinned,
                source_sha256=digest(fixture),
                expected_source_sha256=source_hashes[case],
                command_receipt=command_receipt,
            )
            raise ValueError("Synthetic CAN excess-termination fixture changed during export")
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                log.event(
                    f"can-termination-heuristics-fixture/{case}",
                    "FAIL",
                    project=project,
                    kicad_version=config.kicad_version,
                    image=pinned,
                    missing_netlist=netlist_path.name,
                    command_receipt=command_receipt,
                )
                raise ValueError(f"Native CAN fixture omitted {netlist_path.name}")
            observed = read_netlist(netlist_path)
            observations[(case, run)] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()

    for case in fixtures:
        first_hash = normalized_hashes[(case, "first")]
        repeat_hash = normalized_hashes[(case, "repeat")]
        if first_hash != repeat_hash:
            log.event(
                f"can-termination-heuristics-fixture/{case}",
                "FAIL",
                project=project,
                kicad_version=config.kicad_version,
                image=pinned,
                normalized_netlist_sha256=first_hash,
                repeat_normalized_netlist_sha256=repeat_hash,
                command_receipt=command_receipt,
            )
            raise ValueError(f"Native CAN {case} exports differ after typed normalization")
        observed = observations[(case, "first")]
        excess_candidates = tuple(
            item
            for item in can_candidates(observed)
            if item.rule_id == "bus.can_excess_termination"
        )
        expected_excess_count = 1 if case == "fault" else 0
        if len(excess_candidates) != expected_excess_count:
            log.event(
                f"can-termination-heuristics-fixture/{case}",
                "FAIL",
                project=project,
                kicad_version=config.kicad_version,
                image=pinned,
                source_sha256=source_hashes[case],
                normalized_netlist_sha256=first_hash,
                findings=len(excess_candidates),
                expected_findings=expected_excess_count,
                command_receipt=command_receipt,
            )
            raise ValueError(
                f"Native CAN {case} exported {len(excess_candidates)} excess-termination findings; "
                f"expected {expected_excess_count}"
            )
        if case == "fault" and excess_candidates[0].evidence.get("terminations") != (
            "R1=120 Ω",
            "R2=120 Ω",
            "R3=120 Ω",
        ):
            log.event(
                f"can-termination-heuristics-fixture/{case}",
                "FAIL",
                project=project,
                kicad_version=config.kicad_version,
                image=pinned,
                source_sha256=source_hashes[case],
                normalized_netlist_sha256=first_hash,
                evidence=json.dumps(dict(excess_candidates[0].evidence), sort_keys=True),
                command_receipt=command_receipt,
            )
            raise ValueError(
                "Native CAN excess-termination evidence did not retain all three resistors"
            )
        log.event(
            f"can-termination-heuristics-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=first_hash,
            repeat_normalized_netlist_sha256=repeat_hash,
            findings=len(excess_candidates),
            evidence=(
                json.dumps(dict(excess_candidates[0].evidence), sort_keys=True)
                if excess_candidates
                else "none"
            ),
            repeatable="true",
            command_receipt=command_receipt,
        )
        missing_candidates = tuple(
            item
            for item in can_candidates(observed)
            if item.rule_id == "bus.can_missing_termination"
        )
        expected_missing_count = 1 if case == "missing" else 0
        if len(missing_candidates) != expected_missing_count:
            log.event(
                f"can-missing-termination-fixture/{case}",
                "FAIL",
                project=project,
                kicad_version=config.kicad_version,
                image=pinned,
                source_sha256=source_hashes[case],
                normalized_netlist_sha256=first_hash,
                findings=len(missing_candidates),
                expected_findings=expected_missing_count,
                dnp_components=",".join(observed.dnp_components),
                command_receipt=command_receipt,
            )
            raise ValueError(
                f"Native CAN {case} exported {len(missing_candidates)} missing-termination "
                f"findings; expected {expected_missing_count}"
            )
        if case == "missing" and (
            set(observed.dnp_components) != {"R1", "R2"}
            or missing_candidates[0].evidence.get("termination") != ()
            or missing_candidates[0].evidence.get("CANH") != ("NET_A",)
            or missing_candidates[0].evidence.get("CANL") != ("NET_B",)
        ):
            log.event(
                f"can-missing-termination-fixture/{case}",
                "FAIL",
                project=project,
                kicad_version=config.kicad_version,
                image=pinned,
                source_sha256=source_hashes[case],
                normalized_netlist_sha256=first_hash,
                evidence=json.dumps(dict(missing_candidates[0].evidence), sort_keys=True),
                dnp_components=",".join(observed.dnp_components),
                command_receipt=command_receipt,
            )
            raise ValueError("Native CAN missing-termination fault lost its DNP resistor evidence")
        log.event(
            f"can-missing-termination-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=first_hash,
            repeat_normalized_netlist_sha256=repeat_hash,
            findings=len(missing_candidates),
            evidence=(
                json.dumps(dict(missing_candidates[0].evidence), sort_keys=True)
                if missing_candidates
                else "none"
            ),
            dnp_components=",".join(observed.dnp_components),
            repeatable="true",
            command_receipt=command_receipt,
        )
