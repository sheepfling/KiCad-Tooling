"""Hosted native STM32 pin-map fixture lane."""

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


def stm32_pin_map_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Compare CubeMX pin-map controls and faults with repeated pinned native exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.design_lint_stm32_coverage import scan_stm32_pin_maps
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        Stm32CubeMxPinMap,
        Stm32PinExclusion,
        Stm32PinRequirement,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"STM32 pin-map fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/stm32-pin-map-native"
    )
    cases = {
        "control": ("valid.kicad_sch", "valid.ioc", ()),
        "net-drift": ("net-drift.kicad_sch", "valid.ioc", ("PA0",)),
        "signal-drift": ("valid.kicad_sch", "signal-drift.ioc", ("PA0",)),
    }
    source_hashes = {
        filename: digest(fixture_root / filename)
        for schematic, ioc, _ in cases.values()
        for filename in (schematic, ioc)
    }
    scratch = Path(
        tempfile.mkdtemp(prefix=f"stm32-pin-map-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, (schematic, ioc, _) in cases.items():
        for source in (schematic, ioc):
            destination = inputs / f"{case}-{source}"
            shutil.copyfile(fixture_root / source, destination)
            if digest(destination) != source_hashes[source]:
                raise ValueError(
                    f"Synthetic {case} STM32 fixture changed while preparing native input"
                )
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")

    source_lines = [
        'mkdir -p "$HOME"\n',
        'actual="$(kicad-cli version)"\n',
        'printf "kicad_version=%s\\n" "$actual"\n',
        f'test "$actual" = "{config.kicad_version}"\n',
    ]
    for case, (schematic, _, _) in cases.items():
        source_lines.append(
            f"for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{case}-{schematic}"; done\n'
        )
    script = "".join(source_lines)
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
        "HOME=/tmp/kicad-stm32-pin-map-fixtures",
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
        "stm32-pin-map-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "stm32-pin-map-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native STM32 pin-map fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        "stm32-pin-map-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{path}:{source_hashes[path]}" for path in sorted(source_hashes)),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    pin_map = Stm32CubeMxPinMap(
        id="synthetic-main-mcu",
        basis="Synthetic four-pin fixture package-to-symbol map",
        reference="U1",
        expected_symbol="Synthetic:STM32Fixture",
        expected_part="STM32-TOOLING-FIXTURE",
        ioc_path="firmware/controller.ioc",
        package_pins=("PA0", "PB6", "PB7", "PA13"),
        pins=(
            Stm32PinRequirement(
                port_pin="PA0",
                symbol_pin="1",
                expected_net="USER_BUTTON",
                accepted_ioc_signals=("GPIO_Input",),
                accepted_ioc_gpio_labels=("BUTTON",),
            ),
            Stm32PinRequirement(
                port_pin="PB6",
                symbol_pin="2",
                expected_net="I2C_SCL",
                accepted_ioc_signals=("I2C1_SCL",),
                accepted_ioc_gpio_labels=("SCL",),
            ),
            Stm32PinRequirement(
                port_pin="PB7",
                symbol_pin="3",
                expected_net="I2C_SDA",
                accepted_ioc_signals=("I2C1_SDA",),
                accepted_ioc_gpio_labels=("SDA",),
            ),
        ),
        exclusions=(
            Stm32PinExclusion(
                port_pin="PA13", reason="Reserved for the synthetic SWD debug interface"
            ),
        ),
    )
    policy = DesignLintPolicy(stm32_pin_maps=(pin_map,))
    project_root = scratch / "project"
    ioc_input = project_root / "firmware/controller.ioc"
    ioc_input.parent.mkdir(parents=True)

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case, (_, ioc, expected_pins) in cases.items():
        shutil.copyfile(fixture_root / ioc, ioc_input)
        if digest(ioc_input) != source_hashes[ioc]:
            raise ValueError(f"Synthetic {case} CubeMX input changed while staging native evidence")
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native STM32 fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            coverage = scan_stm32_pin_maps(project_root, policy, observed, raw_hashes[(case, run)])
            observed_pins = tuple(item.port_pin for item in coverage.mismatches)
            if coverage.status != "COMPLETE" or observed_pins != expected_pins:
                raise ValueError(
                    f"Native {case} STM32 coverage expected {expected_pins}, "
                    f"observed {observed_pins} ({coverage.status}: {coverage.issue})"
                )
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-stm32-pin-map-{case}",
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(
                coach.project_id,
                coach,
                policy,
                stm32_pin_map_coverage=coverage,
            )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native STM32 exports differ after normalization to parsed netlist contracts"
        )
    for case, (_, ioc, expected_pins) in cases.items():
        report = reports[(case, "first")]
        rule_findings = tuple(
            item for item in report.findings if item.rule_id == "mcu.stm32_cubemx_pin_map"
        )
        if len(rule_findings) != len(expected_pins):
            raise ValueError(
                f"Native {case} STM32 pin-map findings differ from expected pins {expected_pins}"
            )
        if expected_pins and report.status != "REVIEW":
            raise ValueError(f"Native {case} STM32 pin-map drift did not produce REVIEW")
        if not expected_pins and rule_findings:
            raise ValueError("Native STM32 pin-map control produced an unexpected finding")
        log.event(
            f"stm32-pin-map-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[cases[case][0]],
            ioc_sha256=source_hashes[ioc],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=report.status,
            mismatch_pins=",".join(expected_pins) or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(fixture_root / source) != source_hashes[source]
        or digest(inputs / f"{case}-{source}") != source_hashes[source]
        for case, (schematic, ioc, _) in cases.items()
        for source in (schematic, ioc)
    ):
        raise ValueError("Synthetic STM32 fixture source changed during native export")
