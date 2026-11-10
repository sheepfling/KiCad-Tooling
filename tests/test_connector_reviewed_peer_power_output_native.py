"""Exact-version native evidence for reviewed connector power-output splits."""

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

RULE_ID = "connector.reviewed_peer_power_output_split"
FIXTURE_ROOT = (
    Path(__file__).resolve().parent / "fixtures/design_lint/reviewed-peer-power-output-split-native"
)
EXPECTED_SOURCE_HASHES = {
    "fault": "19b83b154efa06421f2b09874d2403ed708c848c2e75ac8ca042647eb146dce2",
    "control": "a3e5a9915ae3b3192730100e45835cb1ceb16606b380d286b06c0e2fbc83b380",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_netlist_sha256(netlist: NetlistContract) -> str:
    data = json.dumps(netlist.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def test_native_reviewed_peer_power_output_fixture_sources_match_reviewed_hashes() -> None:
    assert {
        case: _sha256(FIXTURE_ROOT / f"{case}.kicad_sch") for case in EXPECTED_SOURCE_HASHES
    } == EXPECTED_SOURCE_HASHES


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_CONNECTOR_FIXTURES") != "1",
    reason="Digest-pinned native connector fixtures run in package acceptance",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_native_reviewed_peer_power_output_fault_and_control_are_repeatable(
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
    scratch = root / "build/ci-hosted/reviewed-peer-power-output"
    inputs, outputs = scratch / "fixtures", scratch / "native-netlists"
    inputs.mkdir(parents=True)
    outputs.mkdir()
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
        "for case in fault control; do "
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
        "HOME=/tmp/kicad-reviewed-peer-power-output",
        "-v",
        f"{inputs}:/fixtures:ro",
        "-v",
        f"{outputs}:/output:rw",
        "-w",
        "/fixtures",
        "--entrypoint",
        "/bin/sh",
        pinned_image(config.image),
        "-ec",
        script,
    )
    log = HostedLog(root, f"native-reviewed-peer-power-output-{project}")
    log.event(
        "reviewed-peer-power-output/native-export",
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
            "reviewed-peer-power-output/native-export",
            "FAIL",
            project=project,
            kicad_version=version,
            image=config.image,
            error=command.stderr or command.error or f"exit {command.returncode}",
        )
        pytest.fail(command.stderr or command.error or f"Native export exited {command.returncode}")
    log.event(
        "reviewed-peer-power-output/native-export",
        "PASS",
        project=project,
        kicad_version=version,
        image=config.image,
        source_hashes=",".join(f"{case}:{value}" for case, value in EXPECTED_SOURCE_HASHES.items()),
        command_receipt=receipt.relative_to(root).as_posix(),
    )
    assert_native_fixture_mounts(root, receipt.relative_to(root).as_posix())

    for case in EXPECTED_SOURCE_HASHES:
        first = read_netlist(outputs / f"{case}.first.netlist.xml")
        repeat = read_netlist(outputs / f"{case}.repeat.netlist.xml")
        assert _normalized_netlist_sha256(first) == _normalized_netlist_sha256(repeat)
        assert first.component_symbols["J1"] != first.component_symbols["J2"]
        assert first.components["J1"].value == "USB-C receptacle"
        assert first.components["J2"].value == "Serial connector"
        assert first.components["J1"].footprint == "Synthetic:USB_C"
        assert first.components["J2"].footprint == "Synthetic:DB9"
        assert first.pin_functions["J1.1"] == "VBUS"
        assert first.pin_functions["J2.1"] == "VDD_OUT"
        assert first.pin_electrical_types["J1.1"].casefold() == "power_out"
        assert first.pin_electrical_types["J2.1"].casefold() == "power_out"
        coverage = power_input_coverage(
            first,
            interface_signals=("POWER_OUTPUT", "POWER_OUTPUT"),
            roles=("supply", "supply"),
            directions=("output", "output"),
        )
        assert coverage.status == "COMPLETE"
        report = lint_report(first, coverage)
        findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
        if case == "fault":
            assert len(findings) == 1
            assert findings[0].evidence["assignments"] == (
                "J1.1=USB_5V",
                "J2.1=SERIAL_5V",
            )
            assert findings[0].evidence["interface_directions"] == ("output", "output")
        else:
            assert not findings
