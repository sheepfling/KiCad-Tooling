"""Exact-version native fixtures for SPI shared-clock reference review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.component_peer_pin_findings import (
    component_peer_power_pin_assignment_divergences,
)
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import write_model
from .hwrepo.design_lint_spi_candidates import spi_peer_reference_candidates
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import NetlistContract
from .hwrepo.spi_peer_reference_scan import scan_spi_peer_references
from .validate import read_netlist


def spi_peer_reference_native_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify split/common clock-reference fixtures through pinned KiCad exports."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"SPI peer-reference fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = tooling_checkout_root() / "tests/fixtures/design_lint/spi-peer-reference-native"
    fixtures = {case: fixture_root / f"{case}.kicad_sch" for case in ("control", "fault")}
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    expected_source_hashes = {
        "control": "a6e4d8da462d9381763fc1cbc23e10fd922506effa09bf7f14ad9509b53bc976",
        "fault": "c78a85c48b12c4f2350cfb624e3b57126e7c6dad354cc42e0e1a8f5c6fbce4b4",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("SPI peer-reference fixture sources differ from the reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"native-spi-peer-reference-{project}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        shutil.copyfile(fixture, inputs / fixture.name)
        if digest(inputs / fixture.name) != source_hashes[case]:
            raise ValueError(f"Synthetic SPI {case} fixture changed while preparing native input")
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
        "HOME=/tmp/kicad-spi-peer-reference",
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
        "spi-peer-reference-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    receipt_path = receipt.relative_to(root).as_posix()
    if command.returncode != 0 or command.error is not None:
        log.event(
            "spi-peer-reference-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=receipt_path,
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native SPI peer-reference export failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    observations: dict[tuple[str, str], NetlistContract] = {}
    for case, fixture in fixtures.items():
        if (
            digest(fixture) != source_hashes[case]
            or digest(inputs / fixture.name) != source_hashes[case]
        ):
            raise ValueError("Synthetic SPI fixture changed during native export")
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native SPI fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
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
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native SPI {case} export is not repeatable")

    for case, expected_disposition in (
        ("control", "COMMON_REFERENCE"),
        ("fault", "SPLIT_REFERENCE_REVIEW"),
    ):
        observed = observations[(case, "first")]
        scan = scan_spi_peer_references(observed)
        if (
            scan.recognized_endpoint_count != 2
            or len(scan.buses) != 1
            or scan.buses[0].disposition != expected_disposition
        ):
            raise ValueError(f"Native SPI {case} fixture did not produce {expected_disposition}")
        bus = scan.buses[0]
        if bus.clock_net != "SPI_SCK":
            raise ValueError(
                f"Native SPI {case} fixture exported unexpected SCK net {bus.clock_net}"
            )
        if set(observed.nets.get("+3V3", ())) != {"U1.4", "U2.4"}:
            raise ValueError(f"Native SPI {case} fixture did not preserve the common +3V3 supply")
        if tuple(item.reference for item in bus.endpoints) != ("U1", "U2"):
            raise ValueError(f"Native SPI {case} fixture exported unexpected peer references")
        if observed.component_symbols.get("U1") == observed.component_symbols.get("U2"):
            raise ValueError("Native SPI peer fixtures must use distinct symbol identities")
        if component_peer_power_pin_assignment_divergences(observed):
            raise ValueError("SPI peer fixture unexpectedly overlaps component-peer findings")
        candidates = spi_peer_reference_candidates(observed, scan)
        expected_count = 0 if case == "control" else 1
        if len(candidates) != expected_count:
            raise ValueError(
                f"Native SPI {case} fixture produced {len(candidates)} lint candidates; "
                f"expected {expected_count}"
            )
        expected_references = ("GND",) if case == "control" else ("GND_A", "GND_B")
        reference_nets = tuple(
            sorted({item.reference_net for item in bus.endpoints if item.reference_net is not None})
        )
        if reference_nets != expected_references:
            raise ValueError(
                f"Native SPI {case} fixture exported wrong references: {reference_nets}"
            )
        log.event(
            f"spi-peer-reference-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            raw_netlist_sha256=raw_hashes[(case, "first")],
            repeat_raw_netlist_sha256=raw_hashes[(case, "repeat")],
            sck=bus.clock_net,
            supply="+3V3",
            references=",".join(expected_references),
            disposition=expected_disposition,
            lint_candidate_count=str(expected_count),
            repeatable="true",
            command_receipt=receipt_path,
        )
    log.event(
        "spi-peer-reference-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in fixtures),
        command_receipt=receipt_path,
    )
