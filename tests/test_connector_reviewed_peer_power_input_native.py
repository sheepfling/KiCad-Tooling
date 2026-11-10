"""Exact-version native evidence for reviewed unlike connector power inputs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted_support import HostedLog
from kicad_tooling.hwrepo.contract_coach import pinned_image, run_command
from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from kicad_tooling.hwrepo.native_report_parsing import read_netlist
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.design_lint_fixtures.connector_reviewed_peer_power_input import (
    lint_report,
    power_input_coverage,
)
from tests.native_fixture_support import assert_native_fixture_mounts
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.power_lint]

RULE_ID = "connector.reviewed_peer_power_input_split"
PASSIVE_OPEN_RULE_ID = "connector.reviewed_peer_passive_power_input_open"
FIXTURE_ROOT = (
    Path(__file__).resolve().parent / "fixtures/design_lint/reviewed-peer-power-input-split-native"
)
EXPECTED_SOURCE_HASHES = {
    "fault": "1f274d1f6358c0b4340e69473d582df0c5c843469930e0813eab7dad6b98bc4e",
    "control": "d67e9657b9bcf7a8136d319c22562f2d6dcd4df11cc241dcd9613c18cc223110",
    "passive-fault": "08f4b355fce56952ed21bb63e39a20f4da061811ae7d7b791caef15786bd759e",
    "passive-control": "b05b1c46c0a492d6691261b905278eac431acd2c835dcc61e06d9d36a3d46223",
    "passive-open-fault": "d6ca4949abb67e0a1b7f4e331a989808dcb215200b752503ba85e78f24645aa5",
    "named-fault": "ae825d986b42a4987d580d66a174fd87cf53d0c93d7d949ac65a3660990e1936",
    "named-control": "85dc5cb5f4458bc37efe8dba6f48064c72acf0c4987be0e4a8fde4b136e805f1",
}
PASSIVE_CASES = frozenset({"passive-fault", "passive-control", "passive-open-fault"})
NAMED_CASES = frozenset({"named-fault", "named-control"})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_netlist_sha256(netlist: NetlistContract) -> str:
    data = json.dumps(netlist.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def test_native_reviewed_peer_power_input_fixture_sources_match_reviewed_hashes() -> None:
    assert {
        case: _sha256(FIXTURE_ROOT / f"{case}.kicad_sch") for case in EXPECTED_SOURCE_HASHES
    } == EXPECTED_SOURCE_HASHES


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.design_lint_rule(rule_id=PASSIVE_OPEN_RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="Digest-pinned native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_reviewed_peer_power_input_fault_and_control_are_repeatable(
    tmp_path: Path,
    project: str,
    version: str,
) -> None:
    image = PINNED_NATIVE_KICAD_IMAGES[version]
    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        project_id=project,
        kicad_version=version,
        image=image,
    )
    config = selected_config(root, project)
    assert (config.kicad_version, config.image) == (version, image)
    scratch = root / "build/ci-hosted/reviewed-peer-power-input"
    inputs = scratch / "fixtures"
    output = scratch / "native-netlists"
    inputs.mkdir(parents=True)
    output.mkdir()
    for case, expected_hash in EXPECTED_SOURCE_HASHES.items():
        fixture = FIXTURE_ROOT / f"{case}.kicad_sch"
        assert _sha256(fixture) == expected_hash
        shutil.copyfile(fixture, inputs / fixture.name)
        assert _sha256(inputs / fixture.name) == expected_hash

    user_args: tuple[str, ...] = ()
    if os.name != "nt":
        user_args = ("--user", f"{os.getuid()}:{os.getgid()}")
    script = (
        'mkdir -p "$HOME"; '
        'actual="$(kicad-cli version)"; '
        f'test "$actual" = "{version}"; '
        "for case in fault control passive-fault passive-control passive-open-fault "
        "named-fault named-control; do "
        "for run in first repeat; do "
        "kicad-cli sch export netlist --format kicadxml "
        '"--output" "/output/${case}.${run}.netlist.xml" '
        '"/fixtures/${case}.kicad_sch"; '
        "done; done"
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
        *user_args,
        "-e",
        "HOME=/tmp/kicad-reviewed-peer-power-input",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{output}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned_image(config.image),
        "-ec",
        script,
    )
    log = HostedLog(root, f"native-reviewed-peer-power-input-{project}")
    log.event(
        "reviewed-peer-power-input/native-export",
        "START",
        project=project,
        kicad_version=version,
        image=config.image,
    )
    command = run_command(root, argv, timeout=600)
    receipt = scratch / "native.command.json"
    write_model(receipt, command)
    if command.returncode != 0 or command.error is not None:
        log.event(
            "reviewed-peer-power-input/native-export",
            "FAIL",
            project=project,
            kicad_version=version,
            image=config.image,
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        pytest.fail(command.stderr or command.error or f"Native export exited {command.returncode}")
    log.event(
        "reviewed-peer-power-input/native-export",
        "PASS",
        project=project,
        kicad_version=version,
        image=config.image,
        source_hashes=",".join(f"{case}:{value}" for case, value in EXPECTED_SOURCE_HASHES.items()),
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    assert_native_fixture_mounts(root, receipt.relative_to(root).as_posix())

    for case in EXPECTED_SOURCE_HASHES:
        first = read_netlist(output / f"{case}.first.netlist.xml")
        repeat = read_netlist(output / f"{case}.repeat.netlist.xml")
        assert _normalized_netlist_sha256(first) == _normalized_netlist_sha256(repeat)
        assert first.component_symbols["J1"] != first.component_symbols["J2"]
        assert first.components["J1"].value == "USB-C receptacle"
        assert first.components["J2"].value == "Serial connector"
        assert first.components["J1"].footprint == "Synthetic:USB_C"
        assert first.components["J2"].footprint == "Synthetic:DB9"
        expected_type = "passive" if case in PASSIVE_CASES else "power_in"
        assert first.pin_electrical_types["J1.1"].casefold() == expected_type
        assert first.pin_electrical_types["J2.1"].casefold() == expected_type
        if case in NAMED_CASES:
            assert first.pin_functions["J1.1"] == "VBUS"
            assert first.pin_functions["J2.1"] == "VDD_IN"
            coverage = power_input_coverage(first, roles=("supply", "supply"))
        else:
            coverage = power_input_coverage(first)
        assert coverage.status == "COMPLETE"
        report = lint_report(first, coverage)
        finding_ids = {finding.rule_id for finding in report.findings}
        if case == "passive-open-fault":
            assert PASSIVE_OPEN_RULE_ID in finding_ids
            assert RULE_ID not in finding_ids
            finding = next(item for item in report.findings if item.rule_id == PASSIVE_OPEN_RULE_ID)
            assert finding.evidence["assignments"] == (
                "J1.1=USB_5V",
                "J2.1=<unassigned>",
            )
        elif case in {"fault", "passive-fault", "named-fault"}:
            assert RULE_ID in finding_ids
            finding = next(item for item in report.findings if item.rule_id == RULE_ID)
            assert finding.evidence["assignments"] == ("J1.1=USB_5V", "J2.1=SERIAL_5V")
            if case == "named-fault":
                assert finding.evidence["native_pin_functions"] == (
                    "J1.1=VBUS",
                    "J2.1=VDD_IN",
                )
                assert finding.evidence["power_role_categories"] == ("vbus", "vdd")
        else:
            assert RULE_ID not in finding_ids
            assert PASSIVE_OPEN_RULE_ID not in finding_ids
