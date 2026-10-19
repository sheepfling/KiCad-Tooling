"""Focused exact-version acceptance for synthetic DB9 return contracts."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.models import CommandEvidence, DesignLintPolicy, NetlistContract
from tests.design_lint_fixtures.connector_peer_pin_cases import peer_pin_case_contracts
from tests.design_lint_fixtures.connector_return_cases import return_case_contracts
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
]


def _assert_db9_contract_results(results: dict[str, dict[str, str]], version: str) -> None:
    prefix = "connector-return-fixture/"
    expected_contracts = {
        "ground-contract-common-fault": "FAIL",
        "ground-contract-common-control": "PASS",
        "ground-contract-isolated-fault": "PASS",
        "ground-contract-isolated-control": "FAIL",
        "pin-connectivity-contract-common-fault": "FAIL",
        "pin-connectivity-contract-common-control": "PASS",
        "pin-connectivity-contract-isolated-fault": "PASS",
        "pin-connectivity-contract-isolated-control": "FAIL",
        "pin-connectivity-contract-assignment-only-split-control": "PASS",
        "pin-connectivity-contract-assignment-only-common-control": "PASS",
    }
    for stage, expected_status in expected_contracts.items():
        result = results[f"{prefix}{stage}"]
        assert result["status"] == "PASS"
        assert result["contract_status"] == expected_status
        assert result["kicad_version"] == version
        assert result["repeatable"] == "true"
        digest_key = (
            "grounding_contract_sha256"
            if stage.startswith("ground-contract-")
            else "pin_connectivity_contract_sha256"
        )
        assert re.fullmatch(r"[0-9a-f]{64}", result[digest_key])


def test_combined_grounding_verifier_keeps_peer_power_and_stale_pin_cases() -> None:
    from kicad_tooling.ci_hosted_connector_return_grounding import (
        verify_connector_grounding_contracts,
    )

    observed = {**return_case_contracts(), **peer_pin_case_contracts()}
    cases = (
        "four-db9-fault",
        "four-db9-control",
        "peer-pin-outlier-fault",
        "peer-pin-outlier-control",
        "peer-power-fault",
        "peer-power-control",
    )
    selected = {case: observed[case] for case in cases}
    root = Path.cwd()
    log = HostedLog(root, "grounding-contract-unit")
    config = SimpleNamespace(kicad_version="10.0.0")
    digest = "a" * 64
    context = SimpleNamespace(
        root=root,
        project="synthetic",
        config=config,
        pinned="fixture.invalid/kicad@sha256:" + digest,
        log=log,
        scratch=root,
        source_hashes={case: digest for case in cases},
        netlist_hashes={(case, run): digest for case in cases for run in ("first", "repeat")},
        normalized_netlist_hashes={
            (case, run): digest for case in cases for run in ("first", "repeat")
        },
        observed_contracts={
            (case, run): contract
            for case, contract in selected.items()
            for run in ("first", "repeat")
        },
    )

    verify_connector_grounding_contracts(
        context,
        selected["four-db9-control"].nets,
    )

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {item["stage"].rsplit("/", 1)[-1]: item for item in events}
    assert results["ground-contract-common-fault"]["contract_status"] == "FAIL"
    assert results["ground-contract-isolated-fault"]["contract_status"] == "PASS"
    assert results["pin-connectivity-contract-peer-common-open-fault"]["contract_status"] == "FAIL"
    assert results["pin-connectivity-contract-peer-common-control"]["contract_status"] == "PASS"
    assert (
        results["pin-connectivity-contract-peer-independent-control"]["checks"].split(";")[0]
        == "pin-connectivity/peer-independent-outputs-assigned=PASS"
    )
    assert (
        results["pin-connectivity-contract-peer-independent-control"]["contract_status"] == "PASS"
    )
    assert (
        results["pin-connectivity-contract-peer-independent-common-net-mismatch"]["contract_status"]
        == "FAIL"
    )
    assert results["pin-connectivity-contract-stale-pin-reference"]["contract_status"] == "FAIL"


def test_db9_return_lane_exports_only_fault_and_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kicad_tooling.ci_hosted_connector_return_lane import db9_return_contract_fixture_lane

    root = tmp_path.resolve()
    image = PINNED_NATIVE_KICAD_IMAGES["10.0.0"]
    config = SimpleNamespace(image=image, kicad_version="10.0.0")
    observed = return_case_contracts()
    cases = ("four-db9-fault", "four-db9-control")

    def fake_run_command(root: Path, argv: tuple[str, ...], timeout: int) -> CommandEvidence:
        assert root == tmp_path.resolve()
        assert timeout == 600
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert argv[argv.index("--entrypoint") + 1] == "/bin/sh"
        assert argv[argv.index("--platform") + 1] == "linux/amd64"
        assert image in argv

        mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
        source_mount = next(item for item in mounts if item.endswith(":/fixtures:ro"))
        output_mount = next(item for item in mounts if item.endswith(":/output:rw"))
        source_directory = Path(source_mount.removesuffix(":/fixtures:ro"))
        output_directory = Path(output_mount.removesuffix(":/output:rw"))
        assert {item.name for item in source_directory.iterdir()} == {
            f"{case}.kicad_sch" for case in cases
        }
        for case in cases:
            for run in ("first", "repeat"):
                (output_directory / f"{case}.{run}.netlist.xml").write_text(
                    f"synthetic {case} export {run}\n", encoding="utf-8"
                )
        return CommandEvidence(
            argv=argv,
            started_utc="2026-10-12T00:00:00+00:00",
            returncode=0,
            stdout="kicad_version=10.0.0\n",
        )

    def fake_read_netlist(path: Path) -> NetlistContract:
        return observed[path.name.split(".", 1)[0]]

    monkeypatch.setattr("kicad_tooling.hwrepo.electrical.selected_config", lambda *_args: config)
    monkeypatch.setattr("kicad_tooling.hwrepo.contract_coach.run_command", fake_run_command)
    monkeypatch.setattr("kicad_tooling.validate.read_netlist", fake_read_netlist)

    log = HostedLog(root, "db9-return-contract-unit")
    db9_return_contract_fixture_lane(root, project="synthetic", image=image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    prefix = "connector-return-fixture/"
    results = {item["stage"]: item for item in events if item["stage"].startswith(prefix)}
    assert {stage.removeprefix(prefix) for stage in results} == {
        "native-export",
        "four-db9-fault",
        "four-db9-control",
        "ground-contract-common-fault",
        "ground-contract-common-control",
        "ground-contract-isolated-fault",
        "ground-contract-isolated-control",
        "pin-connectivity-contract-common-fault",
        "pin-connectivity-contract-common-control",
        "pin-connectivity-contract-isolated-fault",
        "pin-connectivity-contract-isolated-control",
        "pin-connectivity-contract-assignment-only-split-control",
        "pin-connectivity-contract-assignment-only-common-control",
    }
    assert results[f"{prefix}four-db9-fault"]["lint_status"] == "REVIEW"
    assert results[f"{prefix}four-db9-control"]["lint_status"] == "PASS"
    _assert_db9_contract_results(results, "10.0.0")


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_DB9_RETURN_CONTRACT_FIXTURES") != "1",
    reason="focused DB9 native fixtures run in the digest-pinned acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_db9_return_contracts_are_source_bound_and_repeatable(
    tmp_path: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted_connector_return_lane import db9_return_contract_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config

    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == image

    log = HostedLog(root, f"native-db9-return-contracts-{project}")
    db9_return_contract_fixture_lane(root, project=project, image=config.image, log=log)

    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    prefix = "connector-return-fixture/"
    results = {item["stage"]: item for item in events if item.get("stage", "").startswith(prefix)}
    expected_stages = {
        f"{prefix}native-export",
        f"{prefix}four-db9-fault",
        f"{prefix}four-db9-control",
        *(
            f"{prefix}ground-contract-{case}"
            for case in ("common-fault", "common-control", "isolated-fault", "isolated-control")
        ),
        *(
            f"{prefix}pin-connectivity-contract-{case}"
            for case in (
                "common-fault",
                "common-control",
                "isolated-fault",
                "isolated-control",
                "assignment-only-split-control",
                "assignment-only-common-control",
            )
        ),
    }
    assert set(results) == expected_stages

    native_export = results[f"{prefix}native-export"]
    assert native_export["status"] == "PASS"
    assert native_export["kicad_version"] == version
    assert {source.split(":", 1)[0] for source in native_export["source_hashes"].split(",")} == {
        "four-db9-fault",
        "four-db9-control",
    }
    assert_native_fixture_mounts(root, native_export["command_receipt"])

    fault = results[f"{prefix}four-db9-fault"]
    assert fault["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert set(fault["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "net.numbered_returns",
    }
    control = results[f"{prefix}four-db9-control"]
    assert control["status"] == "PASS"
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"

    _assert_db9_contract_results(results, version)
