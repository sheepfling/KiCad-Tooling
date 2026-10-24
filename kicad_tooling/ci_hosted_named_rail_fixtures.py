"""Shared digest-pinned native runner for named-rail lint fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from .ci_hosted_kicad10_images import KICAD_10_NATIVE_TOOLCHAINS
from .hwrepo.contracts import read_kicad_erc_report, write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


def named_rail_fixture_lane(
    root: Path,
    *,
    version: str,
    image: str,
    log: HostedLog,
    protocol: str,
    feature: str,
    rule_id: str,
    fixture_directory: str,
    source_hashes: Mapping[str, str],
    expected_nets: Mapping[str, Mapping[str, tuple[str, ...]]],
    expected_subjects: Mapping[str, tuple[str, ...]],
    expected_pin_functions: Mapping[str, str] | None = None,
) -> None:
    """Export and relint exact fault/control schematics on one pinned KiCad image."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    if (version, image) not in KICAD_10_NATIVE_TOOLCHAINS:
        raise ValueError(f"Named-rail fixture lane is not configured for KiCad {version}")
    cases = ("fault", "control")
    if any(
        set(mapping) != set(cases) for mapping in (source_hashes, expected_nets, expected_subjects)
    ):
        raise ValueError("Named-rail fixture lane requires exact fault and control expectations")
    pinned = pinned_image(image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint" / fixture_directory
    )
    sources = {case: fixture_root / f"{case}.kicad_sch" for case in cases}
    actual_source_hashes = {case: digest(source) for case, source in sources.items()}
    if actual_source_hashes != dict(source_hashes):
        raise ValueError(f"{protocol} {feature} named-rail sources differ from reviewed hashes")

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"{protocol}-{feature}-named-rail-{version}-",
            dir=log.directory.resolve(),
        )
    )
    inputs = scratch / "input"
    inputs.mkdir()
    output = scratch / "output"
    output.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"\n'
        'actual="$(kicad-cli version)"\n'
        'printf "kicad_version=%s\\n" "$actual"\n'
        f'test "$actual" = "{version}"\n'
        "for case in fault control; do\n"
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
        f"HOME=/tmp/kicad-{protocol}-{feature}-named-rail",
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
    stage_prefix = f"{protocol}-{feature}-named-rail-fixture"
    log.event(
        f"{stage_prefix}/native-export",
        "START",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        raise ValueError(
            f"Native {protocol} {feature} named-rail export failed: "
            f"{command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    findings: dict[tuple[str, str], tuple[str, ...]] = {}
    for case, source in sources.items():
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            erc_path = output / f"{case}.{run}.erc.json"
            if not netlist_path.is_file() or not erc_path.is_file():
                raise ValueError(
                    f"Native KiCad omitted {protocol} {feature} named-rail {case} evidence"
                )
            observed = read_netlist(netlist_path)
            if expected_pin_functions is not None and observed.pin_functions != dict(
                expected_pin_functions
            ):
                raise ValueError(f"Native {protocol} {feature} {case} pin functions changed")
            if any(observed.nets.get(net) != pins for net, pins in expected_nets[case].items()):
                raise ValueError(
                    f"Native {protocol} {feature} named-rail {case} net assignments changed"
                )
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            erc = read_kicad_erc_report(erc_path)
            if erc.kicad_version != version or any(
                item.severity == "error" for item in erc.violations
            ):
                raise ValueError(
                    f"Native ERC reported errors for {protocol} {feature} named-rail {case}"
                )
            project_id = f"synthetic-{protocol}-{feature}-named-rail-{case}"
            report = evaluate(
                project_id,
                ContractCoachReport(
                    status="READY_FOR_REVIEW",
                    project_id=project_id,
                    observed=observed,
                    netlist_sha256=digest(netlist_path),
                ),
                DesignLintPolicy(),
            )
            findings[(case, run)] = tuple(
                item.subject for item in report.findings if item.rule_id == rule_id
            )

    for case in cases:
        first = normalized_hashes[(case, "first")]
        repeat = normalized_hashes[(case, "repeat")]
        expected = tuple(expected_subjects[case])
        if first != repeat or findings[(case, "first")] != expected:
            raise ValueError(
                f"Native {protocol} {feature} named-rail {case} result differs from its fixture"
            )
        if findings[(case, "repeat")] != findings[(case, "first")]:
            raise ValueError(
                f"Native {protocol} {feature} named-rail {case} findings are not repeatable"
            )
        log.event(
            f"{stage_prefix}/{case}",
            "PASS",
            project=f"kicad-{version}",
            kicad_version=version,
            image=pinned,
            source_sha256=actual_source_hashes[case],
            normalized_netlist_sha256=first,
            repeat_normalized_netlist_sha256=repeat,
            erc_errors="none",
            repeatable="true",
            subjects=";".join(expected) if expected else "none",
        )
    log.event(
        f"{stage_prefix}/native-export",
        "PASS",
        project=f"kicad-{version}",
        kicad_version=version,
        image=pinned,
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    log.finish()
