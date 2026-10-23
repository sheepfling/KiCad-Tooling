"""Hosted native I2C pull-up fixture lane."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import read_model, write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


def i2c_pullup_native_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Exercise mapped I2C resistor-array requirements from pinned native exports."""
    import hashlib

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.i2c_pullup_contract import i2c_pullup_checks
    from .hwrepo.i2c_pullup_heuristics import i2c_pullup_heuristic_coverage
    from .hwrepo.i2c_pullup_models import I2cPullupAnalysis
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        ElectricalCheck,
        NetlistContract,
    )
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
        "control": "46fbdf1453e8254a633b7dee43b8877fc516758446314f4834f55a41db2a2479",
        "fault": "c4ec4dbb38f9a076d3f8969fd77b9f2f869648c1ca490f1c973e4b92ba16f595",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("I2C pull-up fixture sources differ from the reviewed hashes")

    contract_fixture = fixture_root / "pullups.json"
    expected_contract_sha256 = "38c97126ac75bb0dadf2153decdbcfa2f78101532d401920db54712bb204f5b2"
    if digest(contract_fixture) != expected_contract_sha256:
        raise ValueError("I2C pull-up requirement fixture differs from the reviewed hash")
    project_contract = root / "projects/synthetic-i2c-array/electrical.json"
    project_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(contract_fixture, project_contract)
    contract_sha256 = digest(project_contract)
    if contract_sha256 != expected_contract_sha256:
        raise ValueError("I2C pull-up requirement changed while preparing the native fixture")
    contract_path = project_contract.relative_to(root).as_posix()
    requirement = read_model(project_contract, I2cPullupAnalysis)

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
        or set(control.nets.get("I2C_SDA", ())) != {"RN1.1", "U1.1", "X1.1"}
        or control.nets.get("I2C_SCL") != ("RN1.3", "U1.2")
        or control.nets.get("+3V3") != ("RN1.2", "RN1.4")
    ):
        raise ValueError(
            "Native I2C control lost its exact array identity, pins, or net assignments"
        )
    capacitor = control.components.get("X1")
    if (
        capacitor is None
        or capacitor.value != "10p"
        or capacitor.footprint != "Synthetic:0603"
        or control.component_symbols.get("X1") != "Device:C"
        or set(control.component_pin_numbers.get("X1", ())) != {"1", "2"}
        or "X1.1" not in control.nets.get("I2C_SDA", ())
        or control.nets.get("GND") != ("X1.2",)
    ):
        raise ValueError("Native I2C control lost its explicitly mapped X1 capacitance evidence")
    fault = observations[("fault", "first")]
    extra_capacitor = fault.components.get("X2")
    if (
        extra_capacitor is None
        or extra_capacitor.value != "4p"
        or extra_capacitor.footprint != "Synthetic:0603"
        or fault.component_symbols.get("X2") != "Device:C"
        or set(fault.component_pin_numbers.get("X2", ())) != {"1", "2"}
        or "X2.1" not in fault.nets.get("I2C_SDA", ())
        or "X2.2" not in fault.nets.get("GND", ())
    ):
        raise ValueError("Native I2C fault lost its unmapped non-C capacitor evidence")
    control_checks = {item.id: item for item in reports[("control", "first")]}
    if any(
        control_checks[f"i2c-pullup/array-bus/{line}"].status != "PASS" for line in ("sda", "scl")
    ):
        raise ValueError("Native mapped I2C resistor-array control did not pass both lines")
    if any(
        control_checks[f"i2c-pullup/array-bus/{line}/electrical-window/tolerance-scope"].status
        != "PASS"
        for line in ("sda", "scl")
    ):
        raise ValueError("Native mapped I2C tolerance scope did not cover every array channel")
    if any(
        control_checks[f"i2c-pullup/array-bus/{line}/electrical-window/capacitance-scope"].status
        != "PASS"
        for line in ("sda", "scl")
    ):
        raise ValueError("Native mapped I2C capacitance scope did not pass")

    fault_checks = {item.id: item for item in reports[("fault", "first")]}
    sda_fault = fault_checks["i2c-pullup/array-bus/sda"]
    if (
        fault.nets.get("SDA_WRONG") != ("RN1.1",)
        or sda_fault.status != "FAIL"
        or "RN1.1 is on SDA_WRONG" not in sda_fault.detail
        or fault_checks["i2c-pullup/array-bus/scl"].status != "PASS"
    ):
        raise ValueError("Native I2C array pin/net fault lost its exact line-specific failure")
    if any(
        fault_checks[f"i2c-pullup/array-bus/{line}/electrical-window/tolerance-scope"].status
        != "PASS"
        for line in ("sda", "scl")
    ):
        raise ValueError("Native pin/net fault unexpectedly changed authored tolerance coverage")
    fault_capacitance = fault_checks["i2c-pullup/array-bus/sda/electrical-window/capacitance-scope"]
    if (
        fault_capacitance.status != "FAIL"
        or "unmapped fitted capacitors on I2C_SDA: X2" not in fault_capacitance.detail
        or fault_checks["i2c-pullup/array-bus/scl/electrical-window/capacitance-scope"].status
        != "PASS"
    ):
        raise ValueError("Native I2C fault did not discover its unmapped X2 capacitor")

    for case in fixtures:
        first_hash = normalized_hashes[(case, "first")]
        repeat_hash = normalized_hashes[(case, "repeat")]
        if first_hash != repeat_hash:
            raise ValueError(f"Native I2C {case} exports differ after typed normalization")
        checks = {item.id: item for item in reports[(case, "first")]}
        observed = observations[(case, "first")]
        netlist_sha256 = raw_hashes[(case, "first")]
        coach = ContractCoachReport(
            status="READY_FOR_REVIEW",
            project_id=f"synthetic-i2c-array-{case}",
            observed=observed,
            netlist_sha256=netlist_sha256,
        )
        baseline = evaluate(coach.project_id, coach, DesignLintPolicy())
        baseline_has_hint = any(
            item.rule_id == "bus.i2c_missing_pullup" for item in baseline.findings
        )
        coverage = i2c_pullup_heuristic_coverage(
            observed,
            netlist_sha256=netlist_sha256,
            source_path=contract_path,
            source_sha256=contract_sha256,
            state="required",
            spec=requirement,
        )
        lint_report = evaluate(
            coach.project_id,
            coach,
            DesignLintPolicy(),
            i2c_pullup_heuristic_coverage=coverage,
        )
        lint_rule_findings = tuple(
            sorted(
                {
                    item.rule_id
                    for item in lint_report.findings
                    if item.rule_id == "bus.i2c_missing_pullup"
                }
            )
        )
        expected_coverage = "COMPLETE" if case == "control" else "OPEN"
        expected_rule_findings = () if case == "control" else ("bus.i2c_missing_pullup",)
        if (
            not baseline_has_hint
            or coverage.status != expected_coverage
            or lint_rule_findings != expected_rule_findings
        ):
            raise ValueError(
                f"Native I2C {case} heuristic/contract result differs from its reviewed expectation"
            )
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
            contract_path=contract_path,
            contract_sha256=contract_sha256,
            baseline_missing_pullup="OPEN" if baseline_has_hint else "QUIET",
            heuristic_coverage=coverage.status,
            heuristic_findings=",".join(lint_rule_findings) or "none",
            sda=checks["i2c-pullup/array-bus/sda"].status,
            scl=checks["i2c-pullup/array-bus/scl"].status,
            sda_tolerance_scope=checks[
                "i2c-pullup/array-bus/sda/electrical-window/tolerance-scope"
            ].status,
            scl_tolerance_scope=checks[
                "i2c-pullup/array-bus/scl/electrical-window/tolerance-scope"
            ].status,
            sda_capacitance_scope=checks[
                "i2c-pullup/array-bus/sda/electrical-window/capacitance-scope"
            ].status,
            sda_capacitance_contributors="X1",
            sda_capacitance_unmapped="X2" if case == "fault" else "none",
            scl_capacitance_scope=checks[
                "i2c-pullup/array-bus/scl/electrical-window/capacitance-scope"
            ].status,
            repeatable="true",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
