"""Open-drain bias fixture analysis and native acceptance."""

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


def open_drain_bias_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify open-output bias candidates from repeated pinned native exports."""
    import hashlib

    from .ci_hosted import read_kicad_erc_report
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintFinding,
        DesignLintPolicy,
        NetlistContract,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Open-output bias fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/open-drain-native"
    )
    cases = {
        "collector-control": (
            "open_collector",
            "pull-up to a recognized positive rail",
            "+3V3",
            False,
        ),
        "collector-fault": (
            "open_collector",
            "pull-up to a recognized positive rail",
            "+3V3",
            True,
        ),
        "emitter-control": ("open_emitter", "pull-down to a recognized return", "GND", False),
        "emitter-fault": ("open_emitter", "pull-down to a recognized return", "GND", True),
    }
    source_hashes = {case: digest(fixture_root / f"{case}.kicad_sch") for case in cases}
    expected_source_hashes = {
        "collector-control": "bdb0b34256ef9bac90b7fba687abe5998400c29da2f2467cd1a43e8b1029c177",
        "collector-fault": "bb4d7075d2892bf2991a3b840ba1db956cdf6a2f6caba1538ef1381c0d937714",
        "emitter-control": "3f2bcdb733865867bef38ba1fe790518e8aa35225e04117220dcac07e53645f0",
        "emitter-fault": "b987e6f281edc13de3587614cb3bb19ed80bfeeaccde783dcf1492ef598826e1",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("Open-output bias fixture sources differ from their reviewed hashes")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"open-drain-bias-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case in cases:
        fixture = fixture_root / f"{case}.kicad_sch"
        shutil.copyfile(fixture, inputs / fixture.name)
        if digest(inputs / fixture.name) != source_hashes[case]:
            raise ValueError(f"Synthetic {case} fixture changed while preparing native input")
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
        f"for case in {' '.join(cases)}; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
        '      "/fixtures/${case}.kicad_sch"\n'
        "    kicad-cli sch erc --format json --severity-all "
        '      --output "/output/${case}.${run}.erc.json" '
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
        "HOME=/tmp/kicad-open-drain-fixtures",
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
        "open-drain-bias-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "open-drain-bias-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native open-output bias fixture command failed: {command.stderr or command.error}"
        )

    for case, (output_type, bias_description, rail, is_fault) in cases.items():
        is_emitter = output_type == "open_emitter"
        observations: dict[str, NetlistContract] = {}
        normalized_netlist_hashes: dict[str, str] = {}
        normalized_erc_hashes: dict[str, str] = {}
        erc_warning_types: dict[str, tuple[str, ...]] = {}
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native open-output {case} export omitted an expected report")
            observed = read_netlist(netlist_path)
            observations[run] = observed
            normalized_netlist = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_netlist_hashes[run] = hashlib.sha256(normalized_netlist).hexdigest()

            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native open-output {case} ERC report version differs from KiCad "
                    f"{config.kicad_version}"
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
                                detail,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            ),
                        )
                    ),
                )
                for item in erc.violations
            ]
            erc_rows.sort(
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
            normalized_erc = json.dumps(
                {"kicad_version": erc.kicad_version, "violations": erc_rows},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[run] = hashlib.sha256(normalized_erc).hexdigest()
            erc_errors = tuple(
                sorted(item.type for item in erc.violations if item.severity == "error")
            )
            if erc_errors:
                raise ValueError(
                    f"Native open-output {case} has unexpected ERC errors: {erc_errors}"
                )
            erc_warning_types[run] = tuple(
                sorted({item.type for item in erc.violations if item.severity == "warning"})
            )

        if normalized_netlist_hashes["first"] != normalized_netlist_hashes["repeat"]:
            raise ValueError(f"Native open-output {case} netlists are not repeatable")
        if normalized_erc_hashes["first"] != normalized_erc_hashes["repeat"]:
            raise ValueError(f"Native open-output {case} ERC reports are not repeatable")
        observed = observations["first"]
        expected_types = {"U2.1": output_type, "U1.2": "input"}
        if any(
            observed.pin_electrical_types.get(pin) != value for pin, value in expected_types.items()
        ):
            raise ValueError(f"Native open-output {case} lost exact native pin electrical types")
        expected_functions = {"U2.1": "OPEN_OUTPUT", "U1.2": "INPUT_PEER"}
        if any(
            observed.pin_functions.get(pin) != value for pin, value in expected_functions.items()
        ):
            raise ValueError(f"Native open-output {case} lost exact pin functions")
        expected_nets = {"ALERT_N": {"U2.1", "U1.2", "R1.1"}, rail: {"R1.2"}}
        actual_nets = {net: set(observed.nets.get(net, ())) for net in expected_nets}
        if actual_nets != expected_nets:
            raise ValueError(
                f"Native open-output {case} net assignments differ: "
                f"expected {expected_nets}, observed {actual_nets}"
            )
        expected_dnp = ("R1",) if is_fault else ()
        if observed.dnp_components != expected_dnp:
            raise ValueError(f"Native open-output {case} changed DNP resistor evidence")
        if observed.component_pin_numbers.get("R1") != ("1", "2"):
            raise ValueError(f"Native open-output {case} lost the complete resistor pin inventory")
        expected_erc_warning_types = {
            "footprint_link_issues",
            "isolated_pin_label",
            "lib_symbol_issues",
        }
        for run, warning_types in erc_warning_types.items():
            if set(warning_types) != expected_erc_warning_types:
                raise ValueError(
                    f"Native open-output {case} has unexpected ERC warning types in {run}: "
                    f"{warning_types}"
                )

        report = evaluate(
            f"synthetic-open-output-{case}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-open-output-{case}",
                observed=observed,
                netlist_sha256=digest(output / f"{case}.first.netlist.xml"),
            ),
            DesignLintPolicy(),
        )
        matching = tuple(
            item
            for item in report.findings
            if item.rule_id
            == (
                "signal.open_emitter_input_without_visible_bias"
                if is_emitter
                else "signal.open_collector_input_without_visible_bias"
            )
        )
        independent_peer_input = tuple(
            item
            for item in report.findings
            if item.rule_id == "component.peer_signal_input_unconnected"
        )
        peer_input_coverage = next(
            item
            for item in report.component_peer_pin_coverage
            if item.rule_id == "component.peer_signal_input_unconnected"
        )
        expected_bias_status = "REVIEW" if is_fault else "PASS"
        expected_evidence = {
            "net": ("ALERT_N",),
            "expected_bias": (bias_description,),
            "open_output_pins": ("U2.1",),
            "input_pins": ("U1.2",),
            "visible_resistors_on_signal_net": (),
        }
        expected_rule_ids = {"component.peer_signal_input_unconnected"}
        if is_fault:
            expected_rule_ids.add(
                "signal.open_emitter_input_without_visible_bias"
                if is_emitter
                else "signal.open_collector_input_without_visible_bias"
            )
        if (
            report.status != "REVIEW"
            or {item.rule_id for item in report.findings} != expected_rule_ids
            or len(matching) != (1 if is_fault else 0)
            or (is_fault and matching[0].mode != "review")
            or (is_fault and dict(matching[0].evidence) != expected_evidence)
            or len(independent_peer_input) != 1
            or independent_peer_input[0].evidence.get("unassigned_pins") != ("U2.2",)
            or peer_input_coverage.status != "EVALUATED"
            or peer_input_coverage.netlist_sha256 != report.netlist_sha256
            or peer_input_coverage.candidate_group_count != 1
            or peer_input_coverage.finding_count != 1
            or peer_input_coverage.suppressed_candidate_count != 0
        ):
            raise ValueError(f"Native open-output {case} no longer matches its lint control/fault")
        repeated = evaluate(
            f"synthetic-open-output-{case}",
            ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-open-output-{case}",
                observed=observations["repeat"],
                netlist_sha256=digest(output / f"{case}.repeat.netlist.xml"),
            ),
            DesignLintPolicy(),
        )

        def finding_key(finding: DesignLintFinding) -> tuple[object, ...]:
            return finding.fingerprint, finding.rule_id, finding.mode, finding.evidence

        if tuple(map(finding_key, report.findings)) != tuple(map(finding_key, repeated.findings)):
            raise ValueError(f"Native open-output {case} lint report is not repeatable")

        log.event(
            f"open-drain-bias-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=digest(output / f"{case}.first.netlist.xml"),
            normalized_netlist_sha256=normalized_netlist_hashes["first"],
            repeat_normalized_netlist_sha256=normalized_netlist_hashes["repeat"],
            normalized_erc_sha256=normalized_erc_hashes["first"],
            repeat_normalized_erc_sha256=normalized_erc_hashes["repeat"],
            lint_status=report.status,
            findings=";".join(item.rule_id for item in report.findings) or "none",
            bias_rule_status=expected_bias_status,
            bias_findings=";".join(item.rule_id for item in matching) or "none",
            peer_input_coverage_status=peer_input_coverage.status,
            peer_input_coverage_netlist_sha256=peer_input_coverage.netlist_sha256,
            peer_input_coverage_candidate_count=peer_input_coverage.candidate_group_count,
            peer_input_coverage_finding_count=peer_input_coverage.finding_count,
            expected_bias=bias_description,
            bias_rail=rail,
            open_output_type=output_type,
            input_type="input",
            open_output_pin="U2.1",
            input_pin="U1.2",
            signal_net="ALERT_N",
            net_assignments=";".join(
                f"{net}={','.join(sorted(pins, key=str.casefold))}"
                for net, pins in sorted(expected_nets.items())
            ),
            dnp_resistor="R1" if is_fault else "none",
            erc_errors="0",
            erc_warning_types=";".join(erc_warning_types["first"]) or "none",
            repeatable="true",
            repeatability_basis="normalized_native_netlist_erc_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "open-drain-bias-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
