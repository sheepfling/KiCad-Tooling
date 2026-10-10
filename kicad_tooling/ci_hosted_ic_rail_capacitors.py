"""IC rail capacitor fixture analysis and native acceptance."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def ic_rail_capacitor_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Check synthetic IC power-rail faults and controls with native exports and ERC."""
    import hashlib
    import os

    from .hwrepo.component_roles import resolve_component_role_map
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
    from .hwrepo.power_decoupling import ic_power_rails_without_fitted_capacitors
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"IC rail-capacitor fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/cohort-power-pin-dc"
    )
    cases = {
        "positive-rail-no-cap": "no-cap.kicad_sch",
        "positive-rail-cap-control": "control.kicad_sch",
        "unrecognized-rail-control": "fault.kicad_sch",
        "source-backed-control": "source-backed-control.kicad_sch",
        "source-backed-no-cap": "source-backed-no-cap.kicad_sch",
        "source-backed-dnp-capacitor": "source-backed-dnp-capacitor.kicad_sch",
        "custom-capacitor-role-control": "custom-capacitor-role-control.kicad_sch",
        "custom-capacitor-role-wrong-return": "custom-capacitor-role-wrong-return.kicad_sch",
    }
    source_hashes = {case: digest(fixture_root / name) for case, name in cases.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"ic-rail-capacitor-{project}-", dir=log.directory.resolve())
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
    for case, filename in cases.items():
        export_command = (
            f"for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{filename}"; done\n'
        )
        erc_command = (
            f"for run in first repeat; do kicad-cli sch erc --format json --severity-all "
            f'--output "/output/{case}.${{run}}.erc.json" '
            f'"/fixtures/{filename}"; done\n'
        )
        source_lines.extend((export_command, erc_command))
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
        "HOME=/tmp/kicad-rail-cap-fixtures",
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
        "ic-rail-cap-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "ic-rail-cap-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native IC rail-capacitor fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        "ic-rail-cap-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    expected_gaps: dict[str, set[tuple[str, tuple[str, ...], tuple[str, ...]]]] = {
        "positive-rail-no-cap": {("+3V3", ("U1.1",), ("U1",))},
        "positive-rail-cap-control": set(),
        "unrecognized-rail-control": set(),
        "source-backed-control": set(),
        "source-backed-no-cap": {("+3V3", ("U1.1",), ("U1",))},
        "source-backed-dnp-capacitor": {("+3V3", ("U1.1",), ("U1",))},
        "custom-capacitor-role-control": set(),
        "custom-capacitor-role-wrong-return": {("+3V3", ("U1.1",), ("U1",))},
    }
    expected_findings: dict[str, set[str]] = {
        "positive-rail-no-cap": {"+3V3: IC supply decoupling review"},
        "positive-rail-cap-control": set(),
        "unrecognized-rail-control": set(),
        "source-backed-control": set(),
        "source-backed-no-cap": {"+3V3: IC supply decoupling review"},
        "source-backed-dnp-capacitor": {"+3V3: IC supply decoupling review"},
        "custom-capacitor-role-control": set(),
        "custom-capacitor-role-wrong-return": {"+3V3: IC supply decoupling review"},
    }
    expected_source_path_findings: dict[str, set[str]] = {
        "positive-rail-no-cap": set(),
        "positive-rail-cap-control": set(),
        "unrecognized-rail-control": {"LOCAL_A: power-input source-path review"},
        "source-backed-control": set(),
        "source-backed-no-cap": set(),
        "source-backed-dnp-capacitor": set(),
        "custom-capacitor-role-control": set(),
        "custom-capacitor-role-wrong-return": set(),
    }
    expected_power_pin_not_driven = {
        "positive-rail-no-cap",
        "positive-rail-cap-control",
        "unrecognized-rail-control",
    }
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
                basis="Synthetic native fixture uses this exact opaque two-pin capacitor identity",
            ),
        )
    )
    normalized_hashes: dict[tuple[str, str], str] = {}
    normalized_erc_hashes: dict[tuple[str, str], str] = {}
    erc_types: dict[tuple[str, str], tuple[str, ...]] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native IC rail-capacitor fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc_path = output / f"{case}.{run}.erc.json"
            if not erc_path.is_file():
                raise ValueError(f"Native IC power-rail fixture omitted {erc_path.name}")
            erc_report = read_kicad_erc_report(erc_path)
            if erc_report.kicad_version != config.kicad_version:
                raise ValueError(
                    f"Native {case} ERC report version differs from KiCad {config.kicad_version}"
                )
            violations = erc_report.violations
            erc_types[(case, run)] = tuple(sorted(item.type for item in violations))
            normalized_erc = json.dumps(
                {
                    "kicad_version": erc_report.kicad_version,
                    "violations": sorted(
                        [
                            (
                                item.type,
                                item.severity,
                                item.description,
                                tuple(
                                    sorted(
                                        [
                                            (detail.description, detail.x, detail.y)
                                            for detail in item.items
                                        ],
                                        key=lambda detail: json.dumps(
                                            detail,
                                            sort_keys=True,
                                            separators=(",", ":"),
                                            ensure_ascii=False,
                                        ),
                                    )
                                ),
                            )
                            for item in violations
                        ],
                        key=lambda item: json.dumps(
                            item,
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ),
                    ),
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_erc_hashes[(case, run)] = hashlib.sha256(normalized_erc).hexdigest()
            has_undriven_power_pin = "power_pin_not_driven" in erc_types[(case, run)]
            if has_undriven_power_pin != (case in expected_power_pin_not_driven):
                raise ValueError(
                    f"Native {case} ERC power-source result differs from expectation: "
                    f"{erc_types[(case, run)]}"
                )
            erc_error_types = tuple(
                sorted(item.type for item in erc_report.violations if item.severity == "error")
            )
            expected_error_types = (
                ("power_pin_not_driven",) if case in expected_power_pin_not_driven else ()
            )
            if erc_error_types != expected_error_types:
                raise ValueError(
                    f"Native {case} ERC error set differs from expectation: {erc_error_types}"
                )
            policy = (
                DesignLintPolicy(component_role_map=custom_capacitor_role_map)
                if case.startswith("custom-capacitor-role-")
                else DesignLintPolicy()
            )
            role_resolution = resolve_component_role_map(observed, policy.component_role_map)
            if role_resolution.issues:
                raise ValueError(
                    f"Native {case} project capacitor role map is stale: {role_resolution.issues}"
                )
            mapped_capacitor_references = tuple(
                reference
                for reference, binding in role_resolution.by_reference.items()
                if binding.role == "capacitor"
            )
            gaps = {
                (item.net, item.input_pins, item.component_references)
                for item in ic_power_rails_without_fitted_capacitors(
                    observed, mapped_capacitor_references=mapped_capacitor_references
                )
            }
            if gaps != expected_gaps[case]:
                raise ValueError(
                    f"Native {case} rail-capacitor topology differs from expectation: "
                    f"{sorted(gaps)}"
                )
            if case in {
                "source-backed-control",
                "source-backed-no-cap",
                "source-backed-dnp-capacitor",
                "custom-capacitor-role-control",
                "custom-capacitor-role-wrong-return",
            }:
                expected_source_net = (
                    {"U1.1", "U2.1"} if case == "source-backed-no-cap" else {"C1.1", "U1.1", "U2.1"}
                )
                if set(observed.nets.get("+3V3", ())) != expected_source_net:
                    raise ValueError(f"Native {case} does not match its authored +3V3 pin topology")
                if observed.pin_electrical_types.get("U2.1") != "power_out":
                    raise ValueError(f"Native {case} source pin is not power_out")
                if (case == "source-backed-dnp-capacitor") != ("C1" in observed.dnp_components):
                    raise ValueError(
                        f"Native {case} did not preserve the capacitor population state"
                    )
            if case.startswith("custom-capacitor-role-"):
                component = observed.components.get("C1")
                if (
                    component is None
                    or component.part_id != "synthetic-decoupling-capacitor"
                    or component.footprint != "Synthetic:CAP123_0603"
                    or observed.component_symbols.get("C1") != "Vendor:CAP123"
                    or observed.component_pin_numbers.get("C1") != ("1", "2")
                    or observed.pin_functions.get("C1.1") != "1"
                    or observed.pin_functions.get("C1.2") != "2"
                    or observed.pin_electrical_types.get("C1.1") != "passive"
                    or observed.pin_electrical_types.get("C1.2") != "passive"
                ):
                    raise ValueError(
                        f"Native {case} did not preserve the exact project capacitor-role identity"
                    )
                expected_capacitor_reference_net = (
                    "GND" if case == "custom-capacitor-role-control" else "CAP_REF"
                )
                net_by_pin = {
                    pin.casefold(): net for net, pins in observed.nets.items() for pin in pins
                }
                if (
                    net_by_pin.get("c1.1") != "+3V3"
                    or net_by_pin.get("c1.2") != expected_capacitor_reference_net
                ):
                    raise ValueError(f"Native {case} does not match its authored capacitor nets")
            project_id = f"synthetic-ic-rail-capacitor-{case}"
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
            "Native IC rail-capacitor exports differ after normalization to parsed netlist contracts"
        )
    if any(
        normalized_erc_hashes[(case, "first")] != normalized_erc_hashes[(case, "repeat")]
        for case in cases
    ):
        raise ValueError("Native IC power-rail ERC reports differ after normalization")
    for case in cases:
        findings = {
            item.subject
            for item in reports[(case, "first")].findings
            if item.rule_id == "power.ic_rail_without_fitted_capacitor"
        }
        if findings != expected_findings[case]:
            raise ValueError(
                f"Native {case} lint result differs from the rail-capacitor expectation: "
                f"{sorted(findings)}"
            )
        source_path_findings = {
            item.subject
            for item in reports[(case, "first")].findings
            if item.rule_id == "power.input_without_supported_source_path"
        }
        if source_path_findings != expected_source_path_findings[case]:
            raise ValueError(
                f"Native {case} source-anchor/path result differs from expectation: "
                f"{sorted(source_path_findings)}"
            )
        if case == "unrecognized-rail-control":
            source_finding = next(
                item
                for item in reports[(case, "first")].findings
                if item.rule_id == "power.input_without_supported_source_path"
            )
            if source_finding.evidence.get("source_anchor_state") != ("not_recognized",):
                raise ValueError(
                    "Native custom-rail case lost its explicit source-anchor coverage evidence"
                )
        log.event(
            f"ic-rail-cap-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            normalized_erc_sha256=normalized_erc_hashes[(case, "first")],
            repeat_normalized_erc_sha256=normalized_erc_hashes[(case, "repeat")],
            native_erc_types=",".join(erc_types[(case, "first")]) or "none",
            native_erc_error_types=",".join(
                sorted(
                    item.type
                    for item in read_kicad_erc_report(output / f"{case}.first.erc.json").violations
                    if item.severity == "error"
                )
            )
            or "none",
            power_pin_not_driven=("true" if case in expected_power_pin_not_driven else "false"),
            lint_status=reports[(case, "first")].status,
            capacitor_findings=";".join(sorted(findings)) or "none",
            source_path_findings=";".join(sorted(source_path_findings)) or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_and_erc",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(fixture_root / filename) != source_hashes[case] for case, filename in cases.items()
    ):
        raise ValueError("Synthetic IC rail-capacitor fixture source changed during native export")
