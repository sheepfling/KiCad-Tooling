"""Digest-pinned native export lane for Ethernet pin/net-label review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_ethernet_label_models import ETHERNET_LABEL_FIXTURES, EthernetLabelFeature
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contracts import write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import ContractCoachReport, DesignLintPolicy, NetlistContract
from .validate import read_netlist

ETHERNET_LABEL_NATIVE_TOOLCHAINS = (
    (
        "10.0.0",
        (
            "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
        ),
    ),
    (
        "10.0.5",
        (
            "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
        ),
    ),
)


def ethernet_label_fixture_lane(
    root: Path,
    *,
    project: str | None = None,
    version: str | None = None,
    image: str,
    log: HostedLog,
    feature: EthernetLabelFeature = "data",
) -> None:
    """Export source-hashed Ethernet label controls and evaluate one focused rule."""
    root = root.resolve()
    fixture = ETHERNET_LABEL_FIXTURES[feature]
    if project is None:
        if version is None or (version, image) not in ETHERNET_LABEL_NATIVE_TOOLCHAINS:
            raise ValueError("Ethernet native fixture requires a configured KiCad 10 toolchain")
        selected_version = version
        project_label = f"kicad-{version}"
    else:
        config = selected_config(root, project)
        if config.image != image:
            raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
        if version is not None and config.kicad_version != version:
            raise ValueError(
                f"{project}: native fixture version differs from its reviewed toolchain"
            )
        if config.kicad_version not in {"10.0.0", "10.0.5"}:
            raise ValueError(f"Ethernet label fixtures do not cover KiCad {config.kicad_version}")
        selected_version = config.kicad_version
        project_label = project
    pinned = pinned_image(image)
    repository = tooling_checkout_root()
    sources = {
        case: repository / f"tests/fixtures/design_lint/{fixture.directory}/{case}.kicad_sch"
        for case in ("control", "fault")
    }
    expected_source_hashes = {
        "control": fixture.control.source_sha256,
        "fault": fixture.fault.source_sha256,
    }
    source_hashes = {case: digest(path) for case, path in sources.items()}
    if source_hashes != expected_source_hashes:
        raise ValueError("Ethernet label fixtures differ from their reviewed source hashes")

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"ethernet-{feature}-label-{project_label}-", dir=log.directory.resolve()
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(source, target)
        if digest(target) != source_hashes[case]:
            raise ValueError(f"Synthetic Ethernet {case} schematic changed during preparation")
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{selected_version}"\n'
        "for case in control fault; do\n"
        "  for run in first repeat; do\n"
        "    kicad-cli sch export netlist --format kicadxml "
        '      --output "/output/${case}.${run}.netlist.xml" '
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
        "HOME=/tmp/kicad-ethernet-label-fixtures",
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
        f"{fixture.stage_prefix}/native-export",
        "START",
        project=project_label,
        kicad_version=selected_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            f"{fixture.stage_prefix}/native-export",
            "FAIL",
            project=project_label,
            kicad_version=selected_version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(f"Native Ethernet label export failed: {command.stderr or command.error}")
    log.event(
        f"{fixture.stage_prefix}/native-export",
        "PASS",
        project=project_label,
        kicad_version=selected_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in sorted(sources)),
        command_receipt=receipt.relative_to(root).as_posix(),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    observations: dict[tuple[str, str], NetlistContract] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native Ethernet export omitted {netlist_path.name}")
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
            project_id = f"synthetic-ethernet-{feature}-label-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())

    if any(
        normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]
        for case in sources
    ):
        raise ValueError("Native Ethernet exports differ after netlist normalization")

    control = reports[("control", "first")]
    fault = reports[("fault", "first")]
    control_findings = tuple(item for item in control.findings if item.rule_id == fixture.rule_id)
    fault_findings = tuple(item for item in fault.findings if item.rule_id == fixture.rule_id)
    if tuple(item.subject for item in control_findings) != fixture.control.subjects:
        raise ValueError("Native Ethernet label control produced an unexpected finding")
    if tuple(item.subject for item in fault_findings) != fixture.fault.subjects:
        raise ValueError(
            f"Native Ethernet label fault produced "
            f"{tuple(item.subject for item in fault_findings)!r}; "
            f"expected {fixture.fault.subjects!r}"
        )
    if fixture.complete_data_pairs and any(
        item.rule_id == "bus.complementary_pair_assignment" for item in fault.findings
    ):
        raise ValueError("Complete Ethernet pairs should remain outside pair-completeness findings")

    for case, report, findings in (
        ("control", control, control_findings),
        ("fault", fault, fault_findings),
    ):
        observed = observations[(case, "first")]
        expectation = fixture.control if case == "control" else fixture.fault
        for expected_pin in expectation.pins:
            pin = expected_pin.reference
            function = expected_pin.function
            net = expected_pin.net
            assigned_nets = tuple(
                sorted(
                    name
                    for name, members in observed.nets.items()
                    if any(member.casefold() == pin.casefold() for member in members)
                )
            )
            expected_nets = () if net is None else (net,)
            if observed.pin_functions.get(pin) != function or assigned_nets != expected_nets:
                raise ValueError(f"Native Ethernet {feature} {case} evidence changed for {pin}")
            if net is None:
                unconnected_pins = {
                    pin.casefold()
                    for members in observed.unconnected_nets.values()
                    for pin in members
                }
                if pin.casefold() not in unconnected_pins:
                    raise ValueError(
                        f"Native Ethernet {feature} {case} omitted the open-pin evidence for {pin}"
                    )
        log.event(
            f"{fixture.stage_prefix}/{case}",
            "PASS",
            project=project_label,
            kicad_version=selected_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            repeatable="true",
            lint_status=report.status,
            findings=";".join(item.subject for item in findings) if findings else "none",
        )
    log.finish()
