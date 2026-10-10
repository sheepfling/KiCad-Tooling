"""Digest-pinned native acceptance for connector DC-reference review."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_NET_DC_REFERENCE_FIXTURES") != "1",
    reason="native DC-reference fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_connector_capacitor_only_fault_and_controls_export_repeatably(
    hosted_reference_root: Path, project: str, version: str
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, net_dc_reference_fixture_lane
    from kicad_tooling.hwrepo.electrical import selected_config

    repository = Path(__file__).resolve().parents[1]
    root = hosted_reference_root
    expected_images = {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
    fixture_root = repository / "tests/fixtures/design_lint/net-dc-reference"
    expected_source_hashes = {
        "fault.kicad_sch": "34678343d148878ab7ab470a3dd99e049ccfc08969cbd419548397602e5c483a",
        "control.kicad_sch": "312d7a1f6cd61c4c2e05f31ec57e5688c22610f7bb76dd18271d53eba86eb2ec",
        "dnp-control.kicad_sch": "fecaddc449493001871d6ca049b1d764030d7f72860e3aa11aa492fdcf570924",
    }
    actual_source_hashes = {
        name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest()
        for name in expected_source_hashes
    }
    assert actual_source_hashes == expected_source_hashes

    config = selected_config(root, project)
    assert config.kicad_version == version
    assert config.image == expected_images[project]
    log = HostedLog(root, f"native-net-dc-reference-{project}")
    net_dc_reference_fixture_lane(root, project=project, image=config.image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("net-dc-reference-fixture/")
    }
    assert set(results) == {
        "net-dc-reference-fixture/native-export",
        "net-dc-reference-fixture/fault",
        "net-dc-reference-fixture/control",
        "net-dc-reference-fixture/dnp-control",
    }
    assert results["net-dc-reference-fixture/native-export"]["status"] == "PASS"
    native = results["net-dc-reference-fixture/native-export"]
    receipt = root / native["command_receipt"]
    assert receipt.is_file()
    command = json.loads(receipt.read_text())
    argv = command["argv"]
    assert expected_images[project] in argv
    assert "--network" in argv
    assert "none" in argv
    assert "--read-only" in argv
    mounts = tuple(argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-v")
    assert len(mounts) == 2
    assert sum(item.endswith(":/fixtures:ro") for item in mounts) == 1
    assert sum(item.endswith(":/output:rw") for item in mounts) == 1
    fault = results["net-dc-reference-fixture/fault"]
    control = results["net-dc-reference-fixture/control"]
    dnp_control = results["net-dc-reference-fixture/dnp-control"]
    assert fault["status"] == "PASS"
    assert fault["lint_status"] == "REVIEW"
    assert "ANALOG_IN" in fault["finding"]
    assert fault["erc_error_types"] == "none"
    assert control["status"] == "PASS"
    assert control["lint_status"] == "PASS"
    assert control["finding"] == "none"
    assert control["erc_error_types"] == "none"
    assert dnp_control["status"] == "PASS"
    assert dnp_control["lint_status"] == "PASS"
    assert dnp_control["finding"] == "none"
    assert dnp_control["erc_error_types"] == "none"
    for result, name in (
        (fault, "fault.kicad_sch"),
        (control, "control.kicad_sch"),
        (dnp_control, "dnp-control.kicad_sch"),
    ):
        assert result["kicad_version"] == version
        assert result["image"] == expected_images[project]
        assert result["source_sha256"] == expected_source_hashes[name]
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert result["normalized_erc_sha256"] == result["repeat_normalized_erc_sha256"]
