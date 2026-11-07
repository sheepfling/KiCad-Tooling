"""Digest-pinned native fixtures for open CANH/CANL schematic pins."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .ci_hosted_support import HostedLog, tooling_checkout_root
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.contracts import read_kicad_erc_report, write_model
from .hwrepo.design_lint import evaluate
from .hwrepo.evidence import digest
from .hwrepo.models import DesignLintPolicy
from .hwrepo.native_report_parsing import read_netlist

CAN_UNCONNECTED_LINE_TOOLCHAINS = KICAD_10_NATIVE_TOOLCHAINS
_RULE_ID = "bus.can_unconnected_line"
_SOURCE_HASHES = MappingProxyType(
    {
        "control": "79e2f1512c05cb291a8a542c2701d9737e8b0231d8790fcac7b33a89385c9e97",
        "fault": "c84f251d9d84da280d75563a948b499af0b733d78167517106b0bcba9bb823e6",
    }
)


def can_unconnected_line_fixture_lane(
    root: Path, *, version: str, image: str, log: HostedLog
) -> None:
    """Export repeated exact-version fault/control netlists and evaluate the CAN line lint."""
    root = root.resolve()
    if (version, image) not in CAN_UNCONNECTED_LINE_TOOLCHAINS:
        raise ValueError(f"CAN unconnected-line fixtures do not cover KiCad {version}")
    pinned = pinned_image(image)
    fixture_root = (
        tooling_checkout_root() / "tests/fixtures/design_lint/can-unconnected-lines-native"
    )
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in ("control", "fault")}
    source_hashes = {case: digest(source) for case, source in sources.items()}
    if source_hashes != dict(_SOURCE_HASHES):
        raise ValueError("CAN unconnected-line fixture sources differ from their reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"can-unconnected-line-{version}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    output = scratch / "output"
    output.mkdir()
    for case, source in sources.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(source, target)
        if digest(target) != source_hashes[case]:
            raise ValueError(f"Synthetic CAN {case} source changed while preparing native input")

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{version}"\n'
        "for case in control fault; do\n"
        "  for run in first repeat; do\n"
        '    kicad-cli sch export netlist --format kicadxml --output "/output/$case.$run.netlist.xml" '
        '"/fixtures/$case.kicad_sch"\n'
        '    kicad-cli sch erc --format json --severity-all --output "/output/$case.$run.erc.json" '
        '"/fixtures/$case.kicad_sch"\n'
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
        "HOME=/tmp/kicad-can-unconnected-line",
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
    stage = "can-unconnected-line-fixture/native-export"
    log.event(stage, "START", project=f"kicad-{version}", kicad_version=version, image=pinned)
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            stage,
            "FAIL",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native CAN unconnected-line export failed: {command.stderr or command.error}"
        )

    expected_nets = {
        "control": {"CANL_BUS": ("U1.2",), "CANH_BUS": ("U1.1",)},
        "fault": {"CANL_BUS": ("U1.2",)},
    }
    expected_unconnected = {"control": (), "fault": ("U1.1",)}
    expected_subjects = {"control": (), "fault": ("U1.1: CANH",)}
    normalized_hashes: dict[tuple[str, str], str] = {}
    netlist_hashes: dict[tuple[str, str], str] = {}
    observed_subjects: dict[tuple[str, str], tuple[str, ...]] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(f"Native KiCad omitted CAN unconnected-line {case} evidence")
            observed = read_netlist(netlist_path)
            if observed.pin_functions != {"U1.1": "CANH", "U1.2": "CANL"}:
                raise ValueError(
                    f"Native CAN {case} pin functions changed: {observed.pin_functions}"
                )
            if observed.component_pin_numbers.get("U1") != ("1", "2"):
                raise ValueError(f"Native CAN {case} pin inventory changed")
            if any(observed.nets.get(net) != pins for net, pins in expected_nets[case].items()):
                raise ValueError(f"Native CAN {case} line assignments changed: {observed.nets}")
            unconnected = tuple(
                sorted(pin for pins in observed.unconnected_nets.values() for pin in pins)
            )
            if unconnected != expected_unconnected[case]:
                raise ValueError(f"Native CAN {case} open-pin inventory changed: {unconnected}")

            netlist_hashes[(case, run)] = digest(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version or any(
                violation.severity == "error" for violation in erc.violations
            ):
                raise ValueError(f"Native ERC reported errors for CAN unconnected-line {case}")

            project_id = f"synthetic-can-unconnected-line-{case}"
            report = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=netlist_hashes[(case, run)],
                ),
                DesignLintPolicy(),
            )
            observed_subjects[(case, run)] = tuple(
                finding.subject for finding in report.findings if finding.rule_id == _RULE_ID
            )

    for case in sources:
        first = normalized_hashes[(case, "first")]
        repeat = normalized_hashes[(case, "repeat")]
        if first != repeat:
            raise ValueError(f"Native CAN {case} netlists differ after normalization")
        if observed_subjects[(case, "first")] != expected_subjects[case]:
            raise ValueError(
                f"Native CAN {case} findings are {observed_subjects[(case, 'first')]!r}; "
                f"expected {expected_subjects[case]!r}"
            )
        if observed_subjects[(case, "repeat")] != observed_subjects[(case, "first")]:
            raise ValueError(f"Native CAN {case} lint findings differ on repeat")
        log.event(
            f"can-unconnected-line-fixture/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=first,
            repeat_normalized_netlist_sha256=repeat,
            erc_errors="none",
            repeatable="true",
            subjects=";".join(expected_subjects[case]) or "none",
        )
    log.event(
        stage,
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        control_source_sha256=source_hashes["control"],
        fault_source_sha256=source_hashes["fault"],
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
