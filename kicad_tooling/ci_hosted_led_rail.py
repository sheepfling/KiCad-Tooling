"""Hosted native LED rail fixture lane."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def led_rail_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Check native direct-rail and output-driven LED topology fixtures."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.led_heuristics import (
        leds_directly_between_positive_and_return_nets,
        leds_directly_driven_without_visible_series_resistor,
    )
    from .hwrepo.models import (
        ComponentRoleBinding,
        ComponentRoleMap,
        ComponentRolePin,
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"LED rail fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/cohort-led-resistor"
    )
    cases = {
        "direct-rails": "fault-direct-across-rails.kicad_sch",
        "series-control": "control-series-resistor.kicad_sch",
        "parallel-resistor": "fault-parallel-resistor.kicad_sch",
        "direct-output": "fault-direct-output.kicad_sch",
        "series-return-control": "control-output-series-return-resistor.kicad_sch",
        "parallel-output-resistor": "fault-output-parallel-resistor.kicad_sch",
        "custom-direct-output": "fault-custom-direct-output.kicad_sch",
        "custom-series-return-control": "control-custom-output-series-return-resistor.kicad_sch",
    }
    source_hashes = {case: digest(fixture_root / name) for case, name in cases.items()}
    scratch = Path(tempfile.mkdtemp(prefix=f"led-rail-{project}-", dir=log.directory.resolve()))
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
    for case, filename in cases.items():
        export_command = (
            f"for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{filename}"; done\n'
        )
        source_lines.append(export_command)
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
        "HOME=/tmp/kicad-led-fixtures",
        "-v",
        f"{fixture_root.resolve()}:/fixtures:ro",
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
        "led-rail-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "led-rail-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native LED fixture command failed: {command.stderr or command.error}")
    log.event(
        "led-rail-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    expected_findings: dict[str, set[str]] = {
        "direct-rails": {"D1: LED directly spans supply and return"},
        "series-control": set(),
        "parallel-resistor": {"D1: LED directly spans supply and return"},
        "direct-output": set(),
        "series-return-control": set(),
        "parallel-output-resistor": set(),
        "custom-direct-output": set(),
        "custom-series-return-control": set(),
    }
    expected_output_findings: dict[str, set[str]] = {
        "direct-rails": set(),
        "series-control": set(),
        "parallel-resistor": set(),
        "direct-output": {"D1: LED directly shares an output net and a rail"},
        "series-return-control": set(),
        "parallel-output-resistor": {"D1: LED directly shares an output net and a rail"},
        "custom-direct-output": set(),
        "custom-series-return-control": set(),
    }
    expected_mapped_output_findings: dict[str, set[str]] = {
        "custom-direct-output": {"D1: LED directly shares an output net and a rail"},
        "custom-series-return-control": set(),
    }
    custom_led_role_map = ComponentRoleMap(
        entries=(
            ComponentRoleBinding(
                part_id="training-led",
                symbol="Training:LED_5mm",
                footprint="Training:LED_0603",
                role="led",
                pins=(
                    ComponentRolePin(number="1", function="A", electrical_type="passive"),
                    ComponentRolePin(number="2", function="K", electrical_type="passive"),
                ),
                basis="Synthetic native fixture reviewed its exact custom LED symbol identity",
            ),
        )
    )
    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native LED fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if case == "parallel-output-resistor":
                native_nets = tuple(set(pins) for pins in observed.nets.values())
                if not any({"U1.1", "D1.1", "R1.1"} <= pins for pins in native_nets) or not any(
                    {"D1.2", "R1.2"} <= pins for pins in native_nets
                ):
                    raise ValueError(
                        "Native parallel-output-resistor fixture does not place R1 across "
                        "the LED's output and return nets"
                    )
            if case.startswith("custom-") and (
                observed.components.get("D1") is None
                or observed.components["D1"].part_id != "training-led"
                or observed.components["D1"].footprint != "Training:LED_0603"
                or observed.component_symbols.get("D1") != "Training:LED_5mm"
                or observed.component_pin_numbers.get("D1") != ("1", "2")
                or observed.pin_functions.get("D1.1") != "A"
                or observed.pin_functions.get("D1.2") != "K"
                or observed.pin_electrical_types.get("D1.1") != "passive"
                or observed.pin_electrical_types.get("D1.2") != "passive"
            ):
                raise ValueError(
                    "Native custom LED export changed its PART_ID, symbol, footprint, "
                    "or complete pin signature"
                )
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            bridges = leds_directly_between_positive_and_return_nets(observed)
            observed_bridges = {
                f"{item.reference}: LED directly spans supply and return" for item in bridges
            }
            if observed_bridges != expected_findings[case]:
                raise ValueError(
                    f"Native {case} LED topology differs from the fixture expectation: "
                    f"{sorted(observed_bridges)}"
                )
            output_driven = leds_directly_driven_without_visible_series_resistor(observed)
            observed_output_findings = {
                f"{item.reference}: LED directly shares an output net and a rail"
                for item in output_driven
            }
            if observed_output_findings != expected_output_findings[case]:
                raise ValueError(
                    f"Native {case} output-driven LED topology differs from the fixture "
                    f"expectation: {sorted(observed_output_findings)}"
                )
            policy = (
                DesignLintPolicy(component_role_map=custom_led_role_map)
                if case.startswith("custom-")
                else DesignLintPolicy()
            )
            mapped_output = leds_directly_driven_without_visible_series_resistor(
                observed, policy.component_role_map
            )
            mapped_output_findings = {
                f"{item.reference}: LED directly shares an output net and a rail"
                for item in mapped_output
            }
            expected_mapped = expected_mapped_output_findings.get(
                case, expected_output_findings[case]
            )
            if mapped_output_findings != expected_mapped:
                raise ValueError(
                    f"Native {case} project-role LED result differs from its fixture "
                    f"expectation: {sorted(mapped_output_findings)}"
                )
            project_id = f"synthetic-led-rail-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, policy)

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native LED exports differ after normalization to parsed netlist contracts"
        )
    for case in cases:
        findings = {
            item.subject
            for item in reports[(case, "first")].findings
            if item.rule_id == "component.led_directly_across_supply_and_return"
        }
        if findings != expected_findings[case]:
            raise ValueError(
                f"Native {case} lint result differs from its LED expectation: {sorted(findings)}"
            )
        output_findings = {
            item.subject
            for item in reports[(case, "first")].findings
            if item.rule_id == "component.led_directly_driven_from_output"
        }
        expected_report_output_findings = expected_mapped_output_findings.get(
            case, expected_output_findings[case]
        )
        if output_findings != expected_report_output_findings:
            raise ValueError(
                f"Native {case} lint result differs from its output-driven LED expectation: "
                f"{sorted(output_findings)}"
            )
        log.event(
            f"led-rail-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=reports[(case, "first")].status,
            led_rule_findings=";".join(sorted(findings)) or "none",
            led_output_rule_findings=";".join(sorted(output_findings)) or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(fixture_root / filename) != source_hashes[case] for case, filename in cases.items()
    ):
        raise ValueError("Synthetic LED fixture source changed during native export")
