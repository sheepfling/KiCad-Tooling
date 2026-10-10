"""Hosted native CAN termination fixture lane."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def can_termination_native_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Exercise split CAN termination requirements from pinned native exports."""
    import hashlib
    import json
    import os

    from .hwrepo.can_termination_contract import (
        can_termination_checks,
    )
    from .hwrepo.can_termination_models import (
        CanTerminationAnalysis,
        CanTerminationBusRequirement,
        CanTerminationEndpointRequirement,
        CanTerminationMidpointCapacitorRequirement,
        CanTerminationResistorRequirement,
    )
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ElectricalCheck, NetlistContract
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"CAN termination fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/can-split-midpoint-native"
    )
    fixtures = {case: fixture_root / f"{case}.kicad_sch" for case in ("control", "fault")}
    source_hashes = {case: digest(path) for case, path in fixtures.items()}
    expected_source_hashes = {
        "control": "f69f9084482ce5455740c4ac33628fd226e5243650acd9a2e022984aec830726",
        "fault": "0c84ea82f7ff60be1d8a1ea6f2815fe9e6593ad1e8ae192f362c02af73bb8db6",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("CAN termination fixture sources differ from the reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"native-can-termination-{project}-", dir=log.directory.resolve())
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
        "HOME=/tmp/kicad-can-termination-fixtures",
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
        "can-termination-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "can-termination-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native CAN termination export failed: {command.stderr or command.error}")
    log.event(
        "can-termination-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in fixtures),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    requirement = CanTerminationAnalysis(
        basis="Synthetic reviewed split CAN topology with mapped midpoint capacitor",
        buses=(
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Synthetic controller CAN interface",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=("U1.1",),
                low_pins=("U1.2",),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="local",
                        basis="Synthetic split termination at a local endpoint",
                        topology="split",
                        midpoint_net="CAN_TERM_MID",
                        resistors=(
                            CanTerminationResistorRequirement(
                                reference="R4",
                                first_net="CAN_H",
                                second_net="CAN_TERM_MID",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                            CanTerminationResistorRequirement(
                                reference="R5",
                                first_net="CAN_L",
                                second_net="CAN_TERM_MID",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                        ),
                        midpoint_capacitor=CanTerminationMidpointCapacitorRequirement(
                            reference="C1",
                            expected_symbol="Synthetic:CanMidpointCapacitor",
                            expected_footprint="Synthetic:CAP",
                            midpoint_pin="C1.1",
                            reference_pin="C1.2",
                            reference_net="GND",
                            minimum_nominal_capacitance_pf=90,
                            maximum_nominal_capacitance_pf=110,
                        ),
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
            raise ValueError("Synthetic CAN termination fixture changed during native export")
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native CAN termination fixture omitted {netlist_path.name}")
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
            reports[(case, run)] = can_termination_checks(requirement, observed)

    control = observations[("control", "first")]
    if (
        control.components.get("R4") is None
        or control.components["R4"].value != "60R"
        or control.components["R4"].footprint != "Synthetic:R_0603"
        or control.components.get("R5") is None
        or control.components["R5"].value != "60R"
        or control.components["R5"].footprint != "Synthetic:R_0603"
        or control.component_symbols.get("R4") != "Device:R"
        or control.component_symbols.get("R5") != "Device:R"
        or set(control.component_pin_numbers.get("R4", ())) != {"1", "2"}
        or set(control.component_pin_numbers.get("R5", ())) != {"1", "2"}
        or control.components.get("C1") is None
        or control.components["C1"].value != "100pF"
        or control.components["C1"].footprint != "Synthetic:CAP"
        or control.component_symbols.get("C1") != "Synthetic:CanMidpointCapacitor"
        or set(control.component_pin_numbers.get("C1", ())) != {"1", "2"}
        or set(control.nets.get("CAN_H", ())) != {"R4.1", "U1.1"}
        or set(control.nets.get("CAN_L", ())) != {"R5.1", "U1.2"}
        or control.pin_functions.get("U1.1") != "CANH"
        or control.pin_functions.get("U1.2") != "CANL"
        or set(control.nets.get("CAN_TERM_MID", ())) != {"C1.1", "R4.2", "R5.2"}
        or tuple(control.nets.get("GND", ())) != ("C1.2",)
    ):
        raise ValueError(
            "Native CAN control lost its exact component identity, pins, or net assignments"
        )

    expected_check_ids = {
        "can-termination/fieldbus/signal-pins",
        "can-termination/fieldbus/unlisted-direct",
        "can-termination/fieldbus/local",
        "can-termination/fieldbus/local/midpoint-capacitor",
    }
    control_checks = {item.id: item for item in reports[("control", "first")]}
    if set(control_checks) != expected_check_ids or any(
        item.status != "PASS" for item in control_checks.values()
    ):
        raise ValueError("Native split CAN termination control did not pass every declared check")

    fault = observations[("fault", "first")]
    fault_checks = {item.id: item for item in reports[("fault", "first")]}
    capacitor_id = "can-termination/fieldbus/local/midpoint-capacitor"
    capacitor_check = fault_checks.get(capacitor_id)
    if (
        set(fault_checks) != expected_check_ids
        or fault.nets.get("GND_ALT") != ("C1.2",)
        or capacitor_check is None
        or capacitor_check.status != "FAIL"
        or "C1.2 is assigned to GND_ALT; expected only GND" not in capacitor_check.detail
        or any(
            fault_checks[check_id].status != "PASS"
            for check_id in expected_check_ids - {capacitor_id}
        )
    ):
        raise ValueError("Native CAN midpoint-reference fault lost its exact isolated failure")

    for case in fixtures:
        first_hash = normalized_hashes[(case, "first")]
        repeat_hash = normalized_hashes[(case, "repeat")]
        if first_hash != repeat_hash:
            raise ValueError(f"Native CAN {case} exports differ after typed normalization")
        checks = {item.id: item for item in reports[(case, "first")]}
        log.event(
            f"can-termination-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=first_hash,
            repeat_normalized_netlist_sha256=repeat_hash,
            signal_pins=checks["can-termination/fieldbus/signal-pins"].status,
            unlisted_direct=checks["can-termination/fieldbus/unlisted-direct"].status,
            split_path=checks["can-termination/fieldbus/local"].status,
            midpoint_capacitor=checks[capacitor_id].status,
            repeatable="true",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
