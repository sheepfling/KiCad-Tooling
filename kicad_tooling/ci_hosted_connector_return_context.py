"""Source-bound setup for connector return native regression fixtures."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .hwrepo.contracts import write_model
from .hwrepo.models import DesignLintReport, NetlistContract, ProjectConfig


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
    scratch: Path
    cases: tuple[str, ...]
    source_hashes: dict[str, str]
    reports: dict[tuple[str, str], DesignLintReport]
    observed_contracts: dict[tuple[str, str], NetlistContract]
    netlist_hashes: dict[tuple[str, str], str]
    normalized_netlist_hashes: dict[tuple[str, str], str]


def prepare_connector_return_fixture_context(
    root: Path, project: str, image: str, log: ConnectorReturnLog
) -> ConnectorReturnFixtureContext:
    """Prepare digest-pinned synthetic inputs and repeated native netlist reports."""
    import hashlib

    from .hwrepo.contract_coach import pinned_image, run_command
    from .hwrepo.design_lint import evaluate
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
    fixtures = {
        "fault": fixture_root / "cohort-connector-ground-domains/fault.kicad_sch",
        "control": fixture_root / "cohort-connector-ground-domains/control.kicad_sch",
        "cross-symbol-fault": fixture_root
        / "cohort-cross-symbol-connectors/cross-symbol-fault.kicad_sch",
        "cross-symbol-control": fixture_root
        / "cohort-cross-symbol-connectors/cross-symbol-control.kicad_sch",
        "cross-symbol-open": fixture_root
        / "cohort-cross-symbol-connectors/cross-symbol-open.kicad_sch",
        "mapped-supply-fault": fixture_root
        / "cohort-mapped-connector-supplies/split-supply-fault.kicad_sch",
        "mapped-supply-control": fixture_root
        / "cohort-mapped-connector-supplies/common-supply-control.kicad_sch",
        "channel-power-fault": fixture_root / "cohort-channel-power-names/fault.kicad_sch",
        "channel-power-control": fixture_root / "cohort-channel-power-names/control.kicad_sch",
        "four-db9-fault": fixture_root / "four-port-db9-returns/fault.kicad_sch",
        "four-db9-control": fixture_root / "four-port-db9-returns/control.kicad_sch",
        "four-db9-neutral-fault": fixture_root
        / "four-port-db9-returns/numeric-function-neutral-fault.kicad_sch",
        "four-db9-neutral-control": fixture_root
        / "four-port-db9-returns/numeric-function-neutral-control.kicad_sch",
        "peer-power-fault": fixture_root / "generic-peer-power-pin/fault.kicad_sch",
        "peer-power-control": fixture_root / "generic-peer-power-pin/control.kicad_sch",
        "peer-pin-outlier-fault": fixture_root
        / "generic-peer-pin-assignment-native/fault.kicad_sch",
        "peer-pin-outlier-control": fixture_root
        / "generic-peer-pin-assignment-native/control.kicad_sch",
        "peer-pin-part-id-open-fault": fixture_root
        / "connector-peer-part-id-native/fault.kicad_sch",
        "peer-pin-part-id-common-control": fixture_root
        / "connector-peer-part-id-native/control.kicad_sch",
        "peer-pin-part-id-split-fault": fixture_root
        / "connector-peer-part-id-native/split-assignment-fault.kicad_sch",
        "peer-pin-minority-fault": fixture_root
        / "generic-peer-pin-assignment-native/minority-fault.kicad_sch",
        "peer-pin-divergence-fault": fixture_root
        / "generic-peer-pin-assignment-native/divergence-fault.kicad_sch",
        "generic-placeholder-divergence-fault": fixture_root
        / "generic-peer-pin-assignment-native/generic-placeholder-divergence-fault.kicad_sch",
        "peer-scope-split-return-fault": fixture_root
        / "generic-peer-pin-assignment-native/peer-scope-split-return-fault.kicad_sch",
        "generic-placeholder-control": fixture_root
        / "generic-peer-pin-assignment-native/generic-placeholder-control.kicad_sch",
        "two-peer-open-fault": fixture_root
        / "generic-peer-pin-assignment-native/two-peer-open-fault.kicad_sch",
        "two-peer-no-connect-fault": fixture_root
        / "generic-peer-pin-assignment-native/two-peer-no-connect-fault.kicad_sch",
        "two-peer-common-control": fixture_root
        / "generic-peer-pin-assignment-native/two-peer-common-control.kicad_sch",
        "single-offboard-port-control": fixture_root
        / "generic-peer-pin-assignment-native/single-offboard-port-control.kicad_sch",
        "unconnected-generic-power-input-fault": fixture_root
        / "unconnected-generic-power-input-connector/fault.kicad_sch",
        "unconnected-generic-power-input-control": fixture_root
        / "unconnected-generic-power-input-connector/control.kicad_sch",
        "unconnected-generic-component-power-input-fault": fixture_root
        / "generic-component-power-input/fault.kicad_sch",
        "unconnected-generic-component-power-input-control": fixture_root
        / "generic-component-power-input/control.kicad_sch",
        "unconnected-generic-component-power-input-no-connect-fault": fixture_root
        / "generic-component-power-input/no-connect-fault.kicad_sch",
        "unconnected-generic-component-power-input-dnp-control": fixture_root
        / "generic-component-power-input/dnp-control.kicad_sch",
    }
    cases = tuple(fixtures)
    source_hashes = {case: digest(path) for (case, path) in fixtures.items()}
    expected_source_hashes = {
        "fault": "aea557c738a417192ccfce0e7228b5832aab566f66c2a354dce72f5df7882474",
        "control": "9584fbcc1f0560ac66306691f49d161617199b240cb7520588ad298a69b72176",
        "cross-symbol-fault": "941aa1acc62384d86fe04e7dec77638a5e23cd8b67b196bc1d93130e5e99f21e",
        "cross-symbol-control": "5b9f1a9d18b4e57495d090e815ff192c44f61b8a164ef03622e3d962ac553baf",
        "cross-symbol-open": "180c28fd280b71febe0c636e799217f0d86a3659c45e280cb86a768b7a03533a",
        "mapped-supply-fault": "0991c6df2403df88ff33d5c359b14487b6aa385023bd864573ce236478449213",
        "mapped-supply-control": "c45d390f138ebb9e440a1c6b0fea822f858ce9e31bfa229b28aaddc248adca3b",
        "channel-power-fault": "d6a52dd120801e0bf5776e82421ceb64670b26a9ace28afafd89b608a61aabb3",
        "channel-power-control": "37c7c28963b530a679cd3dc2087a4fa3b5d97dda52250332556406c66b9e1fc7",
        "four-db9-fault": "1baabede29ea7a33cf85ec85f35c3affb2937e31db981e8f5d68f3b769d43791",
        "four-db9-control": "ed2096c8aedbf263290c19c3a067cdf959fac92512aa3ab02fabbd7e10db4171",
        "four-db9-neutral-fault": "8b54babacd735da898cbd477b641a57085ff03b74bf0d9aa665fc8625a36f65f",
        "four-db9-neutral-control": "49e3bca48e79e4b46ce4eba8298026b5c730fca56b119a3ec407dfaafbcf54cd",
        "peer-power-fault": "4e2382aede1643770a466a9c902b1e960f8a8ab0d1bc676a03db33dfe6e582a8",
        "peer-power-control": "e50d57b2739dc49d3b164e0ea141f48835967fdc1982d3cfdd702f671dc7d197",
        "peer-pin-outlier-fault": "e9945c83c351ece43064a6c09c770fd8f3ab5fadd550ac58ee5d001f5d8842e2",
        "peer-pin-outlier-control": "94a9897ea50645a4232abf005477e620a4cd9b12330dfc2d6f32734e8157b8be",
        "peer-pin-part-id-open-fault": "db6f556278611edb21a66f8445f7dfc3a2e456a63783dc3d1e8a79a56a69d478",
        "peer-pin-part-id-common-control": "b8b85aa1fdc8c62547eab58788b120fa6028a8ba65051126f954432f4dd07d2c",
        "peer-pin-part-id-split-fault": "8530bab2ac3537a821be48321e9bb713aa8b2933d714902cc5a30fb4168fa192",
        "peer-pin-minority-fault": "a071543178ad7668d20a3653fea5196cf556c3b96338b81dbeac97a6360ede2c",
        "peer-pin-divergence-fault": "c278b2ff86c869a6dba7c19ee08f064a863d282d251be44fd47c1e8a71254e57",
        "generic-placeholder-divergence-fault": "f6f4c9b419ab590366ca329b1ac0749706b29536017f2f24145de7ef6bdfaf30",
        "peer-scope-split-return-fault": "a597bbdee4794b3de8ff08bce5691363a7a123bde303462d64cb692a6a97968e",
        "generic-placeholder-control": "d63a7f7cd79fd0855de599041dacb8219313ffbb2667f37d1e61e88fbec880c0",
        "two-peer-open-fault": "3de502ac74b394afb21cdaef8130026f11f7aa6050018a571dc65b10ae864350",
        "two-peer-no-connect-fault": "8801b0ff24e9f012e6f2df10247cdc04668db40d3233eb5d2111d279cfdf7256",
        "two-peer-common-control": "ae23ddb802c9a0f5cf30e89699a2cf6f48b3d15b6e18967387e756dcdf6fa3df",
        "single-offboard-port-control": "ceaa7038e372ec74a00f7e7c2cb5311377df01624760ab555adb413c4e02d8e9",
        "unconnected-generic-power-input-fault": "2e16c602d6ba0068360b3f8b493351f6d7e4d7adbe94946d17db883587f0528f",
        "unconnected-generic-power-input-control": "b05c1a3994a4f26f07e18bdfe28c8caaf4a298cbb66b6d1814b20c9a7dce2c13",
        "unconnected-generic-component-power-input-fault": "40271ae0a6551c8c7209427b30e89d9a95267aa92765eaac1a5cdf65e1ffd1a1",
        "unconnected-generic-component-power-input-control": "67d6ad249e1caa2095b3a408457e6a1710fb9bb6ef7d8e5cb1fdcdd7710b43ec",
        "unconnected-generic-component-power-input-no-connect-fault": "664e619ceaba71c27bd7acfaa0bb4563ab3203b33a03c564b2a8f7c6bdf4c4bd",
        "unconnected-generic-component-power-input-dnp-control": "3be52ef83ba54bf0f43bede043095afe42583319e9fd6fa19f17aba250cc3c81",
    }
    if source_hashes != expected_source_hashes:
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
        "connector-return-fixture/native-export",
        "START",
        project=project,
        kicad_version=config.kicad_version,
        image=pinned,
    )
    command = run_command(root, argv, timeout=600)
    write_model(scratch / "native.command.json", command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "connector-return-fixture/native-export",
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
        "connector-return-fixture/native-export",
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
            reports[case, run] = evaluate(project_id, coach, DesignLintPolicy())
    return ConnectorReturnFixtureContext(
        root=root,
        project=project,
        config=config,
        pinned=pinned,
        log=log,
        scratch=scratch,
        cases=cases,
        source_hashes=source_hashes,
        reports=reports,
        observed_contracts=observed_contracts,
        netlist_hashes=netlist_hashes,
        normalized_netlist_hashes=normalized_netlist_hashes,
    )
