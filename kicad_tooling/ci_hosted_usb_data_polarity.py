"""Digest-pinned native export lane for USB data pin/name polarity review."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .hwrepo.contracts import write_model

if TYPE_CHECKING:
    from .ci_hosted_support import HostedLog


def usb_data_polarity_fixture_lane(root: Path, *, project: str, image: str, log: HostedLog) -> None:
    """Check a crossed connector pair and matching control using repeated native exports."""
    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.design_lint_report_models import DesignLintReport
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import ContractCoachReport, DesignLintPolicy
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(f"USB data polarity fixtures do not cover KiCad {config.kicad_version}")
    pinned = pinned_image(config.image)
    repository = Path(__file__).resolve().parents[1]
    sources = {
        "control": repository
        / "tests/fixtures/design_lint/usb-data-path-native/integrated-phy-direct.kicad_sch",
        "fault": repository
        / "tests/fixtures/design_lint/usb-data-polarity-native/reversed-connector-pair.kicad_sch",
        "pair-control": repository
        / "tests/fixtures/design_lint/usb-data-pair-crossing-native/control.kicad_sch",
        "pair-fault": repository
        / "tests/fixtures/design_lint/usb-data-pair-crossing-native/fault.kicad_sch",
    }
    expected_source_hashes = {
        "control": "e93371b78de2ba8c473ccde0579e551d0da0b44b5d9ed417473ab1dd63781d27",
        "fault": "c3586926cfb20926b90160f7b9823fcb9e5c955a17c35babd450aca183c08c7e",
        "pair-control": "e0cf5d7a0f585b025ad4dc28861a19d37e1af78b79da518ff6032fd32e97c239",
        "pair-fault": "29b47ef57440ff01c634efa31192fbe89b2af06bfc8ae95c563a28b847a30bdb",
    }
    source_hashes = {case: digest(path) for case, path in sources.items()}
    if source_hashes != expected_source_hashes:
        raise ValueError("USB data polarity fixtures differ from their reviewed source hashes")

    scratch = Path(
        tempfile.mkdtemp(prefix=f"usb-data-polarity-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source in sources.items():
        target = inputs / f"{case}.kicad_sch"
        shutil.copyfile(source, target)
        if digest(target) != source_hashes[case]:
            raise ValueError(f"Synthetic {case} schematic changed while preparing native input")
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
        "for case in control fault pair-control pair-fault; do\n"
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
        "HOME=/tmp/kicad-usb-polarity-fixtures",
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
        "usb-data-polarity-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "usb-data-polarity-fixture/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=receipt.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native USB data polarity export failed: {command.stderr or command.error}"
        )
    log.event(
        "usb-data-polarity-fixture/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in sorted(sources)),
        command_receipt=receipt.relative_to(root).as_posix(),
    )

    normalized_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    for case in sources:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native USB polarity export omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-usb-data-polarity-{case}"
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
        raise ValueError("Native USB polarity exports differ after netlist normalization")

    polarity_rule_id = "bus.usb_data_polarity_label_mismatch"
    crossing_rule_id = "bus.usb_peer_data_pair_crossed"
    expected_subjects = ("J1.1: D+ on USB_D-", "J1.2: D- on USB_D+")
    for case in ("control", "fault"):
        report = reports[(case, "first")]
        findings = tuple(item for item in report.findings if item.rule_id == polarity_rule_id)
        subjects = tuple(item.subject for item in findings)
        expected = expected_subjects if case == "fault" else ()
        if subjects != expected:
            raise ValueError(
                f"Native USB polarity {case} produced {subjects!r}; expected {expected!r}"
            )
        if any(item.rule_id == "bus.complementary_pair_assignment" for item in report.findings):
            raise ValueError("Complete USB pair should remain outside pair-completeness findings")
        log.event(
            f"usb-data-polarity-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[(case, "first")],
            repeat_netlist_sha256=raw_hashes[(case, "repeat")],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            repeatable="true",
            lint_status=report.status,
            polarity_findings=";".join(subjects) if subjects else "none",
        )

    expected_crossing = {
        "pair-control": (),
        "pair-fault": ("J1 / U1: USB 2.0 data pair is crossed",),
    }
    for case, expected in expected_crossing.items():
        report = reports[(case, "first")]
        crossing_findings = tuple(
            item for item in report.findings if item.rule_id == crossing_rule_id
        )
        subjects = tuple(item.subject for item in crossing_findings)
        if subjects != expected:
            raise ValueError(
                f"Native USB pair crossing {case} produced {subjects!r}; expected {expected!r}"
            )
        if any(item.rule_id == polarity_rule_id for item in report.findings):
            raise ValueError(
                "Neutral USB data route names must not duplicate label-polarity review"
            )
        log.event(
            f"usb-data-pair-crossing-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            source_sha256=source_hashes[case],
            normalized_netlist_sha256=normalized_hashes[(case, "first")],
            repeat_normalized_netlist_sha256=normalized_hashes[(case, "repeat")],
            repeatable="true",
            lint_status=report.status,
            crossing_findings=";".join(subjects) if subjects else "none",
        )

    log.finish()
