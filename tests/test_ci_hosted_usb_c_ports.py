"""Digest-pinned native USB-C port fixture regressions."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

import pytest

from kicad_tooling.ci_hosted import HostedLog, usb_c_port_fixture_lane
from kicad_tooling.hwrepo.electrical import selected_config
from tests.support import reference_root

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_USB_C_PORT_FIXTURES") != "1",
        reason="native USB-C port fixtures run in the digest-pinned package acceptance lane",
    ),
]

_PROJECTS = (
    pytest.param(("controller", "10.0.0"), id="controller-kicad-10-0-0"),
    pytest.param(("raspberry-pi-status-led", "10.0.5"), id="status-led-kicad-10-0-5"),
)
_EXPECTED_IMAGES = {
    "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
    "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
    "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
    "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
}
_EXPECTED_SOURCE_HASHES = {
    "connector": "42935f2e21f3b86acc33a87916072b466d5c75b61cddd472a40fb6219d59ce9a",
    "source-rp-control": "b9913fa1e44adaaa3837257dc0756bcb39411b9bb79dcd1568c1a264248a1f8f",
    "sink-rd-control": "5ac40420e4adcc7f2005e1808f1ebdeb765fd4907113bfa5be657407d2d6d789",
    "vbus-capacitance-control": "d664fe8ece994d847c133187c14bcc279c2466eb917ddddddac4faa22c17c6ca",
    "vbus-capacitance-fault": "c126f173af020b3aa2eeebf74657064685e87eac684b4b197a15d82992970560",
}
_EXPECTED_STAGES = {
    "usb-c-port-fixture/native-export",
    "usb-c-port-fixture/unmapped",
    "usb-c-port-fixture/mapped",
    "usb-c-port-fixture/source-rp-control",
    "usb-c-port-fixture/sink-rd-control",
    "usb-c-port-fixture/vbus-capacitance-control",
    "usb-c-port-fixture/vbus-capacitance-fault",
}


class NativeUsbCPortRun(NamedTuple):
    """One isolated project run and its source-bound native lane events."""

    root: Path
    project: str
    version: str
    image: str
    results: Mapping[str, Mapping[str, str]]


@pytest.fixture(scope="module", params=_PROJECTS)
def native_usb_c_port_run(request: pytest.FixtureRequest) -> NativeUsbCPortRun:
    project, version = request.param
    repository = Path(__file__).resolve().parents[1]
    acceptance = repository / "build/ci"
    acceptance.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="native-usb-c-port-project-", dir=acceptance))
    shutil.copytree(
        reference_root(),
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )

    expected_image = _EXPECTED_IMAGES[project]
    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == expected_image
    log = HostedLog(root, f"native-usb-c-port-{project}")
    usb_c_port_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results: dict[str, Mapping[str, str]] = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("usb-c-port-fixture/")
    }
    assert set(results) == _EXPECTED_STAGES
    return NativeUsbCPortRun(root, project, version, expected_image, results)


def _assert_repeatable_source_evidence(
    run: NativeUsbCPortRun,
    case: str,
    result: Mapping[str, str],
) -> None:
    assert result["kicad_version"] == run.version, case
    assert result["image"] == run.image, case
    assert result["source_sha256"] == _EXPECTED_SOURCE_HASHES[case], case
    assert result["repeatable"] == "true", case
    assert result["repeat_normalized_netlist_sha256"] == result["normalized_netlist_sha256"], case

    receipt = run.root / result["command_receipt"]
    assert receipt.is_file(), case
    command = json.loads(receipt.read_text())
    mounts = tuple(
        command["argv"][index + 1]
        for index, item in enumerate(command["argv"][:-1])
        if item == "-v"
    )
    assert len(mounts) == 2, case
    assert sum(item.endswith(":/fixtures:ro") for item in mounts) == 1, case
    assert sum(item.endswith(":/output:rw") for item in mounts) == 1, case


@pytest.mark.design_lint_rule(rule_id="bus.usb_c_unreviewed_port")
def test_native_usb_c_role_map_fault_and_controls_are_repeatable(
    native_usb_c_port_run: NativeUsbCPortRun,
) -> None:
    run = native_usb_c_port_run
    unmapped = run.results["usb-c-port-fixture/unmapped"]
    assert unmapped["status"] == "PASS"
    assert unmapped["lint_status"] == "REVIEW"
    assert unmapped["findings"] == "J1: USB-C role-map coverage"
    assert unmapped["cc_pin_functions"] == "J1.4=CC1;J1.5=CC2"
    _assert_repeatable_source_evidence(run, "connector", unmapped)

    mapped = run.results["usb-c-port-fixture/mapped"]
    assert mapped["status"] == "PASS"
    assert mapped["lint_status"] == "PASS"
    assert mapped["findings"] == "none"
    _assert_repeatable_source_evidence(run, "connector", mapped)

    for case in ("source-rp-control", "sink-rd-control"):
        result = run.results[f"usb-c-port-fixture/{case}"]
        assert result["status"] == "PASS", case
        assert result["lint_status"] == "REVIEW", case
        assert result["findings"] == "J1: USB-C role-map coverage", case
        assert result["cc_pin_functions"] == "J1.4=CC1;J1.5=CC2", case
        assert result["fixture_case"] == case
        _assert_repeatable_source_evidence(run, case, result)


@pytest.mark.design_lint_rule(rule_id="bus.usb_c_vbus_capacitance_review")
def test_native_usb_c_vbus_capacitance_fault_and_control_are_repeatable(
    native_usb_c_port_run: NativeUsbCPortRun,
) -> None:
    run = native_usb_c_port_run
    control = run.results["usb-c-port-fixture/vbus-capacitance-control"]
    assert control["status"] == "PASS"
    assert control["check_status"] == "PASS"
    assert control["expected_check_status"] == "PASS"
    assert float(control["observed_nf"]) == 4700.0
    _assert_repeatable_source_evidence(run, "vbus-capacitance-control", control)

    fault = run.results["usb-c-port-fixture/vbus-capacitance-fault"]
    assert fault["status"] == "PASS"
    assert fault["check_status"] == "FAIL"
    assert fault["expected_check_status"] == "FAIL"
    assert float(fault["observed_nf"]) == 2200.0
    _assert_repeatable_source_evidence(run, "vbus-capacitance-fault", fault)
