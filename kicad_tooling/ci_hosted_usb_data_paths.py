"""Hosted native fixture lane for USB data paths and reference domains."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_usb_requirements import usb_data_path_requirements

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def usb_data_path_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Compare mapped USB PHY topologies with repeated, pinned native netlist exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.contracts import write_model
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
    )
    from .hwrepo.usb_data_paths import usb_data_path_mismatches
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"USB data-path fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)

    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    cases = {
        "integrated-direct": fixture_root / "usb-data-path-native/integrated-phy-direct.kicad_sch",
        "external-series": fixture_root
        / "usb-data-path-native/external-phy-series-control.kicad_sch",
        "external-series-reference-bond-control": fixture_root
        / "usb-data-path-native/external-phy-series-reference-bond-control.kicad_sch",
        "external-series-reference-fault": fixture_root
        / "usb-data-path-native/external-phy-series-reference-fault.kicad_sch",
        "external-bypass": fixture_root
        / "usb-data-path-native/external-phy-direct-bypass-fault.kicad_sch",
        "peer-reference-fault": fixture_root / "usb-peer-reference-native/fault.kicad_sch",
        "peer-reference-control": fixture_root / "usb-peer-reference-native/control.kicad_sch",
        "usb-c-peer-reference-fault": fixture_root / "usb-c-peer-reference-native/fault.kicad_sch",
        "usb-c-peer-reference-control": fixture_root
        / "usb-c-peer-reference-native/control.kicad_sch",
        "usb-multiport-peer-reference-fault": fixture_root
        / "usb-multiport-peer-reference-native/fault.kicad_sch",
        "usb-multiport-peer-reference-control": fixture_root
        / "usb-multiport-peer-reference-native/control.kicad_sch",
    }
    source_hashes = {case: digest(path) for case, path in cases.items()}
    scratch = Path(
        tempfile.mkdtemp(prefix=f"usb-data-path-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source_path in cases.items():
        shutil.copyfile(source_path, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} USB fixture changed while preparing native input")
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
    for case in cases:
        export_command = (
            f"for run in first repeat; do kicad-cli sch export netlist "
            f'--format kicadxml --output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{case}.kicad_sch"; done\n'
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
        "HOME=/tmp/kicad-usb-fixtures",
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
        "usb-data-path-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "usb-data-path-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native USB fixture command failed: {command.stderr or command.error}")
    log.event(
        "usb-data-path-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )

    requirements = usb_data_path_requirements()

    normalized_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native USB fixture omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            mismatches = usb_data_path_mismatches(requirements[case], observed)
            if case == "external-bypass":
                subjects = {item.line for item in mismatches}
                if subjects != {"D+", "D-"}:
                    raise ValueError(
                        f"Native external-PHY bypass should mismatch both USB data lines; "
                        f"observed {sorted(subjects)}"
                    )
            elif mismatches:
                raise ValueError(
                    f"Native {case} USB control mismatched the authored topology: {mismatches}"
                )

            project_id = f"synthetic-usb-data-path-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(
                project_id,
                coach,
                DesignLintPolicy(usb_data_path_map=requirements[case]),
            )

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")] for case in cases
    ):
        raise ValueError(
            "Native USB exports differ after normalization to parsed netlist contracts"
        )

    fault = reports[("external-bypass", "first")]
    fault_findings = tuple(
        item for item in fault.findings if item.rule_id == "bus.usb_data_path_mismatch"
    )
    if fault.status != "REVIEW":
        raise ValueError("Native external-PHY bypass did not produce the expected REVIEW")
    if {item.subject for item in fault_findings} != {
        "external-usb-phy: USB D+ path",
        "external-usb-phy: USB D- path",
    }:
        raise ValueError("Native external-PHY bypass did not emit one path finding per data line")
    for case in (
        "integrated-direct",
        "external-series",
        "external-series-reference-bond-control",
    ):
        if any(
            item.rule_id == "bus.usb_data_path_mismatch"
            for item in reports[(case, "first")].findings
        ):
            raise ValueError(f"Native {case} control produced a USB data-path finding")
    if any(
        item.rule_id == "bus.usb_peer_reference_review"
        for item in reports[("external-series", "first")].findings
    ):
        raise ValueError("Native common-reference series USB control produced a reference review")
    if any(
        item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
        for item in reports[("external-series-reference-bond-control", "first")].findings
    ):
        raise ValueError("Native exact bonded-reference USB control produced a reference finding")

    series_peer_faults = tuple(
        item
        for item in reports[("external-series-reference-fault", "first")].findings
        if item.rule_id == "bus.usb_peer_reference_review"
    )
    if len(series_peer_faults) != 1:
        raise ValueError(
            "Native split-reference USB peer with series resistors should produce one review"
        )
    series_peer_evidence = series_peer_faults[0].evidence
    if series_peer_evidence.get("USB_D+_series_resistor") != (
        "R1 (Device:R, 27R; R1.1=USB_D+, R1.2=USB_DP_PHY)",
    ) or series_peer_evidence.get("USB_D-_series_resistor") != (
        "R2 (Device:R, 27R; R2.1=USB_D-, R2.2=USB_DM_PHY)",
    ):
        raise ValueError(
            "Native series-resistor reference review omitted exact resistor pin/net evidence"
        )
    if series_peer_evidence.get("connector_reference_pin_assignments") != (
        "J1.4 (GND, passive)=USB_GND",
    ) or series_peer_evidence.get("phy_reference_pin_assignments") != (
        "U1.3 (AGND, power_in)=PHY_GND",
    ):
        raise ValueError("Native series-resistor review omitted split-reference assignments")

    peer_reference_faults = tuple(
        item
        for item in reports[("peer-reference-fault", "first")].findings
        if item.rule_id == "bus.usb_peer_reference_review"
    )
    if len(peer_reference_faults) != 1:
        raise ValueError(
            "Native split-reference USB peer should produce exactly one bounded review"
        )
    if peer_reference_faults[0].evidence.get("connector_reference_pin_assignments") != (
        "J1.4 (GND, passive)=USB_GND",
    ) or peer_reference_faults[0].evidence.get("phy_reference_pin_assignments") != (
        "U1.3 (AGND, power_in)=PHY_GND",
    ):
        raise ValueError("Native USB peer review did not preserve exact reference-pin evidence")
    if any(
        item.rule_id == "bus.usb_peer_reference_review"
        for item in reports[("peer-reference-control", "first")].findings
    ):
        raise ValueError("Native common-reference USB peer control produced a review")

    usb_c_peer_faults = tuple(
        item
        for item in reports[("usb-c-peer-reference-fault", "first")].findings
        if item.rule_id == "bus.usb_peer_reference_review"
    )
    if len(usb_c_peer_faults) != 1:
        raise ValueError("Native USB-C split-reference peer should produce exactly one review")
    usb_c_peer_evidence = usb_c_peer_faults[0].evidence
    if usb_c_peer_evidence.get("USB_D+_link") != ("J1.A6, J1.B6 / U1.1=USB_D+",) or (
        usb_c_peer_evidence.get("USB_D-_link") != ("J1.A7, J1.B7 / U1.2=USB_D-",)
    ):
        raise ValueError("Native USB-C review did not preserve duplicate-contact pin evidence")
    if usb_c_peer_evidence.get("USB_D+_shunt_branches") != (
        "D1.2 (Synthetic:TVS) to D1.1=USB_GND",
    ) or usb_c_peer_evidence.get("USB_D-_shunt_branches") != (
        "D2.2 (Synthetic:TVS) to D2.1=USB_GND",
    ):
        raise ValueError("Native USB-C review did not preserve two-pin shunt evidence")
    if any(
        item.rule_id == "bus.usb_peer_reference_review"
        for item in reports[("usb-c-peer-reference-control", "first")].findings
    ):
        raise ValueError("Native common-reference USB-C peer control produced a review")

    multiport_faults = tuple(
        item
        for item in reports[("usb-multiport-peer-reference-fault", "first")].findings
        if item.rule_id == "bus.usb_peer_reference_review"
    )
    if tuple((item.subject, item.evidence.get("USB_port_group")) for item in multiport_faults) != (
        ("J1 / U1: USB reference-domain review (port 1)", ("1",)),
        ("J2 / U1: USB reference-domain review (port 2)", ("2",)),
    ):
        raise ValueError("Native multiport USB fault did not localize both exact hub port groups")
    if any(
        item.rule_id == "bus.usb_peer_reference_review"
        for item in reports[("usb-multiport-peer-reference-control", "first")].findings
    ):
        raise ValueError("Native common-reference multiport USB control produced a review")

    for case in cases:
        report = reports[(case, "first")]
        log.event(
            f"usb-data-path-fixture/{case}",
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
            usb_path_findings=";".join(
                item.subject
                for item in report.findings
                if item.rule_id == "bus.usb_data_path_mismatch"
            )
            or "none",
            usb_reference_findings=";".join(
                item.subject
                for item in report.findings
                if item.rule_id == "bus.usb_peer_reference_review"
            )
            or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_contract",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )

    if any(
        digest(filename) != source_hashes[case]
        or digest(inputs / f"{case}.kicad_sch") != source_hashes[case]
        for case, filename in cases.items()
    ):
        raise ValueError("Synthetic USB fixture source changed during native export")
