"""Hosted native two-pin component fixture lane."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


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


def two_pin_component_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Verify same-net component rules against repeated pinned native exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ComponentRoleBinding,
        ComponentRoleMap,
        ComponentRolePin,
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
    )
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
    cases = TWO_PIN_COMPONENT_FIXTURE_CASES
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
            candidate_kinds = {
                "component.two_pin_passive_same_net": {"resistor", "capacitor", "inductor"},
                "component.two_pin_diode_same_net": {"diode"},
                "component.two_pin_crystal_same_net": {"crystal"},
                "component.two_pin_fuse_same_net": {"fuse", "polyfuse"},
                "component.two_pin_ferrite_same_net": {"ferrite_bead"},
                "component.two_pin_switch_same_net": {"switch"},
            }[rule_id]
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
