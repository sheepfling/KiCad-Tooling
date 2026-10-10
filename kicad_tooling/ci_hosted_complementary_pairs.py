"""Hosted native complementary-pair fixture lane."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted import HostedLog


def complementary_pair_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Verify USB SuperSpeed pin-function aliases with repeated native exports."""
    import hashlib
    import os

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
        DesignLintReport,
        NetlistContract,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"Complementary-pair fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint/complementary-pair-native"
    )
    cases = {"fault": "fault.kicad_sch", "control": "control.kicad_sch"}
    source_hashes = {case: digest(fixture_root / filename) for case, filename in cases.items()}
    expected_source_hashes = {
        "fault": "cc8832c4f8ab0b74996f3035ec5c9b85780c11e63bee9a33ea50d319dff2c755",
        "control": "4c0fcc56824a6004a1f63cfd0fc026f8e90438919eb936c492eeb96e9ecad601",
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("USB SuperSpeed fixture sources differ from the reviewed hashes")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"complementary-pair-{project}-", dir=log.directory.resolve())
    )
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
        "for case in fault control; do\n"
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
        "HOME=/tmp/kicad-complementary-pair-fixtures",
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
        "complementary-pair-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "complementary-pair-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native complementary-pair fixture command failed: {command.stderr or command.error}"
        )

    expected_functions = {
        "J1.1": "StdA_SSTX+",
        "J1.2": "StdA_SSTX-",
        "J1.3": "StdA_SSRX+",
        "J1.4": "StdA_SSRX-",
        "J1.5": "GND",
    }
    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    observed_by_case: dict[str, NetlistContract] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native complementary-pair export omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if observed.pin_functions != expected_functions:
                raise ValueError(
                    "KiCad native export did not preserve the expected Standard-A pin functions: "
                    f"{observed.pin_functions}"
                )
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-usb-superspeed-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())
            observed_by_case[case] = observed

    for case in cases:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native {case} exports differ after netlist normalization")
    for case, expected_findings in (("fault", 1), ("control", 0)):
        report = reports[(case, "first")]
        findings = tuple(
            item for item in report.findings if item.rule_id == "bus.complementary_pair_assignment"
        )
        if len(findings) != expected_findings:
            raise ValueError(
                f"Native {case} expected {expected_findings} complementary-pair findings, "
                f"observed {len(findings)}"
            )
        expected_status = "REVIEW" if expected_findings else "PASS"
        if report.status != expected_status:
            raise ValueError(
                f"Native {case} expected design-lint status {expected_status}, observed "
                f"{report.status}"
            )
        if case == "fault" and (
            findings[0].subject != "J1: USB SuperSpeed RX pair"
            or findings[0].evidence["negative_pins"] != ("J1.4",)
            or findings[0].evidence["negative_nets"]
        ):
            raise ValueError("Native open SSRX- pin did not localize to the expected pair finding")
        log.event(
            f"complementary-pair-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            pin_functions=";".join(
                f"{pin}={function}"
                for pin, function in sorted(observed_by_case[case].pin_functions.items())
            ),
            lint_status=report.status,
            pair_findings=";".join(item.subject for item in findings) or "none",
            repeatable="true",
            repeatability_basis="normalized_netlist_and_design_lint_report",
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
        )
    log.event(
        "complementary-pair-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    if any(
        digest(fixture_root / filename) != source_hashes[case] for case, filename in cases.items()
    ):
        raise ValueError("USB SuperSpeed fixture source changed during native export")
