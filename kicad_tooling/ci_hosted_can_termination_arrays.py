"""Digest-pinned native lane for project-mapped CAN resistor arrays."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.can_termination_contract import can_termination_checks
from .hwrepo.can_termination_models import CanTerminationAnalysis
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import read_model, write_model
from .hwrepo.electrical import selected_config
from .hwrepo.electrical_analysis_contract_models import ElectricalAnalysisContract
from .hwrepo.evidence import digest
from .hwrepo.models import ElectricalCheck, NetlistContract
from .validate import read_netlist

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog

FIXTURE_HASHES = {
    "control": "1f014e79a42f45d5b08d3ef8394dd3b38e992c2af7a67c987c067afa77c3a186",
    "fault": "cae3faf3cba68758c3ed35755d49b96088799922c3c45af3fdc644f5d6d05a2d",
}
REQUIREMENT_HASH = "5c1fc55b40a292e32534aff67e3e17e535edad6e2f10d86fe2a3fe67bba3b872"


def can_termination_array_native_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Export mapped-array controls and faults twice with the project's exact KiCad image."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"CAN termination array fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/can-resistor-array-native"
    )
    fixtures = {case: fixture_root / f"{case}.kicad_sch" for case in FIXTURE_HASHES}
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    if source_hashes != FIXTURE_HASHES or digest(fixture_root / "electrical.json") != (
        REQUIREMENT_HASH
    ):
        raise ValueError("CAN termination array fixture sources differ from reviewed hashes")

    contract = read_model(fixture_root / "electrical.json", ElectricalAnalysisContract)
    if not isinstance(contract.can_termination, CanTerminationAnalysis):
        raise TypeError("Synthetic CAN array fixture must declare a required termination contract")
    requirement = contract.can_termination
    scratch = Path(
        tempfile.mkdtemp(prefix=f"native-can-array-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        shutil.copyfile(fixture, inputs / fixture.name)
        if digest(inputs / fixture.name) != source_hashes[case]:
            raise ValueError(f"Synthetic CAN array {case} fixture changed while staging")
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
        "HOME=/tmp/kicad-can-array-fixtures",
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
        "can-termination-array-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "can-termination-array-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native CAN array export failed: {command.stderr or command.error}")

    observations: dict[tuple[str, str], NetlistContract] = {}
    reports: dict[tuple[str, str], tuple[ElectricalCheck, ...]] = {}
    hashes: dict[tuple[str, str], str] = {}
    for case, fixture in fixtures.items():
        if digest(fixture) != source_hashes[case]:
            raise ValueError("Synthetic CAN array fixture changed during native export")
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native CAN array export omitted {netlist_path.name}")
            observed = read_netlist(netlist_path)
            observations[(case, run)] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            reports[(case, run)] = can_termination_checks(requirement, observed)

    expected_ids = {
        "can-termination/fieldbus/signal-pins",
        "can-termination/fieldbus/unlisted-direct",
        "can-termination/fieldbus/local",
    }
    control = observations[("control", "first")]
    if (
        control.components.get("RN1") is None
        or control.components["RN1"].value != "2x60R"
        or control.components["RN1"].footprint != "Synthetic:RA4"
        or control.components["RN1"].part_id != "SYNTHETIC-CAN-60R2"
        or control.component_symbols.get("RN1") != "Synthetic:ResistorArray"
        or set(control.component_pin_numbers.get("RN1", ())) != {"1", "2", "3", "4"}
        or set(control.nets.get("CAN_H", ())) != {"RN1.1", "U1.1"}
        or set(control.nets.get("CAN_L", ())) != {"RN1.3", "U1.2"}
        or set(control.nets.get("CAN_TERM_MID", ())) != {"RN1.2", "RN1.4"}
        or control.pin_functions.get("U1.1") != "CANH"
        or control.pin_functions.get("U1.2") != "CANL"
    ):
        raise ValueError("Native CAN array control lost its exact identity, pin inventory, or nets")

    control_checks = {item.id: item for item in reports[("control", "first")]}
    if (
        set(control_checks) != expected_ids
        or any(item.status != "PASS" for item in control_checks.values())
        or control_checks["can-termination/fieldbus/local"].observed is not None
        or "resistance is not measured"
        not in control_checks["can-termination/fieldbus/local"].detail
    ):
        raise ValueError("Native mapped CAN array control did not pass with the evidence limit")

    fault = observations[("fault", "first")]
    fault_checks = {item.id: item for item in reports[("fault", "first")]}
    array_id = "can-termination/fieldbus/local"
    if (
        set(fault_checks) != expected_ids
        or fault.nets.get("CAN_WRONG") != ("RN1.1",)
        or fault_checks[array_id].status != "FAIL"
        or "RN1 channel high-leg" not in fault_checks[array_id].detail
        or any(fault_checks[check_id].status != "PASS" for check_id in expected_ids - {array_id})
    ):
        raise ValueError("Native CAN array fault did not isolate the mapped channel mismatch")

    for case in fixtures:
        if hashes[(case, "first")] != hashes[(case, "repeat")]:
            raise ValueError(f"Native CAN array {case} exports differ after typed normalization")
        checks = {item.id: item for item in reports[(case, "first")]}
        log.event(
            f"can-termination-array-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            requirement_sha256=REQUIREMENT_HASH,
            normalized_netlist_sha256=hashes[(case, "first")],
            repeat_normalized_netlist_sha256=hashes[(case, "repeat")],
            signal_pins=checks["can-termination/fieldbus/signal-pins"].status,
            unlisted_direct=checks["can-termination/fieldbus/unlisted-direct"].status,
            array_path=checks[array_id].status,
            repeatable="true",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "can-termination-array-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in fixtures),
        requirement_sha256=REQUIREMENT_HASH,
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
