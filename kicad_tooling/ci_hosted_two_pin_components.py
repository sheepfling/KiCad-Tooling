"""Hosted native two-pin component fixture lane."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


TWO_PIN_COMPONENT_FIXTURE_CASES: dict[str, tuple[str, str, set[str]]] = {
    "same-net-passive": (
        "two-pin-components/same-net.kicad_sch",
        "component.two_pin_passive_same_net",
        {"R1 (10k resistor) has both pins on one net"},
    ),
    "distinct-nets-passive": (
        "two-pin-components/distinct-nets.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-varistor": (
        "two-pin-varistors/same-net-varistor.kicad_sch",
        "component.two_pin_passive_same_net",
        {"RV1 (230V MOV varistor) has both pins on one net"},
    ),
    "distinct-nets-varistor": (
        "two-pin-varistors/distinct-nets-varistor.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-thermistor": (
        "two-pin-thermistors/same-net-thermistor.kicad_sch",
        "component.two_pin_passive_same_net",
        {"TH1 (10k NTC thermistor) has both pins on one net"},
    ),
    "distinct-nets-thermistor": (
        "two-pin-thermistors/distinct-nets-thermistor.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-thermistor-ptc": (
        "two-pin-thermistors/same-net-thermistor-ptc.kicad_sch",
        "component.two_pin_passive_same_net",
        {"TH1 (10k PTC thermistor) has both pins on one net"},
    ),
    "distinct-nets-thermistor-ptc": (
        "two-pin-thermistors/distinct-nets-thermistor-ptc.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-thermistor-us": (
        "two-pin-thermistors/same-net-thermistor-us.kicad_sch",
        "component.two_pin_passive_same_net",
        {"TH1 (10k US thermistor) has both pins on one net"},
    ),
    "distinct-nets-thermistor-us": (
        "two-pin-thermistors/distinct-nets-thermistor-us.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-thermistor-ntc-us": (
        "two-pin-thermistors/same-net-thermistor-ntc-us.kicad_sch",
        "component.two_pin_passive_same_net",
        {"TH1 (10k NTC US thermistor) has both pins on one net"},
    ),
    "distinct-nets-thermistor-ntc-us": (
        "two-pin-thermistors/distinct-nets-thermistor-ntc-us.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-thermistor-ptc-us": (
        "two-pin-thermistors/same-net-thermistor-ptc-us.kicad_sch",
        "component.two_pin_passive_same_net",
        {"TH1 (10k PTC US thermistor) has both pins on one net"},
    ),
    "distinct-nets-thermistor-ptc-us": (
        "two-pin-thermistors/distinct-nets-thermistor-ptc-us.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-mapped-capacitor": (
        "two-pin-components/custom-capacitor-same-net.kicad_sch",
        "component.two_pin_passive_same_net",
        {"C1 (100nF capacitor) has both pins on one net"},
    ),
    "distinct-nets-mapped-capacitor": (
        "cohort-power-pin-dc/custom-capacitor-role-control.kicad_sch",
        "component.two_pin_passive_same_net",
        set(),
    ),
    "same-net-diode": (
        "two-pin-components/same-net-diode.kicad_sch",
        "component.two_pin_diode_same_net",
        {"D1 (1N4148 diode) has both pins on one net"},
    ),
    "distinct-nets-diode": (
        "two-pin-components/distinct-nets-diode.kicad_sch",
        "component.two_pin_diode_same_net",
        set(),
    ),
    "same-net-led": (
        "two-pin-leds/same-net-led.kicad_sch",
        "component.two_pin_led_same_net",
        {"D1: both LED terminals share LED_TIED"},
    ),
    "distinct-nets-led": (
        "two-pin-leds/distinct-nets-led.kicad_sch",
        "component.two_pin_led_same_net",
        set(),
    ),
    "same-net-buzzer": (
        "two-pin-buzzers/same-net-buzzer.kicad_sch",
        "component.two_pin_buzzer_same_net",
        {"BZ1: both buzzer terminals share BUZZER_TIED"},
    ),
    "distinct-nets-buzzer": (
        "two-pin-buzzers/distinct-nets-buzzer.kicad_sch",
        "component.two_pin_buzzer_same_net",
        set(),
    ),
    "same-net-speaker": (
        "two-pin-speakers/same-net-speaker.kicad_sch",
        "component.two_pin_speaker_same_net",
        {"LS1: both speaker terminals share SPEAKER_TIED"},
    ),
    "distinct-nets-speaker": (
        "two-pin-speakers/distinct-nets-speaker.kicad_sch",
        "component.two_pin_speaker_same_net",
        set(),
    ),
    "same-net-battery": (
        "two-pin-batteries/same-net-battery.kicad_sch",
        "component.two_pin_battery_same_net",
        {"BT1: both battery terminals share BATTERY_TIED"},
    ),
    "distinct-nets-battery": (
        "two-pin-batteries/distinct-nets-battery.kicad_sch",
        "component.two_pin_battery_same_net",
        set(),
    ),
    "same-net-motor": (
        "two-pin-motors/same-net-motor.kicad_sch",
        "component.two_pin_motor_same_net",
        {"M1: both motor terminals share MOTOR_TIED"},
    ),
    "distinct-nets-motor": (
        "two-pin-motors/distinct-nets-motor.kicad_sch",
        "component.two_pin_motor_same_net",
        set(),
    ),
    "same-net-solar-cell": (
        "two-pin-solar-cells/same-net-solar-cell.kicad_sch",
        "component.two_pin_solar_cell_same_net",
        {"BT1: both solar-cell terminals share SOLAR_CELL_TIED"},
    ),
    "distinct-nets-solar-cell": (
        "two-pin-solar-cells/distinct-nets-solar-cell.kicad_sch",
        "component.two_pin_solar_cell_same_net",
        set(),
    ),
    "same-net-thermocouples": (
        "two-pin-thermocouples/same-net-thermocouples.kicad_sch",
        "component.two_pin_thermocouple_same_net",
        {
            "TC1: both thermocouple leads share TC1_TIED",
            "TC2: both thermocouple leads share TC2_TIED",
            "TC3: both thermocouple leads share TC3_TIED",
        },
    ),
    "distinct-nets-thermocouples": (
        "two-pin-thermocouples/distinct-nets-thermocouples.kicad_sch",
        "component.two_pin_thermocouple_same_net",
        set(),
    ),
    "same-net-crystal": (
        "two-pin-crystals/same-net-crystal.kicad_sch",
        "component.two_pin_crystal_same_net",
        {"Y1 (16 MHz crystal) has both pins on one net"},
    ),
    "distinct-nets-crystal": (
        "two-pin-crystals/distinct-nets-crystal.kicad_sch",
        "component.two_pin_crystal_same_net",
        set(),
    ),
    "same-net-fuse": (
        "two-pin-fuses/same-net-fuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        {"F1 (1A fuse) has both pins on one net"},
    ),
    "distinct-nets-fuse": (
        "two-pin-fuses/distinct-nets-fuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        set(),
    ),
    "same-net-polyfuse": (
        "two-pin-fuses/same-net-polyfuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        {"F1 (1A polyfuse) has both pins on one net"},
    ),
    "distinct-nets-polyfuse": (
        "two-pin-fuses/distinct-nets-polyfuse.kicad_sch",
        "component.two_pin_fuse_same_net",
        set(),
    ),
    "same-net-ferrite": (
        "two-pin-ferrites/same-net-ferrite.kicad_sch",
        "component.two_pin_ferrite_same_net",
        {"FB1 (600R@100MHz ferrite_bead) has both pins on one net"},
    ),
    "distinct-nets-ferrite": (
        "two-pin-ferrites/distinct-nets-ferrite.kicad_sch",
        "component.two_pin_ferrite_same_net",
        set(),
    ),
    "same-net-switch": (
        "two-pin-switches/same-net-spst.kicad_sch",
        "component.two_pin_switch_same_net",
        {"SW1 (Synthetic SPST switch) has both pins on one net"},
    ),
    "distinct-nets-switch": (
        "two-pin-switches/distinct-nets-spst.kicad_sch",
        "component.two_pin_switch_same_net",
        set(),
    ),
}

TWO_PIN_COMPONENT_CANDIDATE_KINDS: dict[str, frozenset[str]] = {
    "component.two_pin_passive_same_net": frozenset(
        {"resistor", "capacitor", "inductor", "varistor", "thermistor"}
    ),
    "component.two_pin_diode_same_net": frozenset({"diode"}),
    "component.two_pin_led_same_net": frozenset({"led"}),
    "component.two_pin_buzzer_same_net": frozenset({"buzzer"}),
    "component.two_pin_speaker_same_net": frozenset({"speaker"}),
    "component.two_pin_battery_same_net": frozenset({"battery"}),
    "component.two_pin_motor_same_net": frozenset({"motor"}),
    "component.two_pin_solar_cell_same_net": frozenset({"solar_cell"}),
    "component.two_pin_thermocouple_same_net": frozenset({"thermocouple"}),
    "component.two_pin_crystal_same_net": frozenset({"crystal"}),
    "component.two_pin_fuse_same_net": frozenset({"fuse", "polyfuse"}),
    "component.two_pin_ferrite_same_net": frozenset({"ferrite_bead"}),
    "component.two_pin_switch_same_net": frozenset({"switch"}),
}


def two_pin_component_fixture_cases_for_rules(
    rule_ids: tuple[str, ...] | None,
) -> dict[str, tuple[str, str, set[str]]]:
    """Select native fault/control fixtures for rule-scoped gates."""
    if rule_ids is None:
        return dict(TWO_PIN_COMPONENT_FIXTURE_CASES)

    requested = frozenset(rule_ids)
    known = frozenset(rule_id for _, rule_id, _ in TWO_PIN_COMPONENT_FIXTURE_CASES.values())
    unknown = requested - known
    if unknown:
        raise ValueError(f"Unknown two-pin component rule IDs: {sorted(unknown)}")
    if not requested:
        raise ValueError("At least one two-pin component rule ID is required")

    selected = {
        name: case for name, case in TWO_PIN_COMPONENT_FIXTURE_CASES.items() if case[1] in requested
    }
    if not selected:
        raise ValueError(f"No native fixture cases found for rules: {sorted(requested)}")
    return selected


def two_pin_component_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
    rule_ids: tuple[str, ...] | None = None,
) -> None:
    """Verify same-net component rules against repeated pinned native exports."""
    import hashlib
    import os

    from .hwrepo.component_role_models import (
        ComponentRoleBinding,
        ComponentRoleMap,
        ComponentRolePin,
    )
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.design_lint_report_models import DesignLintReport
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .hwrepo.two_pin_components import two_pin_components_on_same_net
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Two-pin component fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    cases = two_pin_component_fixture_cases_for_rules(rule_ids)
    source_hashes = {
        case: digest(fixture_root / filename) for case, (filename, _, _) in cases.items()
    }
    scratch = Path(
        tempfile.mkdtemp(prefix=f"two-pin-component-{project}-", dir=log.directory.resolve())
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
    for case, (filename, _, _) in cases.items():
        source_lines.append(f'printf "exporting_fixture=%s\\n" "{filename}"\n')
        source_lines.append(
            f"for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{filename}"; done\n'
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
        "HOME=/tmp/kicad-two-pin-component-fixtures",
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
        "".join(source_lines),
    )
    log.event(
        "two-pin-component-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "two-pin-component-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native two-pin component fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        "two-pin-component-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    custom_capacitor_role_map = ComponentRoleMap(
        entries=(
            ComponentRoleBinding(
                part_id="synthetic-decoupling-capacitor",
                symbol="Vendor:CAP123",
                footprint="Synthetic:CAP123_0603",
                role="capacitor",
                pins=(
                    ComponentRolePin(number="1", function="1", electrical_type="passive"),
                    ComponentRolePin(number="2", function="2", electrical_type="passive"),
                ),
                basis="Synthetic native fixture reviews this exact custom capacitor identity",
            ),
        )
    )
    role_map_cases = {"same-net-mapped-capacitor", "distinct-nets-mapped-capacitor"}
    for case, (_, rule_id, case_expected_subjects) in cases.items():
        role_map = custom_capacitor_role_map if case in role_map_cases else None
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native two-pin component fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            candidates = two_pin_components_on_same_net(observed, role_map)
            candidate_kinds = TWO_PIN_COMPONENT_CANDIDATE_KINDS[rule_id]
            matching_candidates = tuple(item for item in candidates if item.kind in candidate_kinds)
            expected_candidate_count = len(case_expected_subjects)
            if len(matching_candidates) != expected_candidate_count:
                raise ValueError(
                    f"Native {case} expected {expected_candidate_count} same-net component "
                    f"candidates, observed {len(matching_candidates)}"
                )
            project_id = f"synthetic-two-pin-component-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(
                project_id,
                coach,
                DesignLintPolicy(component_role_map=role_map),
            )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native two-pin component exports differ after normalization to parsed netlist contracts"
        )
    for case in cases:
        report = reports[(case, "first")]
        findings = {item.subject for item in report.findings if item.rule_id == cases[case][1]}
        if findings != cases[case][2]:
            raise ValueError(
                f"Native {case} lint result differs from expected findings: {sorted(findings)}"
            )
        expected_status = "REVIEW" if cases[case][2] else "PASS"
        if report.status != expected_status:
            raise ValueError(
                f"Native {case} expected lint status {expected_status}, observed {report.status}"
            )
        log.event(
            f"two-pin-component-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            lint_status=report.status,
            component_rule=cases[case][1],
            component_findings=";".join(sorted(findings)) or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(fixture_root / filename) != source_hashes[case]
        for case, (filename, _, _) in cases.items()
    ):
        raise ValueError("Synthetic two-pin component fixture source changed during native export")
