"""Exact-version native acceptance for named power-pin net-role review."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.hwrepo.electrical import selected_config

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.component_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]

_EXPECTED_IMAGES = MappingProxyType(
    {
        "controller": "ghcr.io/kicad/kicad:10.0.0@sha256:"
        "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3",
        "raspberry-pi-status-led": "ghcr.io/kicad/kicad:10.0.5@sha256:"
        "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c",
    }
)
_ENABLE_CONTROL_FIXTURE_HASHES = MappingProxyType(
    {
        "enable-return-fault": "69f5c34420fa5c28805e2b5f17950a06bdcd86979b21245076d829ae383a73c0",
        "enable-signal-control": "de64ab8198ae84fdae62d4fe103e1753068bd4202f47b94a4ca02594534b2157",
        "enable-vss-control": "aad7c1d913edba11aee09867e5af3b404a0c9a1b62f243c70eee1534f64472a7",
    }
)


def _selected_image(hosted_reference_root: Path, project: str, version: str) -> str:

    config = selected_config(hosted_reference_root, project)
    assert config.kicad_version == version
    assert config.image == _EXPECTED_IMAGES[project]
    return config.image


@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_POWER_PIN_NET_ROLE_FIXTURES") != "1",
    reason="native power pin-role fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_named_power_pin_fault_and_control_export_repeatably(
    hosted_reference_root: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, power_pin_net_role_fixture_lane

    root = hosted_reference_root
    expected_image = _selected_image(root, project, version)

    log = HostedLog(root, f"native-power-pin-net-role-{project}")
    power_pin_net_role_fixture_lane(root, project=project, image=expected_image, log=log)
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    passed = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("power-pin-net-role/") and item.get("status") == "PASS"
    }

    assert set(passed) == {
        "power-pin-net-role/native-export",
        "power-pin-net-role/fault",
        "power-pin-net-role/control",
    }
    assert passed["power-pin-net-role/native-export"]["kicad_version"] == version
    assert passed["power-pin-net-role/native-export"]["image"] == expected_image
    fault = passed["power-pin-net-role/fault"]
    control = passed["power-pin-net-role/control"]
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == "U1.1: VDD pin assigned to GND"
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    for result in (fault, control):
        assert result["kicad_version"] == version
        assert result["image"] == expected_image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        receipt = root / result["command_receipt"]
        assert receipt.is_file()


@pytest.mark.design_lint_rule(rule_id="power.named_supply_pin_on_negative_rail")
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_POWER_PIN_NET_ROLE_FIXTURES") != "1",
    reason="native power pin-role fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_named_supply_pin_on_negative_rail_fault_and_control_export_repeatably(
    hosted_reference_root: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, power_pin_net_role_fixture_lane

    root = hosted_reference_root
    expected_image = _selected_image(root, project, version)
    log = HostedLog(root, f"native-negative-power-pin-rail-{project}")
    power_pin_net_role_fixture_lane(
        root,
        project=project,
        image=expected_image,
        log=log,
        cases=("negative-rail-fault", "control"),
    )
    events = tuple(json.loads(line) for line in log.events.read_text().splitlines())
    passed = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("power-pin-net-role/") and item.get("status") == "PASS"
    }

    assert set(passed) == {
        "power-pin-net-role/native-export",
        "power-pin-net-role/negative-rail-fault",
        "power-pin-net-role/control",
    }
    fault = passed["power-pin-net-role/negative-rail-fault"]
    control = passed["power-pin-net-role/control"]
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == "U1.1: VDD pin assigned to -5V"
    assert fault["finding_rules"] == "power.named_supply_pin_on_negative_rail"
    assert control["lint_status"] == "PASS"
    assert control["findings"] == "none"
    for result in (fault, control):
        assert result["kicad_version"] == version
        assert result["image"] == expected_image
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert (root / result["command_receipt"]).is_file()


@pytest.mark.design_lint_rule(rule_id="power.enable_control_tied_to_return")
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_POWER_PIN_NET_ROLE_FIXTURES") != "1",
    reason="native power pin-role fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize(
    ("project", "version"),
    (("controller", "10.0.0"), ("raspberry-pi-status-led", "10.0.5")),
)
def test_enable_control_return_fault_and_controls_export_repeatably(
    hosted_reference_root: Path,
    project: str,
    version: str,
) -> None:
    from kicad_tooling.ci_hosted import HostedLog, power_pin_net_role_fixture_lane

    fixture_root = Path(__file__).parent / "fixtures/design_lint/power-pin-net-role-native"
    assert {
        case: hashlib.sha256((fixture_root / f"{case}.kicad_sch").read_bytes()).hexdigest()
        for case in _ENABLE_CONTROL_FIXTURE_HASHES
    } == _ENABLE_CONTROL_FIXTURE_HASHES
    root = hosted_reference_root
    expected_image = _selected_image(root, project, version)
    log = HostedLog(root, f"native-enable-control-return-{project}")
    power_pin_net_role_fixture_lane(
        root,
        project=project,
        image=expected_image,
        log=log,
        cases=tuple(_ENABLE_CONTROL_FIXTURE_HASHES),
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    passed = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("power-pin-net-role/") and item.get("status") == "PASS"
    }

    assert set(passed) == {
        "power-pin-net-role/native-export",
        *(f"power-pin-net-role/{case}" for case in _ENABLE_CONTROL_FIXTURE_HASHES),
    }
    fault = passed["power-pin-net-role/enable-return-fault"]
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == "U1.3: EN control input assigned to GND"
    assert fault["finding_rules"] == "power.enable_control_tied_to_return"
    for case in ("enable-signal-control", "enable-vss-control"):
        control = passed[f"power-pin-net-role/{case}"]
        assert control["lint_status"] == "PASS"
        assert control["findings"] == "none"
    for case in _ENABLE_CONTROL_FIXTURE_HASHES:
        result = passed[f"power-pin-net-role/{case}"]
        assert result["kicad_version"] == version
        assert result["image"] == expected_image
        assert result["source_sha256"] == _ENABLE_CONTROL_FIXTURE_HASHES[case]
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]
        assert (root / result["command_receipt"]).is_file()
