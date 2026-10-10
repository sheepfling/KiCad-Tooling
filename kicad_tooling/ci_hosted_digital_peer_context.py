"""Source-bound setup for synthetic SPI and peer-interface native fixtures."""

from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.models import NetlistContract, ProjectConfig


class DigitalPeerLog(Protocol):
    directory: Path

    def event(self, stage: str, status: str, **details: str | float) -> None: ...


@dataclass(slots=True)
class DigitalPeerFixtureContext:
    root: Path
    project: str
    config: ProjectConfig
    pinned: str
    log: DigitalPeerLog
    scratch: Path
    fixture_root: Path
    source_hash: str
    peer_fixtures: dict[str, Path]
    peer_source_hashes: dict[str, str]
    serial_peer_fixtures: dict[str, Path]
    serial_peer_source_hashes: dict[str, str]
    serial_connector_reference_fixtures: dict[str, Path]
    serial_connector_reference_source_hashes: dict[str, str]
    serial_label_reference_fixtures: dict[str, Path]
    serial_label_reference_source_hashes: dict[str, str]
    component_peer_fixtures: dict[str, Path]
    component_peer_source_hashes: dict[str, str]
    contracts: dict[str, dict[str, NetlistContract]]
    hashes: dict[str, dict[str, str]]
    normalized_hashes: dict[str, dict[str, str]]
    normalized_erc_hashes: dict[str, dict[str, str]]
    erc_report_versions: dict[str, dict[str, str]]
    erc_warning_types: dict[str, dict[str, tuple[str, ...]]]
    erc_error_types: dict[str, dict[str, tuple[str, ...]]]
    observed: NetlistContract


def prepare_digital_peer_fixture_context(
    root: Path, project: str, image: str, log: DigitalPeerLog
) -> DigitalPeerFixtureContext:
    """Prepare synthetic peer fixtures and repeatable pinned native exports."""
    import hashlib
    import json
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Digital-peer fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    fixture = fixture_root / "spi-participant-native/multi-device.kicad_sch"
    source_hash = digest(fixture)
    scratch = Path(
        tempfile.mkdtemp(prefix=f"spi-participant-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    source = inputs / "multi-device.kicad_sch"
    shutil.copyfile(fixture, source)
    if digest(source) != source_hash:
        raise ValueError("Synthetic SPI fixture changed while preparing native input")
    peer_fixtures = {
        case: fixture_root / f"spi-peer-voltage-native/{case}.kicad_sch"
        for case in ("peer-control", "peer-fault", "peer-translator-control")
    }
    peer_source_hashes = {case: digest(path) for (case, path) in peer_fixtures.items()}
    for case, path in peer_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != peer_source_hashes[case]:
            raise ValueError(f"Synthetic SPI {case} fixture changed while preparing native input")
    serial_peer_fixtures = {
        case: fixture_root / f"serial-peer-voltage-native/{case}.kicad_sch"
        for case in ("serial-control", "serial-fault", "serial-reference-fault")
    }
    serial_peer_source_hashes = {
        case: digest(path) for (case, path) in serial_peer_fixtures.items()
    }
    for case, path in serial_peer_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != serial_peer_source_hashes[case]:
            raise ValueError(f"Synthetic UART {case} fixture changed while preparing native input")
    serial_connector_reference_fixtures = {
        case: fixture_root / f"serial-peer-connector-reference-native/{case}.kicad_sch"
        for case in ("serial-connector-control", "serial-connector-fault")
    }
    serial_connector_reference_source_hashes = {
        case: digest(path) for (case, path) in serial_connector_reference_fixtures.items()
    }
    for case, path in serial_connector_reference_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != serial_connector_reference_source_hashes[case]:
            raise ValueError(
                f"Synthetic UART connector {case} fixture changed while preparing native input"
            )
    serial_label_reference_fixtures = {
        case: fixture_root / f"serial-peer-connector-reference-native/{case}.kicad_sch"
        for case in ("serial-label-control", "serial-label-fault")
    }
    serial_label_reference_source_hashes = {
        case: digest(path) for (case, path) in serial_label_reference_fixtures.items()
    }
    for case, path in serial_label_reference_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != serial_label_reference_source_hashes[case]:
            raise ValueError(
                f"Synthetic UART label {case} fixture changed while preparing native input"
            )
    component_peer_fixtures = {
        f"component-peer-{case}": fixture_root / f"component-peer-power-native/{case}.kicad_sch"
        for case in ("control", "fault")
    }
    component_peer_source_hashes = {
        case: digest(path) for (case, path) in component_peer_fixtures.items()
    }
    for case, path in component_peer_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != component_peer_source_hashes[case]:
            raise ValueError(
                f"Synthetic component peer {case} fixture changed while preparing native input"
            )
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = f'mkdir -p "$HOME"\nactual="$(kicad-cli version)"\nprintf "kicad_version=%s\\n" "$actual"\ntest "$actual" = "{config.kicad_version}"\nfor case in multi-device peer-control peer-fault peer-translator-control serial-control serial-fault serial-reference-fault serial-connector-control serial-connector-fault serial-label-control serial-label-fault component-peer-control component-peer-fault; do\n  for run in first repeat; do\n    kicad-cli sch export netlist --format kicadxml       --output "/output/${{case}}.${{run}}.netlist.xml"       "/fixtures/${{case}}.kicad_sch"\n    case "$case" in component-peer-*)\n      kicad-cli sch erc --format json --severity-all         --output "/output/${{case}}.${{run}}.erc.json"         "/fixtures/${{case}}.kicad_sch" ;;\n    esac\n  done\ndone\n'
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
        "HOME=/tmp/kicad-spi-fixtures",
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
        "spi-participant-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "spi-participant-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native SPI fixture command failed: {command.stderr or command.error}")
    log.event(
        "spi-participant-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_sha256=source_hash,
        peer_source_hashes=";".join(f"{case}:{peer_source_hashes[case]}" for case in peer_fixtures),
        serial_peer_source_hashes=";".join(
            f"{case}:{serial_peer_source_hashes[case]}" for case in serial_peer_fixtures
        ),
        serial_connector_reference_source_hashes=";".join(
            f"{case}:{serial_connector_reference_source_hashes[case]}"
            for case in serial_connector_reference_fixtures
        ),
        serial_label_reference_source_hashes=";".join(
            f"{case}:{serial_label_reference_source_hashes[case]}"
            for case in serial_label_reference_fixtures
        ),
        component_peer_source_hashes=";".join(
            f"{case}:{component_peer_source_hashes[case]}" for case in component_peer_fixtures
        ),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    if (
        digest(fixture) != source_hash
        or digest(source) != source_hash
        or any(
            digest(peer_fixtures[case]) != peer_source_hashes[case]
            or digest(inputs / f"{case}.kicad_sch") != peer_source_hashes[case]
            for case in peer_fixtures
        )
        or any(
            digest(serial_peer_fixtures[case]) != serial_peer_source_hashes[case]
            or digest(inputs / f"{case}.kicad_sch") != serial_peer_source_hashes[case]
            for case in serial_peer_fixtures
        )
        or any(
            digest(serial_connector_reference_fixtures[case])
            != serial_connector_reference_source_hashes[case]
            or digest(inputs / f"{case}.kicad_sch")
            != serial_connector_reference_source_hashes[case]
            for case in serial_connector_reference_fixtures
        )
        or any(
            digest(serial_label_reference_fixtures[case])
            != serial_label_reference_source_hashes[case]
            or digest(inputs / f"{case}.kicad_sch") != serial_label_reference_source_hashes[case]
            for case in serial_label_reference_fixtures
        )
        or any(
            digest(component_peer_fixtures[case]) != component_peer_source_hashes[case]
            or digest(inputs / f"{case}.kicad_sch") != component_peer_source_hashes[case]
            for case in component_peer_fixtures
        )
    ):
        raise ValueError("Synthetic SPI fixture source changed during native export")
    contracts: dict[str, dict[str, NetlistContract]] = {}
    hashes: dict[str, dict[str, str]] = {}
    normalized_hashes: dict[str, dict[str, str]] = {}
    normalized_erc_hashes: dict[str, dict[str, str]] = {}
    erc_report_versions: dict[str, dict[str, str]] = {}
    erc_warning_types: dict[str, dict[str, tuple[str, ...]]] = {}
    erc_error_types: dict[str, dict[str, tuple[str, ...]]] = {}
    fixture_cases = (
        "multi-device",
        *peer_fixtures,
        *serial_peer_fixtures,
        *serial_connector_reference_fixtures,
        *serial_label_reference_fixtures,
        *component_peer_fixtures,
    )
    for fixture_case in fixture_cases:
        contracts[fixture_case] = {}
        hashes[fixture_case] = {}
        normalized_hashes[fixture_case] = {}
        for run in ("first", "repeat"):
            path = output / f"{fixture_case}.{run}.netlist.xml"
            if not path.is_file():
                raise ValueError(f"Native SPI fixture omitted {path.name}")
            hashes[fixture_case][run] = digest(path)
            observed = read_netlist(path)
            contracts[fixture_case][run] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[fixture_case][run] = hashlib.sha256(normalized).hexdigest()
    for case in component_peer_fixtures:
        normalized_erc_hashes[case] = {}
        erc_report_versions[case] = {}
        erc_warning_types[case] = {}
        erc_error_types[case] = {}
        for run in ("first", "repeat"):
            erc_path = output / f"{case}.{run}.erc.json"
            if not erc_path.is_file():
                raise ValueError(f"Native component peer fixture omitted {erc_path.name}")
            erc_report = read_kicad_erc_report(erc_path)
            if erc_report.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native component peer {case} ERC report version differs from KiCad {config.kicad_version}"
                )
            erc_report_versions[case][run] = erc_report.kicad_version
            erc_rows = [
                (
                    item.type,
                    item.severity,
                    item.description,
                    tuple(
                        sorted(
                            [(detail.description, detail.x, detail.y) for detail in item.items],
                            key=lambda detail: json.dumps(
                                detail, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                            ),
                        )
                    ),
                )
                for item in erc_report.violations
            ]
            erc_rows.sort(
                key=lambda item: json.dumps(
                    item, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                )
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc_report.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[case][run] = hashlib.sha256(normalized_erc).hexdigest()
            erc_warning_types[case][run] = tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "warning")
            )
            erc_error_types[case][run] = tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "error")
            )
    return DigitalPeerFixtureContext(
        root=root,
        project=project,
        config=config,
        pinned=pinned,
        log=log,
        scratch=scratch,
        fixture_root=fixture_root,
        source_hash=source_hash,
        peer_fixtures=peer_fixtures,
        peer_source_hashes=peer_source_hashes,
        serial_peer_fixtures=serial_peer_fixtures,
        serial_peer_source_hashes=serial_peer_source_hashes,
        serial_connector_reference_fixtures=serial_connector_reference_fixtures,
        serial_connector_reference_source_hashes=serial_connector_reference_source_hashes,
        serial_label_reference_fixtures=serial_label_reference_fixtures,
        serial_label_reference_source_hashes=serial_label_reference_source_hashes,
        component_peer_fixtures=component_peer_fixtures,
        component_peer_source_hashes=component_peer_source_hashes,
        contracts=contracts,
        hashes=hashes,
        normalized_hashes=normalized_hashes,
        normalized_erc_hashes=normalized_erc_hashes,
        erc_report_versions=erc_report_versions,
        erc_warning_types=erc_warning_types,
        erc_error_types=erc_error_types,
        observed=contracts["multi-device"]["first"],
    )
