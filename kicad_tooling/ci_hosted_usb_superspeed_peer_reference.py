"""Pinned native acceptance for USB SuperSpeed peer-reference review."""

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

_EXPECTED_SOURCE_HASHES = {
    "fault": "4eab8226ec5b526a16c880453f54202bb3df9b42b444bd82684d92fd7720c095",
    "control": "5b8bd68163f9493c91c643b55d283f9514522ccc67b2cc7e37955e83e0b7b400",
}
_EXPECTED_PIN_FUNCTIONS = {
    "J1.1": "StdA_SSTX+",
    "J1.2": "StdA_SSTX-",
    "J1.3": "StdA_SSRX+",
    "J1.4": "StdA_SSRX-",
    "J1.5": "GND",
    "U1.1": "SSRX+",
    "U1.2": "SSRX-",
    "U1.3": "SSTX+",
    "U1.4": "SSTX-",
    "U1.5": "AGND",
}
_EXPECTED_NET_MEMBERS = {
    "ss_tx_p": frozenset({"j1.1", "u1.1"}),
    "ss_tx_n": frozenset({"j1.2", "u1.2"}),
    "ss_rx_p": frozenset({"j1.3", "u1.3"}),
    "ss_rx_n": frozenset({"j1.4", "u1.4"}),
}
_EXPECTED_REFERENCE_NET_MEMBERS = {
    "fault": {
        "usb_gnd": frozenset({"j1.5"}),
        "phy_gnd": frozenset({"u1.5"}),
    },
    "control": {"board_gnd": frozenset({"j1.5", "u1.5"})},
}
_EXPECTED_FAMILIES = frozenset(
    {
        ("USB SuperSpeed TX", "USB SuperSpeed RX"),
        ("USB SuperSpeed RX", "USB SuperSpeed TX"),
    }
)
_EXPECTED_UNRELATED_FINDINGS = frozenset(
    {
        ("signal.named_pair_without_reviewed_requirement", "SS_RX_P / SS_RX_N"),
        ("signal.named_pair_without_reviewed_requirement", "SS_TX_P / SS_TX_N"),
    }
)


def usb_superspeed_peer_reference_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Check split/common references on both full-duplex paths with pinned KiCad."""
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
        raise ValueError(
            f"USB SuperSpeed peer-reference fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)

    fixture_root = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/design_lint/usb-superspeed-peer-reference-native"
    )
    cases = {case: fixture_root / f"{case}.kicad_sch" for case in _EXPECTED_SOURCE_HASHES}
    source_hashes = {case: digest(path) for case, path in cases.items()}
    if source_hashes != _EXPECTED_SOURCE_HASHES:
        raise ValueError(
            "USB SuperSpeed peer-reference fixture sources differ from reviewed hashes"
        )

    scratch = Path(
        tempfile.mkdtemp(prefix=f"usb-superspeed-peer-reference-{project}-", dir=log.directory)
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, source_path in cases.items():
        shutil.copyfile(source_path, inputs / source_path.name)
        if digest(inputs / source_path.name) != source_hashes[case]:
            raise ValueError(f"Synthetic {case} fixture changed while preparing native input")
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
        "HOME=/tmp/kicad-usb-superspeed-peer-fixtures",
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
    receipt_path = scratch / "native.command.json"
    stage = "usb-superspeed-peer-reference-fixture/native-export"
    log.event(stage, "START", project=project, kicad_version=config.kicad_version, image=pinned)
    command = run_command(root, argv, timeout=600)
    write_model(receipt_path, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            stage,
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=receipt_path.relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native USB SuperSpeed fixture command failed: {command.stderr or command.error}"
        )

    normalized_hashes: dict[tuple[str, str], str] = {}
    raw_hashes: dict[tuple[str, str], str] = {}
    reports: dict[tuple[str, str], DesignLintReport] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native USB SuperSpeed export omitted {netlist_path.name}")
            raw_hashes[(case, run)] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            if observed.pin_functions != _EXPECTED_PIN_FUNCTIONS:
                raise ValueError(
                    f"Native USB SuperSpeed export changed pin functions: {observed.pin_functions}"
                )
            observed_members = {
                name.casefold(): frozenset(pin.casefold() for pin in pins)
                for name, pins in observed.nets.items()
            }
            if any(
                observed_members.get(net) != expected
                for net, expected in {
                    **_EXPECTED_NET_MEMBERS,
                    **_EXPECTED_REFERENCE_NET_MEMBERS[case],
                }.items()
            ):
                raise ValueError(
                    f"Native USB SuperSpeed export changed direct pair membership: {observed.nets}"
                )

            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_hashes[(case, run)] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-usb-superspeed-peer-reference-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[(case, run)],
            )
            reports[(case, run)] = evaluate(project_id, coach, DesignLintPolicy())

    for case in cases:
        if normalized_hashes[(case, "first")] != normalized_hashes[(case, "repeat")]:
            raise ValueError(f"Native USB SuperSpeed {case} exports differ after normalization")

    for case, expected_findings in (("fault", 2), ("control", 0)):
        report = reports[(case, "first")]
        findings = tuple(
            item for item in report.findings if item.rule_id == "bus.usb_peer_reference_review"
        )
        coverage = report.usb_peer_reference_coverage
        if coverage is None or coverage.path_entries is None:
            raise ValueError(f"Native {case} export did not produce USB path coverage")
        families = frozenset(
            (item.data_path.connector_signal_family, item.data_path.phy_signal_family)
            for item in coverage.path_entries
        )
        if (
            len(findings) != expected_findings
            or coverage.supported_data_path_count != 2
            or families != _EXPECTED_FAMILIES
        ):
            raise ValueError(
                f"Native {case} expected two full-duplex SuperSpeed paths and "
                f"{expected_findings} reference findings; observed {len(findings)} findings "
                f"and paths {sorted(families)}"
            )
        unrelated_findings = frozenset(
            (item.rule_id, item.subject)
            for item in report.findings
            if item.rule_id != "bus.usb_peer_reference_review"
        )
        if unrelated_findings != _EXPECTED_UNRELATED_FINDINGS:
            raise ValueError(
                f"Native {case} fixture produced unexpected non-reference findings: "
                f"{sorted(unrelated_findings)}"
            )
        if case == "fault":
            if (
                report.status != "REVIEW"
                or coverage.separate_reference_path_count != 2
                or coverage.common_reference_path_count != 0
                or {
                    (
                        item.evidence["USB_connector_pair_family"][0],
                        item.evidence["USB_PHY_pair_family"][0],
                    )
                    for item in findings
                }
                != set(_EXPECTED_FAMILIES)
            ):
                raise ValueError(
                    "Native split-reference fault did not identify both direction pairs"
                )
        elif (
            coverage.common_reference_path_count != 2 or coverage.separate_reference_path_count != 0
        ):
            raise ValueError("Native common-reference control did not resolve both direction pairs")

        links = ";".join(
            sorted(
                f"{item.data_path.connector_signal_family}->{item.data_path.phy_signal_family}"
                for item in coverage.path_entries
            )
        )
        reference_nets = ";".join(
            sorted(
                {
                    f"{item.connector_reference_net}->{item.phy_reference_net}"
                    for item in coverage.path_entries
                }
            )
        )
        log.event(
            f"usb-superspeed-peer-reference-fixture/{case}",
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
            rule_status="REVIEW" if findings else "PASS",
            reference_findings=";".join(sorted(item.subject for item in findings)) or "none",
            reference_nets=reference_nets,
            other_findings=";".join(
                f"{rule_id}:{subject}" for rule_id, subject in sorted(unrelated_findings)
            ),
            pair_families=links,
            common_reference_paths=coverage.common_reference_path_count,
            separate_reference_paths=coverage.separate_reference_path_count,
            repeatable="true",
            repeatability_basis="normalized_netlist_and_design_lint_report",
            command_receipt=receipt_path.relative_to(root).as_posix(),
        )

    if any(digest(path) != source_hashes[case] for case, path in cases.items()):
        raise ValueError("USB SuperSpeed peer-reference source changed during native export")
    log.event(
        stage,
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=";".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=receipt_path.relative_to(root).as_posix(),
    )
