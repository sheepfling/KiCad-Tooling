"""Hosted native I2C pull-up fixture lane."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def i2c_pullup_native_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Exercise mapped I2C resistor-array requirements from pinned native exports."""
    import hashlib

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.i2c_pullup_contract import (
        i2c_pullup_checks,
    )
    from .hwrepo.i2c_pullup_models import (
        I2cPullupAnalysis,
        I2cPullupArrayChannelRequirement,
        I2cPullupArrayRequirement,
        I2cPullupBusRequirement,
        I2cPullupLineRequirement,
    )
    from .hwrepo.models import ElectricalCheck, NetlistContract
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"I2C pull-up fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/i2c-array-native"
    )
    fixtures = {case: fixture_root / f"{case}.kicad_sch" for case in ("control", "fault")}
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    expected_source_hashes = {
        "control": "922e40c8815a302e8af30e3eb7e4a53b1b3361be419cc0c56fe3025619a7243d",
        "fault": "062648e3ec3d9c71e976fc40370d4d7a1ab4d6064e73d79fe191878ee052efc4",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("I2C pull-up fixture sources differ from the reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"native-i2c-pullup-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        shutil.copyfile(fixture, inputs / fixture.name)
        if digest(inputs / fixture.name) != source_hashes[case]:
            raise ValueError(f"Synthetic I2C {case} fixture changed while preparing native input")
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
        "HOME=/tmp/kicad-i2c-pullup-fixtures",
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
        "i2c-pullup-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "i2c-pullup-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native I2C pull-up export failed: {command.stderr or command.error}")
    log.event(
        "i2c-pullup-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in fixtures),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    requirement = I2cPullupAnalysis(
        basis="Synthetic reviewed resistor-array and local I2C bus requirements",
        buses=(
            I2cPullupBusRequirement(
                id="array-bus",
                basis="Synthetic two-line bus",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
            ),
        ),
        arrays=(
            I2cPullupArrayRequirement(
                reference="RN1",
                expected_symbol="Synthetic:ResistorArray",
                expected_footprint="Synthetic:RA4",
                expected_value="4x4.7k",
                basis="Synthetic array pin map and nominal channel values",
                channels=(
                    I2cPullupArrayChannelRequirement(
                        id="sda",
                        signal_pin="RN1.1",
                        rail_pin="RN1.2",
                        signal_net="I2C_SDA",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic SDA resistor-array channel",
                    ),
                    I2cPullupArrayChannelRequirement(
                        id="scl",
                        signal_pin="RN1.3",
                        rail_pin="RN1.4",
                        signal_net="I2C_SCL",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic SCL resistor-array channel",
                    ),
                ),
            ),
        ),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    observations: dict[tuple[str, str], NetlistContract] = {}
    reports: dict[tuple[str, str], tuple[ElectricalCheck, ...]] = {}
    for case, fixture in fixtures.items():
        if (
            digest(fixture) != source_hashes[case]
            or digest(inputs / fixture.name) != source_hashes[case]
        ):
            raise ValueError("Synthetic I2C fixture changed during native export")
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native I2C fixture omitted {netlist_path.name}")
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
            reports[(case, run)] = i2c_pullup_checks(requirement, observed)

    control = observations[("control", "first")]
    if (
        control.components.get("RN1") is None
        or control.components["RN1"].value != "4x4.7k"
        or control.components["RN1"].footprint != "Synthetic:RA4"
        or control.component_symbols.get("RN1") != "Synthetic:ResistorArray"
        or set(control.component_pin_numbers.get("RN1", ())) != {"1", "2", "3", "4"}
        or control.nets.get("I2C_SDA") != ("RN1.1", "U1.1")
        or control.nets.get("I2C_SCL") != ("RN1.3", "U1.2")
        or control.nets.get("+3V3") != ("RN1.2", "RN1.4")
    ):
        raise ValueError(
            "Native I2C control lost its exact array identity, pins, or net assignments"
        )
    control_checks = {item.id: item for item in reports[("control", "first")]}
    if any(
        control_checks[f"i2c-pullup/array-bus/{line}"].status != "PASS" for line in ("sda", "scl")
    ):
        raise ValueError("Native mapped I2C resistor-array control did not pass both lines")

    fault = observations[("fault", "first")]
    fault_checks = {item.id: item for item in reports[("fault", "first")]}
    sda_fault = fault_checks["i2c-pullup/array-bus/sda"]
    if (
        fault.nets.get("SDA_WRONG") != ("RN1.1",)
        or sda_fault.status != "FAIL"
        or "RN1.1 is on SDA_WRONG" not in sda_fault.detail
        or fault_checks["i2c-pullup/array-bus/scl"].status != "PASS"
    ):
        raise ValueError("Native I2C array pin/net fault lost its exact line-specific failure")

    for case in fixtures:
        first_hash = normalized_hashes[(case, "first")]
        repeat_hash = normalized_hashes[(case, "repeat")]
        if first_hash != repeat_hash:
            raise ValueError(f"Native I2C {case} exports differ after typed normalization")
        checks = {item.id: item for item in reports[(case, "first")]}
        log.event(
            f"i2c-pullup-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=first_hash,
            repeat_normalized_netlist_sha256=repeat_hash,
            sda=checks["i2c-pullup/array-bus/sda"].status,
            scl=checks["i2c-pullup/array-bus/scl"].status,
            repeatable="true",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
