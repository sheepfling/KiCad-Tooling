"""Run digest-pinned native fault/control exports for generic connector lints."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from .ci_hosted_support import HostedLog
from .hwrepo.contract_coach import pinned_image, run_command
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.design_lint import evaluate
from .hwrepo.design_lint_policy_models import DesignLintPolicy
from .hwrepo.electrical import selected_config
from .hwrepo.evidence import digest
from .hwrepo.native_report_parsing import read_netlist
from .hwrepo.netlist_contract_models import NetlistContract

RoleEvidence = tuple[str, str, str, str, str]


def generic_connector_fixture_lane(
    root: Path,
    *,
    project: str,
    image: str,
    log: HostedLog,
    protocol: str,
    rule_id: str,
    source_hashes: Mapping[str, str],
    fixture_sources: Mapping[str, Path],
    expected_subject: str,
    role_evidence: tuple[RoleEvidence, ...],
    expected_evidence: tuple[tuple[str, tuple[str, ...]], ...] = (),
) -> dict[str, NetlistContract]:
    """Export each synthetic source twice, verify evidence, and retain typed observations.

    Each role tuple is ``(label, net_key, connector_pins_key, endpoint_pin,
    connector_pin)``. ``expected_evidence`` requires additional exact native
    finding fields. Protocol wrappers own the rule and fixture identity.
    """
    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image or config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError("Generic connector fixtures require their exact KiCad 10 image")
    image_digest = pinned_image(config.image)
    sources = dict(fixture_sources)
    observed_hashes = {case: digest(path) for case, path in sources.items()}
    if observed_hashes != dict(source_hashes) or set(sources) != {"fault", "control"}:
        raise ValueError(f"Synthetic generic {protocol} connector fixture source hash changed")

    scratch = Path(
        tempfile.mkdtemp(
            prefix=f"{protocol}-generic-connector-{project}-",
            dir=log.directory.resolve(),
        )
    )
    inputs = scratch / "input"
    output = scratch / "output"
    inputs.mkdir()
    output.mkdir()
    for case, source in sources.items():
        shutil.copyfile(source, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != observed_hashes[case]:
            raise ValueError(f"Synthetic {case} fixture changed while preparing native input")

    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    commands = [
        'mkdir -p "$HOME"\n',
        'actual="$(kicad-cli version)"\n',
        f'printf "kicad_version=%s\\n" "$actual"\ntest "$actual" = "{config.kicad_version}"\n',
    ]
    native_observations: dict[str, NetlistContract] = {}
    for case in sources:
        commands.append(
            "for run in first repeat; do kicad-cli sch export netlist --format kicadxml "
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
            f"HOME=/tmp/kicad-{protocol}-generic-fixtures",
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
            f"Native generic {protocol} connector fixture failed: {command.stderr or command.error}"
        )

    for case in sources:
        normalized_hashes: list[str] = []
        raw_hashes: list[str] = []
        finding_signatures: list[
            tuple[tuple[str, tuple[tuple[str, tuple[str, ...]], ...]], ...]
        ] = []
        observations: list[NetlistContract] = []
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native generic {protocol} lane omitted {netlist_path.name}")
            raw_hashes.append(digest(netlist_path))
            observed = read_netlist(netlist_path)
            observations.append(observed)
            serialized = BaseModel.model_dump(observed, mode="json")
            normalized = json.dumps(serialized, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
            normalized_hashes.append(hashlib.sha256(normalized).hexdigest())
            project_id = f"synthetic-{protocol}-generic-connector-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=raw_hashes[-1],
            )
            report = evaluate(project_id, coach, DesignLintPolicy())
            findings = tuple(item for item in report.findings if item.rule_id == rule_id)
            finding_signatures.append(
                tuple(
                    (
                        item.subject,
                        tuple(
                            sorted((key, tuple(values)) for key, values in item.evidence.items())
                        ),
                    )
                    for item in findings
                )
            )
        if normalized_hashes[0] != normalized_hashes[1]:
            raise ValueError(
                f"Native {case} generic {protocol} netlists differ after normalization"
            )
        if finding_signatures[0] != finding_signatures[1]:
            raise ValueError(f"Native {case} generic {protocol} findings differ on repeat export")
        expected_count = 1 if case == "fault" else 0
        if len(finding_signatures[0]) != expected_count:
            raise ValueError(
                f"Native {case} expected {expected_count} generic {protocol} review(s), "
                f"got {len(finding_signatures[0])}"
            )
        if case == "fault":
            if finding_signatures[0][0][0] != expected_subject:
                raise ValueError(f"Native generic {protocol} finding omitted the exact pin group")
            evidence = dict(finding_signatures[0][0][1])
            observed = observations[0]
            for evidence_key, expected_values in expected_evidence:
                if evidence.get(evidence_key) != expected_values:
                    raise ValueError(
                        f"Native {protocol} candidate did not retain the expected "
                        f"{evidence_key} evidence"
                    )
            for label, net_key, pins_key, endpoint_pin, connector_pin in role_evidence:
                matching_nets = tuple(
                    net
                    for net, pins in observed.nets.items()
                    if {endpoint_pin, connector_pin} <= set(pins)
                )
                if len(matching_nets) != 1:
                    raise ValueError(
                        f"Native {protocol} fixture did not assign {endpoint_pin} and "
                        f"{connector_pin} to one exact net"
                    )
                if evidence.get(net_key) != (matching_nets[0],):
                    raise ValueError(f"Native {protocol} candidate omitted the exact {label} net")
                if evidence.get(pins_key) != (connector_pin,):
                    raise ValueError(f"Native {protocol} candidate omitted generic {label} contact")
        log.event(
            f"generic-connector/{protocol}/{case}",
            "PASS",
            project=project,
            kicad_version=config.kicad_version,
            image=image_digest,
            source_sha256=observed_hashes[case],
            netlist_sha256=raw_hashes[0],
            repeat_netlist_sha256=raw_hashes[1],
            normalized_netlist_sha256=normalized_hashes[0],
            repeat_normalized_netlist_sha256=normalized_hashes[1],
            finding_count=expected_count,
        )
        native_observations[case] = observations[0]
    return native_observations
