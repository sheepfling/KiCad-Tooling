"""Source-bound setup for connector return native regression fixtures."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .ci_hosted_connector_return_fixture_sources import (
    CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES,
    connector_return_fixture_sources,
)
from .hwrepo.contracts import write_model
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.design_lint_rule_types import DesignLintRuleId
from .hwrepo.models import (
    NetlistContract,
    ProjectConfig,
)


class ConnectorReturnLog(Protocol):
    directory: Path

    def event(self, stage: str, status: str, **details: str | float) -> None: ...


@dataclass(slots=True)
class ConnectorReturnFixtureContext:
    root: Path
    project: str
    config: ProjectConfig
    pinned: str
    log: ConnectorReturnLog
    stage_prefix: str
    scratch: Path
    cases: tuple[str, ...]
    source_hashes: dict[str, str]
    reports: dict[tuple[str, str], DesignLintReport]
    observed_contracts: dict[tuple[str, str], NetlistContract]
    netlist_hashes: dict[tuple[str, str], str]
    normalized_netlist_hashes: dict[tuple[str, str], str]


def prepare_connector_return_fixture_context(
    root: Path,
    project: str,
    image: str,
    log: ConnectorReturnLog,
    *,
    case_names: tuple[str, ...] | None = None,
    stage_prefix: str = "connector-return-fixture",
    rule_overrides_by_case: Mapping[str, tuple[DesignLintRuleId, ...]] | None = None,
) -> ConnectorReturnFixtureContext:
    """Prepare digest-pinned synthetic inputs and repeated native netlist reports."""
    import hashlib

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
    from .hwrepo.design_lint_finding_models import DesignLintRuleOverride
    from .hwrepo.electrical import selected_config
    from .hwrepo.evidence import digest
    from .hwrepo.models import (
        ContractCoachReport,
        DesignLintPolicy,
    )
    from .validate import read_netlist

    root = root.resolve()
    config = selected_config(root, project)
    if config.image != image:
        raise ValueError(f"{project}: native fixture image differs from its reviewed toolchain")
    if config.kicad_version not in {"10.0.0", "10.0.5"}:
        raise ValueError(
            f"Connector return lint fixtures do not cover KiCad {config.kicad_version}"
        )
    pinned = pinned_image(config.image)
    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    fixture_sources = connector_return_fixture_sources(fixture_root)
    cases = tuple(fixture_sources) if case_names is None else tuple(case_names)
    if not cases or len(set(cases)) != len(cases):
        raise ValueError("Connector-return fixture cases must be a non-empty unique sequence")
    if not stage_prefix or stage_prefix.startswith("/") or stage_prefix.endswith("/"):
        raise ValueError("Connector-return fixture stage prefix must be a non-empty relative name")
    unknown_cases = tuple(case for case in cases if case not in fixture_sources)
    if unknown_cases:
        raise ValueError(f"Unknown connector-return fixture cases: {unknown_cases}")
    overrides = {} if rule_overrides_by_case is None else dict(rule_overrides_by_case)
    unknown_override_cases = tuple(case for case in overrides if case not in cases)
    if unknown_override_cases:
        raise ValueError(f"Rule overrides name cases outside this lane: {unknown_override_cases}")
    if any(not rule_ids or len(set(rule_ids)) != len(rule_ids) for rule_ids in overrides.values()):
        raise ValueError("Per-case native fixture rule overrides must be non-empty and unique")
    fixtures = {case: fixture_sources[case] for case in cases}
    source_hashes = {case: digest(path) for (case, path) in fixtures.items()}
    expected_source_hashes = CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES
    reviewed_source_hashes = {case: expected_source_hashes[case] for case in cases}
    if source_hashes != reviewed_source_hashes:
        raise ValueError("Connector-return fixture sources differ from the reviewed hashes")
    scratch = Path(
        tempfile.mkdtemp(prefix=f"connector-return-{project}-", dir=log.directory.resolve())
    )
    inputs = scratch / "input"
    inputs.mkdir()
    for case, fixture in fixtures.items():
        shutil.copyfile(fixture, inputs / f"{case}.kicad_sch")
        if digest(inputs / f"{case}.kicad_sch") != source_hashes[case]:
            raise ValueError(f"Synthetic {case} fixture changed while preparing native input")
    output = scratch / "output"
    output.mkdir()
    user: tuple[str, ...] = ()
    if sys.platform != "win32":
        user = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = f'''mkdir -p "$HOME"\nactual="$(kicad-cli version)"\nprintf "kicad_version=%s\\n" "$actual"\ntest "$actual" = "{config.kicad_version}"\nfor case in {" ".join(cases)}; do\n  for run in first repeat; do\n    kicad-cli sch export netlist --format kicadxml       --output "/output/${{case}}.${{run}}.netlist.xml"       "/fixtures/${{case}}.kicad_sch"\n  done\ndone\n'''
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
        "HOME=/tmp/kicad-connector-fixtures",
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
        f"{stage_prefix}/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            f"{stage_prefix}/native-export",
            "FAIL",
            project=project,
            kicad_version=config.kicad_version,
            image=pinned,
            command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        raise ValueError(
            f"Native connector fixture command failed: {command.stderr or command.error}"
        )
    log.event(
        f"{stage_prefix}/native-export",
        "PASS",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
        source_hashes=",".join(f"{case}:{source_hashes[case]}" for case in cases),
        command_receipt=(scratch / "native.command.json").relative_to(root).as_posix(),
    )
    if any(
        digest(fixtures[case]) != source_hashes[case]
        or digest(inputs / f"{case}.kicad_sch") != source_hashes[case]
        for case in cases
    ):
        raise ValueError("Synthetic connector fixture source changed during native export")
    reports: dict[tuple[str, str], DesignLintReport] = {}
    observed_contracts: dict[tuple[str, str], NetlistContract] = {}
    netlist_hashes: dict[tuple[str, str], str] = {}
    normalized_netlist_hashes: dict[tuple[str, str], str] = {}
    for case in cases:
        for run in ("first", "repeat"):
            netlist_path = output / f"{case}.{run}.netlist.xml"
            if not netlist_path.is_file():
                raise ValueError(f"Native connector fixture omitted {netlist_path.name}")
            netlist_hashes[case, run] = digest(netlist_path)
            observed = read_netlist(netlist_path)
            observed_contracts[case, run] = observed
            normalized = json.dumps(
                observed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized_netlist_hashes[case, run] = hashlib.sha256(normalized).hexdigest()
            project_id = f"synthetic-connector-returns-{case}"
            coach = ContractCoachReport(
                status="READY_FOR_REVIEW",
                project_id=project_id,
                observed=observed,
                netlist_sha256=netlist_hashes[case, run],
            )
            policy = DesignLintPolicy()
            if case in {"stateful-contact-fault", "stateful-contact-control"}:
                from .hwrepo.connector_stateful_contact_models import (
                    ConnectorStatefulContactMap,
                )

                policy = DesignLintPolicy(
                    connector_stateful_contact_map=ConnectorStatefulContactMap.model_validate_json(
                        json.dumps(
                            {
                                "basis": "Synthetic exact audio-jack contact map for native lint regression",
                                "requirements": [
                                    {
                                        "id": "synthetic-audio-jack-contact-map",
                                        "reference": "J1",
                                        "expected_symbol": "Synthetic:AudioJack_2Contact",
                                        "expected_value": "Synthetic Audio Jack",
                                        "expected_footprint": "Synthetic:AudioJack_2Contact",
                                        "expected_part_id": "SYNTH-AUDIO-JACK-001",
                                        "native_pin_numbers": ["1", "2"],
                                        "contact_pairs": [
                                            {
                                                "id": "tip-normal-contact",
                                                "first_pin": "1",
                                                "second_pin": "2",
                                                "closed_when": "plug_removed",
                                                "source_basis": "Synthetic fixture contact table",
                                            }
                                        ],
                                    }
                                ],
                            }
                        )
                    ),
                    rules=(
                        DesignLintRuleOverride(
                            rule_id="connector.stateful_contact_topology_mismatch",
                            mode="review",
                            reason="Synthetic native fixture explicitly enables the mapped contact check",
                        ),
                    ),
                )
            if case in {
                "all-open-generic-peer-fault",
                "all-open-generic-peer-control",
                "all-open-generic-signal-peer-fault",
                "all-open-generic-signal-peer-control",
                "all-open-generic-signal-types-fault",
                "all-open-generic-signal-types-control",
                "part-id-all-open-generic-peer-fault",
                "footprint-alias-all-open-fault",
                "component-peer-assignment-outlier-fault",
                "component-peer-assignment-outlier-control",
            }:
                rule_id = (
                    "component.generic_peer_pin_assignment_outlier"
                    if case.startswith("component-peer-assignment-outlier-")
                    else "connector.footprint_peer_pin_all_open"
                    if case == "footprint-alias-all-open-fault"
                    else "connector.generic_peer_pin_all_open"
                )
                policy = DesignLintPolicy(
                    rules=(
                        DesignLintRuleOverride(
                            rule_id=rule_id,
                            mode="review",
                            reason="Synthetic native fixture explicitly enables the opt-in heuristic",
                        ),
                    )
                )
            extra_rule_ids = overrides.get(case, ())
            if extra_rule_ids:
                existing_rule_ids = {item.rule_id for item in policy.rules}
                if existing_rule_ids.intersection(extra_rule_ids):
                    raise ValueError(
                        f"Duplicate rule override configured for native fixture {case}"
                    )
                policy = policy.model_copy(
                    update={
                        "rules": (
                            *policy.rules,
                            *(
                                DesignLintRuleOverride(
                                    rule_id=rule_id,
                                    mode="review",
                                    reason="Synthetic native fixture explicitly enables the opt-in heuristic",
                                )
                                for rule_id in extra_rule_ids
                            ),
                        )
                    }
                )
            reports[case, run] = evaluate(project_id, coach, policy)
    return ConnectorReturnFixtureContext(
        root=root,
        project=project,
        config=config,
        pinned=pinned,
        log=log,
        stage_prefix=stage_prefix,
        scratch=scratch,
        cases=cases,
        source_hashes=source_hashes,
        reports=reports,
        observed_contracts=observed_contracts,
        netlist_hashes=netlist_hashes,
        normalized_netlist_hashes=normalized_netlist_hashes,
    )
