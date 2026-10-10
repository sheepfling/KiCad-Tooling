"""Hosted native connector inventory fixture lane."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def connector_inventory_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Check connector-candidate coverage from repeated pinned native netlists."""
    import hashlib
    import json
    import os

    from .hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
    from .hwrepo.connector_pins import connector_candidate_references
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ConnectorCoverageReport, ConnectorInventoryReview
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Connector inventory fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/design_lint/connector-inventory-native"
    )
    cases = ("fault", "control")
    source_hashes = {case: digest(fixture_root / f"{case}.kicad_sch") for case in cases}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"connector-inventory-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case in cases:
        shutil.copyfile(fixture_root / f"{case}.kicad_sch", inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} connector inventory fixture changed during copy")
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
        "for case in fault control; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
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
        "HOME=/tmp/kicad-connector-inventory-fixtures",
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
        "connector-inventory-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "connector-inventory-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native connector inventory export failed: {command.stderr or command.error}"
        )

    if any(
        digest(fixture_root / f"{case}.kicad_sch") != source_hashes[case]
        or digest(inputs / f"{case}.kicad_sch") != source_hashes[case]
        for case in cases
    ):
        raise ValueError("Synthetic connector inventory source changed during native export")

    normalized_hashes: dict[tuple[str, str], str] = {}
    netlist_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], ConnectorCoverageReport] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native connector inventory fixture omitted {netlist_path.name}")
            netlist_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()

            if case == "fault":
                if observed.component_symbols.get("U7") != "Connector_Generic:Conn_01x02":
                    raise ValueError(
                        "Native netlist did not retain the standard connector library identity "
                        "under reference U7"
                    )
                inventory_review = None
            else:
                if observed.component_symbols.get("U8") != "Connector:TestPoint_Alt":
                    raise ValueError(
                        "Native netlist did not retain the test-point control identity"
                    )
                inventory_review = ConnectorInventoryReview(
                    basis="Synthetic control reviewed its complete symbol inventory"
                )

            candidates = connector_candidate_references(observed)
            expected_candidates = ("U7",) if case == "fault" else ()
            if candidates != expected_candidates:
                raise ValueError(
                    f"Native connector inventory {case} candidates differ: "
                    f"expected {expected_candidates}, observed {candidates}"
                )
            reports[(case, run)] = evaluate_connector_coverage(
                observed,
                (),
                (),
                inventory_review=inventory_review,
            )

    for case in cases:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(
                f"Native connector inventory {case} netlists differ after normalization"
            )
        report = reports[(case, "first")]
        repeat_report = reports[(case, "repeat")]
        if report != repeat_report:
            raise ValueError(f"Native connector inventory {case} coverage report is not repeatable")
        expected_status = "UNDECLARED" if case == "fault" else "COMPLETE"
        if report.status != expected_status:
            raise ValueError(
                f"Native connector inventory {case} expected {expected_status}, got {report.status}"
            )
        report_path = scratch / f"{case}.coverage.json"
        write_model(report_path, report)
        log.event(
            f"connector-inventory-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=netlist_hashes[(case, "first")],
            repeat_netlist_sha256=netlist_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            coverage_sha256=digest(report_path),
            coverage_status=report.status,
            candidate_references=",".join(item.reference for item in report.entries) or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_and_connector_coverage_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "connector-inventory-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
