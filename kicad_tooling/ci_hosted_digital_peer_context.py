"""Source-bound setup for synthetic SPI and peer-interface native fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from .ci_hosted_digital_peer_models import (
    COMPONENT_PEER_FIXTURE_CASES,
    FIXTURE_CASES,
    SERIAL_CONNECTOR_REFERENCE_CASES,
    SERIAL_LABEL_REFERENCE_CASES,
    SERIAL_PEER_FIXTURE_CASES,
    SPI_PEER_FIXTURE_CASES,
    DigitalPeerFixtureCase,
    DigitalPeerFixtureContext,
    DigitalPeerFixtureEvidence,
    DigitalPeerFixtureSource,
    DigitalPeerLog,
    NativeErcRunEvidence,
    NativeNetlistRunEvidence,
    NativeRunPair,
)
from .ci_hosted_native_fixture_models import NativeRun
from .ci_hosted_support import tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .validate import read_netlist


def prepare_digital_peer_fixture_context(
    root: Path, project: str, image: str, log: DigitalPeerLog
) -> DigitalPeerFixtureContext:
    """Prepare synthetic peer fixtures and repeatable pinned native exports."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Digital-peer fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint"
    fixture = fixture_root / "spi-participant-native/multi-device.kicad_sch"
    source_hash = digest(fixture)
    combo_spi_fixture = fixture_root / "spi-composite-participant-native/combo-device.kicad_sch"
    combo_spi_source_hash = digest(combo_spi_fixture)
    scratch = Path(
        tempfile.mkdtemp(prefix=f"spi-participant-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    source = inputs / "multi-device.kicad_sch"
    shutil.copyfile(fixture, source)
    if digest(source) != source_hash:
        raise ValueError("Synthetic SPI fixture changed while preparing native input")
    combo_spi_source = inputs / "combo-device.kicad_sch"
    shutil.copyfile(combo_spi_fixture, combo_spi_source)
    if digest(combo_spi_source) != combo_spi_source_hash:
        raise ValueError("Synthetic SPI combo-interface fixture changed while preparing input")
    peer_fixtures: dict[DigitalPeerFixtureCase, Path] = {
        case: fixture_root / f"spi-peer-voltage-native/{case}.kicad_sch"
        for case in SPI_PEER_FIXTURE_CASES
    }
    peer_source_hashes: dict[DigitalPeerFixtureCase, str] = {
        case: digest(path) for (case, path) in peer_fixtures.items()
    }
    for case, path in peer_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != peer_source_hashes[case]:
            raise ValueError(f"Synthetic SPI {case} fixture changed while preparing native input")
    serial_peer_fixtures: dict[DigitalPeerFixtureCase, Path] = {
        case: fixture_root / f"serial-peer-voltage-native/{case}.kicad_sch"
        for case in SERIAL_PEER_FIXTURE_CASES
    }
    serial_peer_source_hashes: dict[DigitalPeerFixtureCase, str] = {
        case: digest(path) for (case, path) in serial_peer_fixtures.items()
    }
    for case, path in serial_peer_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != serial_peer_source_hashes[case]:
            raise ValueError(f"Synthetic UART {case} fixture changed while preparing native input")
    serial_connector_reference_fixtures: dict[DigitalPeerFixtureCase, Path] = {
        case: fixture_root / f"serial-peer-connector-reference-native/{case}.kicad_sch"
        for case in SERIAL_CONNECTOR_REFERENCE_CASES
    }
    serial_connector_reference_source_hashes: dict[DigitalPeerFixtureCase, str] = {
        case: digest(path) for (case, path) in serial_connector_reference_fixtures.items()
    }
    for case, path in serial_connector_reference_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != serial_connector_reference_source_hashes[case]:
            raise ValueError(
                f"Synthetic UART connector {case} fixture changed while preparing native input"
            )
    serial_label_reference_fixtures: dict[DigitalPeerFixtureCase, Path] = {
        case: fixture_root / f"serial-peer-connector-reference-native/{case}.kicad_sch"
        for case in SERIAL_LABEL_REFERENCE_CASES
    }
    serial_label_reference_source_hashes: dict[DigitalPeerFixtureCase, str] = {
        case: digest(path) for (case, path) in serial_label_reference_fixtures.items()
    }
    for case, path in serial_label_reference_fixtures.items():
        copied = inputs / f"{case}.kicad_sch"
        shutil.copyfile(path, copied)
        if digest(copied) != serial_label_reference_source_hashes[case]:
            raise ValueError(
                f"Synthetic UART label {case} fixture changed while preparing native input"
            )
    component_peer_fixtures: dict[DigitalPeerFixtureCase, Path] = {
        "component-peer-control": fixture_root / "component-peer-power-native/control.kicad_sch",
        "component-peer-fault": fixture_root / "component-peer-power-native/fault.kicad_sch",
    }
    component_peer_source_hashes: dict[DigitalPeerFixtureCase, str] = {
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
    fixture_case_list = " ".join(FIXTURE_CASES)
    script = f'mkdir -p "$HOME"\nactual="$(kicad-cli version)"\nprintf "kicad_version=%s\\n" "$actual"\ntest "$actual" = "{config.kicad_version}"\nfor case in {fixture_case_list}; do\n  for run in first repeat; do\n    kicad-cli sch export netlist --format kicadxml       --output "/output/${{case}}.${{run}}.netlist.xml"       "/fixtures/${{case}}.kicad_sch"\n    case "$case" in component-peer-*)\n      kicad-cli sch erc --format json --severity-all         --output "/output/${{case}}.${{run}}.erc.json"         "/fixtures/${{case}}.kicad_sch" ;;\n    esac\n  done\ndone\n'
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
        combo_spi_source_sha256=combo_spi_source_hash,
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
        or digest(combo_spi_fixture) != combo_spi_source_hash
        or digest(combo_spi_source) != combo_spi_source_hash
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

    def fixture_sources(
        paths: Mapping[DigitalPeerFixtureCase, Path],
        source_hashes: Mapping[DigitalPeerFixtureCase, str],
    ) -> dict[DigitalPeerFixtureCase, DigitalPeerFixtureSource]:
        return {
            case: DigitalPeerFixtureSource(path=path, sha256=source_hashes[case])
            for case, path in paths.items()
        }

    sources: dict[DigitalPeerFixtureCase, DigitalPeerFixtureSource] = {
        "multi-device": DigitalPeerFixtureSource(path=fixture, sha256=source_hash),
        "combo-device": DigitalPeerFixtureSource(
            path=combo_spi_fixture, sha256=combo_spi_source_hash
        ),
    }
    sources.update(fixture_sources(peer_fixtures, peer_source_hashes))
    sources.update(fixture_sources(serial_peer_fixtures, serial_peer_source_hashes))
    sources.update(
        fixture_sources(
            serial_connector_reference_fixtures, serial_connector_reference_source_hashes
        )
    )
    sources.update(
        fixture_sources(serial_label_reference_fixtures, serial_label_reference_source_hashes)
    )
    sources.update(fixture_sources(component_peer_fixtures, component_peer_source_hashes))

    def load_netlist_run(case: DigitalPeerFixtureCase, run: NativeRun) -> NativeNetlistRunEvidence:
        path = output / f"{case}.{run}.netlist.xml"
        if not path.is_file():
            raise ValueError(f"Native SPI fixture omitted {path.name}")
        observed = read_netlist(path)
        normalized = json.dumps(
            observed.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return NativeNetlistRunEvidence(
            contract=observed,
            netlist_sha256=digest(path),
            normalized_sha256=hashlib.sha256(normalized).hexdigest(),
        )

    def load_erc_run(case: DigitalPeerFixtureCase, run: NativeRun) -> NativeErcRunEvidence:
        erc_path = output / f"{case}.{run}.erc.json"
        if not erc_path.is_file():
            raise ValueError(f"Native component peer fixture omitted {erc_path.name}")
        erc_report = read_kicad_erc_report(erc_path)
        if erc_report.kicad_version != config.kicad_version:
            raise ValueError(
                f"Native component peer {case} ERC report version differs from KiCad {config.kicad_version}"
            )
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
        return NativeErcRunEvidence(
            kicad_version=erc_report.kicad_version,
            normalized_sha256=hashlib.sha256(normalized_erc).hexdigest(),
            warning_types=tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "warning")
            ),
            error_types=tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "error")
            ),
        )

    fixtures: dict[DigitalPeerFixtureCase, DigitalPeerFixtureEvidence] = {}
    for case in FIXTURE_CASES:
        component_erc = (
            NativeRunPair(
                first=load_erc_run(case, "first"),
                repeat=load_erc_run(case, "repeat"),
            )
            if case in COMPONENT_PEER_FIXTURE_CASES
            else None
        )
        fixtures[case] = DigitalPeerFixtureEvidence(
            case=case,
            source=sources[case],
            netlists=NativeRunPair(
                first=load_netlist_run(case, "first"),
                repeat=load_netlist_run(case, "repeat"),
            ),
            component_erc=component_erc,
        )
    return DigitalPeerFixtureContext(
        root=root,
        project=project,
        config=config,
        pinned=pinned,
        log=log,
        scratch=scratch,
        fixture_root=fixture_root,
        fixtures=fixtures,
    )
