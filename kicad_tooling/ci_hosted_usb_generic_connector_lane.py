"""Digest-pinned native acceptance for generic connector USB pair coverage."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .ci_hosted_support import HostedLog
from .ci_hosted_usb_generic_connector_cases import (
    USB_GENERIC_CONNECTOR_SOURCE_HASHES,
    usb_generic_connector_fixture_sources,
)
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.design_lint import evaluate
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.models import DesignLintPolicy
from .hwrepo.native_report_parsing import read_netlist

RULE_ID = "bus.usb_generic_connector_phy_pair_review"
SUPERSPEED_RULE_ID = "bus.usb_superspeed_generic_connector_pair_review"
RULE_IDS = (RULE_ID, SUPERSPEED_RULE_ID)


def generic_usb_connector_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
) -> None:
    """Export and compare each synthetic fixture twice with the exact KiCad image."""
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image or config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError("Generic USB connector fixtures require their exact KiCad 10 image")
    image_digest = pinned_image(config.image)
    sources = usb_generic_connector_fixture_sources()
    source_hashes = {case: digest(path) for case, path in sources.items()}
    if source_hashes != USB_GENERIC_CONNECTOR_SOURCE_HASHES:
        raise ValueError("Synthetic generic USB connector fixture source hash changed")

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"usb-generic-connector-{project}-",
            dir=log.directory.resolve(),
        )
    )
    inputs = scratch / "input"
    output = scratch / "output"
    inputs.mkdir()
    output.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} fixture changed while preparing native input")

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    commands = [
        'mkdir -p "$HOME"\n',
        'actual="$(kicad-cli version)"\n',
        f'printf "kicad_version=%s\\n" "$actual"\ntest "$actual" = "{config.kicad_version}"\n',
    ]
    for case in sources:
        commands.append(
            f"for run in first repeat; do kicad-cli sch export netlist --format kicadxml "
            f'--output "/output/{case}.${{run}}.netlist.xml" '
            f'"/fixtures/{case}.kicad_sch"; done\n'
        )
    command = run_command(
        root,
        (
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
            "HOME=/tmp/kicad-usb-generic-fixtures",
            "-v",
            f"{inputs}:/fixtures:ro",
            "-v",
            f"{output}:/output:rw",
            "-w",
            "/fixtures",
            "--entrypoint",
            "/bin/sh",
            image_digest,
            "-ec",
            "".join(commands),
        ),
        timeout=600,
    )
    if command.returncode != 0 or command.error is not None:
        raise ValueError(
            f"Native generic USB connector fixture failed: {command.stderr or command.error}"
        )

    for case in sources:
        normalized_hashes: list[str] = []
        raw_hashes: list[str] = []
        finding_signatures: list[
            tuple[tuple[str, tuple[tuple[str, tuple[tuple[str, tuple[str, ...]], ...]], ...]], ...]
        ] = []
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native generic USB lane omitted {netlist_path.name}")
            raw_hashes.append(digest(netlist_path))
            observed = read_netlist(netlist_path)
            normalized = json.dumps(
                observed.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            normalized_hashes.append(hashlib.sha256(normalized).hexdigest())
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=f"synthetic-usb-generic-connector-{case}",
                observed=observed,
                netlist_sha256=raw_hashes[-1],
            )
            report = evaluate(coach.project_id, coach, DesignLintPolicy())
            finding_signatures.append(
                tuple(
                    (
                        rule_id,
                        tuple(
                            (
                                item.subject,
                                tuple(
                                    sorted(
                                        (key, tuple(values))
                                        for key, values in item.evidence.items()
                                    )
                                ),
                            )
                            for item in report.findings
                            if item.rule_id == rule_id
                        ),
                    )
                    for rule_id in RULE_IDS
                )
            )
        if normalized_hashes[0] != normalized_hashes[1]:
            raise ValueError(f"Native {case} generic USB netlists differ after normalization")
        if finding_signatures[0] != finding_signatures[1]:
            raise ValueError(f"Native {case} generic USB findings differ on repeat export")
        expected_counts = {
            "fault": {RULE_ID: 1, SUPERSPEED_RULE_ID: 0},
            "control": {RULE_ID: 0, SUPERSPEED_RULE_ID: 0},
            "superspeed_fault": {RULE_ID: 0, SUPERSPEED_RULE_ID: 1},
            "superspeed_control": {RULE_ID: 0, SUPERSPEED_RULE_ID: 0},
        }[case]
        first_findings = dict(finding_signatures[0])
        for rule_id, expected_count in expected_counts.items():
            actual_findings = first_findings[rule_id]
            if len(actual_findings) != expected_count:
                raise ValueError(
                    f"Native {case} expected {expected_count} {rule_id} review(s), "
                    f"got {len(actual_findings)}"
                )
        expected_subject = {
            "fault": (RULE_ID, "J1 / U1: generic pins match USB data nets"),
            "superspeed_fault": (
                SUPERSPEED_RULE_ID,
                "J1 / U1: generic pins match USB SuperSpeed TX pair",
            ),
        }.get(case)
        if expected_subject is not None:
            rule_id, subject = expected_subject
            if first_findings[rule_id][0][0] != subject:
                raise ValueError(
                    f"Native {rule_id} finding omitted the expected endpoint pair for {case}"
                )
        event_evidence: dict[str, str] = {}
        if case == "fault":
            _, evidence_items = first_findings[RULE_ID][0]
            other_contacts = dict(evidence_items).get("other_connector_contacts", ())
            expected_other_contacts = (
                "J1.3 function=VBUS nets=unassigned",
                "J1.4 function=GND nets=USB_GND",
            )
            if other_contacts != expected_other_contacts:
                raise ValueError(
                    "Native generic USB fault omitted the exact open VBUS and GND contacts"
                )
            event_evidence["other_connector_contacts"] = json.dumps(
                other_contacts,
                separators=(",", ":"),
            )
        elif case == "superspeed_fault":
            _, evidence_items = first_findings[SUPERSPEED_RULE_ID][0]
            other_contacts = dict(evidence_items).get("other_connector_contacts", ())
            expected_other_contacts = (
                "J1.3 function=GND nets=USB_GND",
                "J1.4 function=VBUS nets=unassigned",
            )
            if other_contacts != expected_other_contacts:
                raise ValueError(
                    "Native USB SuperSpeed fault omitted the exact open VBUS and GND contacts"
                )
            event_evidence["other_connector_contacts"] = json.dumps(
                other_contacts,
                separators=(",", ":"),
            )
        log.event(
            f"usb-generic-connector-fixture/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=image_digest,
            source_sha256=source_hashes[case],
            netlist_sha256=raw_hashes[0],
            repeat_netlist_sha256=raw_hashes[1],
            normalized_netlist_sha256=normalized_hashes[0],
            repeat_normalized_netlist_sha256=normalized_hashes[1],
            usb2_finding_count=expected_counts[RULE_ID],
            superspeed_finding_count=expected_counts[SUPERSPEED_RULE_ID],
            **event_evidence,
        )
