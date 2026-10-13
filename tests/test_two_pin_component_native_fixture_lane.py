"""Source-hashed native regressions for same-net component lint."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import (
    TWO_PIN_COMPONENT_FIXTURE_CASES,
    HostedLog,
    two_pin_component_fixture_lane,
)
from kicad_tooling.ci_hosted_two_pin_components import two_pin_component_fixture_cases_for_rules
from kicad_tooling.hwrepo.electrical import selected_config
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.synthetic_design_lint_project import (
    PINNED_NATIVE_KICAD_IMAGES,
    synthetic_design_lint_project,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

_EXPECTED_SOURCE_HASHES = {
    "two-pin-components/same-net.kicad_sch": "54de8ccfcffb2d7e44a84fb4b5892872046bc963c2294242498d9b653d526a2b",
    "two-pin-components/distinct-nets.kicad_sch": "338deb4b9194e37a80813b3a3c447d21c14fa59fef78b0925898f595a27fbdea",
    "two-pin-varistors/same-net-varistor.kicad_sch": "c8f563192569de181d597ae31528b4e64782445e69894b9c0c0d37acd7480abf",
    "two-pin-varistors/distinct-nets-varistor.kicad_sch": "60369d9cac30ade461b045c99b599b73821fbefc646a7c06f2ce552d31e871a0",
    "two-pin-thermistors/same-net-thermistor.kicad_sch": "be417443337f223c51b6caa7305038544df0e5342e90cae91d5fce6a797ac26f",
    "two-pin-thermistors/distinct-nets-thermistor.kicad_sch": "7a6753de56bf6985d4fd218b96e1f9b951541fd103920baaea503b8999f02a06",
    "two-pin-thermistors/same-net-thermistor-ptc.kicad_sch": "5d7678f58af0a323961c1af73173a1dbcd52c7ad09fac43f1f0cd1545ff65762",
    "two-pin-thermistors/distinct-nets-thermistor-ptc.kicad_sch": "452b3245be262532becb18866bf8a28dd01e9235214580fc67c74f98210daab5",
    "two-pin-thermistors/same-net-thermistor-us.kicad_sch": "2c01ec413b9a122d7d96ead9f18a5fa470e419a89be1241e3216b0a8a7b0b56c",
    "two-pin-thermistors/distinct-nets-thermistor-us.kicad_sch": "a0881cd4e53dc6b4d0de89401d81d4714254b52db1f12afa6163a6263307947f",
    "two-pin-thermistors/same-net-thermistor-ntc-us.kicad_sch": "4953e4dbfb058fc5b563249736e823b296016504e3782534db9761562870d59f",
    "two-pin-thermistors/distinct-nets-thermistor-ntc-us.kicad_sch": "bbc82a02e7a9e17d63b5d1d0541b8763b836e0934a43eab99c92980f8ac3409f",
    "two-pin-thermistors/same-net-thermistor-ptc-us.kicad_sch": "0f43667c614d9c8c72f257101b173551e947f280ca11a47f32868b40d11320ef",
    "two-pin-thermistors/distinct-nets-thermistor-ptc-us.kicad_sch": "4ca99c33fa15936b648832d1d116b578cf12433b40653f3d82120751c4f40301",
    "two-pin-components/custom-capacitor-same-net.kicad_sch": "304c3eb9b979f807f99ee91fecec83e4688bb8d50207c298ff985688950e9fc2",
    "cohort-power-pin-dc/custom-capacitor-role-control.kicad_sch": "338b39009694575fae172d6691ddd8d17804d74503ad73c374a53661373e789d",
    "two-pin-components/same-net-diode.kicad_sch": "c7b34973f881f5c8d8e8ac26b07c03dec70b061f66b8338d61fb085583c2aa8b",
    "two-pin-components/distinct-nets-diode.kicad_sch": "74d19829e8dd9379a26cb6da9dd3cf10a48abce9d724661338f73ce0086bb928",
    "two-pin-crystals/same-net-crystal.kicad_sch": "0a55a739bcce60cacafaadf2c9995c0ff3ef07caf4284745b420a8e0f2de2b1a",
    "two-pin-crystals/distinct-nets-crystal.kicad_sch": "4c4fa54184ba74eb8194016a166e068c1a41646b4e59686d187395d981c4bc13",
    "two-pin-fuses/same-net-fuse.kicad_sch": "b69792902442ef89c103f5a4b783b73633b88d9519ab01c5b77df9b654df62ca",
    "two-pin-fuses/distinct-nets-fuse.kicad_sch": "c9c6afa14db03137c1bbc78b82875d159f79b5ebabbb7ea21c6eac1e33fc6edb",
    "two-pin-fuses/same-net-polyfuse.kicad_sch": "1537a762c427dbc77e3afb35fd2faecb494e69674b8ca3f7e04e7497fd96e3ad",
    "two-pin-fuses/distinct-nets-polyfuse.kicad_sch": "f4d7ba7f0d27d295c725f2286dace93fa4163b3dbb04130d0c913f05660fc037",
    "two-pin-ferrites/same-net-ferrite.kicad_sch": "8ede05ea1d9c8afb0cec2f1c8c9bddf527eab015ab779097f4ddc528866751f7",
    "two-pin-ferrites/distinct-nets-ferrite.kicad_sch": "199c802ca290b1281622c623f4966b159144f0e95fd99ed0e21a14a0875734a7",
    "two-pin-switches/same-net-spst.kicad_sch": "1ddb2e72f4759c3edddd0f1c7077090c911fa3cbd36d48ef5a0850d6146c25b4",
    "two-pin-switches/distinct-nets-spst.kicad_sch": "2f9e43e716fe6bc89645734768ced5ff5491ba8b62330aa1c544db236d31e147",
}


def test_native_fixture_sources_are_hash_pinned_under_the_fixture_root() -> None:
    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    case_sources = {filename for filename, _, _ in TWO_PIN_COMPONENT_FIXTURE_CASES.values()}
    assert case_sources == set(_EXPECTED_SOURCE_HASHES)
    assert len(TWO_PIN_COMPONENT_FIXTURE_CASES) == 28
    for filename, expected_digest in _EXPECTED_SOURCE_HASHES.items():
        source = (fixture_root / filename).resolve()
        assert source.is_relative_to(fixture_root.resolve())
        assert source.is_file()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_digest


def test_passive_native_fixture_scope_contains_only_passive_faults_and_controls() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_passive_same_net",))
    assert set(selected) == {
        "same-net-passive",
        "distinct-nets-passive",
        "same-net-varistor",
        "distinct-nets-varistor",
        "same-net-thermistor",
        "distinct-nets-thermistor",
        "same-net-thermistor-ptc",
        "distinct-nets-thermistor-ptc",
        "same-net-thermistor-us",
        "distinct-nets-thermistor-us",
        "same-net-thermistor-ntc-us",
        "distinct-nets-thermistor-ntc-us",
        "same-net-thermistor-ptc-us",
        "distinct-nets-thermistor-ptc-us",
        "same-net-mapped-capacitor",
        "distinct-nets-mapped-capacitor",
    }
    assert {rule_id for _, rule_id, _ in selected.values()} == {
        "component.two_pin_passive_same_net"
    }
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


def test_fuse_native_fixture_scope_contains_only_fuse_faults_and_controls() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_fuse_same_net",))
    assert set(selected) == {
        "same-net-fuse",
        "distinct-nets-fuse",
        "same-net-polyfuse",
        "distinct-nets-polyfuse",
    }
    assert {rule_id for _, rule_id, _ in selected.values()} == {"component.two_pin_fuse_same_net"}
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


def test_ferrite_native_fixture_scope_contains_only_ferrite_fault_and_control() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_ferrite_same_net",))
    assert set(selected) == {"same-net-ferrite", "distinct-nets-ferrite"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {
        "component.two_pin_ferrite_same_net"
    }
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


def test_diode_native_fixture_scope_contains_only_diode_fault_and_control() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_diode_same_net",))
    assert set(selected) == {"same-net-diode", "distinct-nets-diode"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {"component.two_pin_diode_same_net"}
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


def test_crystal_native_fixture_scope_contains_only_crystal_fault_and_control() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_crystal_same_net",))
    assert set(selected) == {"same-net-crystal", "distinct-nets-crystal"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {
        "component.two_pin_crystal_same_net"
    }
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


def test_switch_native_fixture_scope_contains_only_switch_fault_and_control() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_switch_same_net",))
    assert set(selected) == {"same-net-switch", "distinct-nets-switch"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {"component.two_pin_switch_same_net"}
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


def _run_native_rule_fixture(
    tmp_path: Path,
    *,
    kicad_version: str,
    rule_id: str,
) -> dict[str, dict[str, str]]:
    selected_cases = two_pin_component_fixture_cases_for_rules((rule_id,))
    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    for filename, _, _ in selected_cases.values():
        source = fixture_root / filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == _EXPECTED_SOURCE_HASHES[filename]

    root, _ = synthetic_design_lint_project(
        tmp_path,
        DesignLintPolicy(),
        kicad_version=kicad_version,
        image=PINNED_NATIVE_KICAD_IMAGES[kicad_version],
    )
    config = selected_config(root, "controller")
    assert config.kicad_version == kicad_version
    assert config.image == PINNED_NATIVE_KICAD_IMAGES[kicad_version]

    log = HostedLog(root, f"native-two-pin-component-{kicad_version}")
    two_pin_component_fixture_lane(
        root,
        project="controller",
        image=config.image,
        log=log,
        rule_ids=(rule_id,),
    )
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    results = {
        item["stage"]: item
        for item in events
        if item.get("stage", "").startswith("two-pin-component-fixture/")
    }
    expected_cases = {
        f"two-pin-component-fixture/{name}" for name in ("native-export", *selected_cases)
    }
    assert set(results) == expected_cases
    native_export = results["two-pin-component-fixture/native-export"]
    assert native_export["status"] == "PASS"
    receipt = root / native_export["command_receipt"]
    assert receipt.is_file()
    argv = json.loads(receipt.read_text(encoding="utf-8"))["argv"]
    assert config.image in argv
    assert argv[argv.index("--network") + 1] == "none"
    assert "--read-only" in argv
    mounts = tuple(argv[index + 1] for index, argument in enumerate(argv[:-1]) if argument == "-v")
    assert len(mounts) == 2
    assert sum(mount.endswith(":/fixtures:ro") for mount in mounts) == 1
    assert sum(mount.endswith(":/output:rw") for mount in mounts) == 1

    for case, (filename, case_rule_id, expected_subjects) in selected_cases.items():
        result = results[f"two-pin-component-fixture/{case}"]
        assert result["status"] == "PASS"
        assert result["component_rule"] == case_rule_id == rule_id
        assert result["source_sha256"] == _EXPECTED_SOURCE_HASHES[filename]
        expected_findings = ";".join(sorted(expected_subjects)) or "none"
        assert result["component_findings"] == expected_findings
        assert result["lint_status"] == ("REVIEW" if expected_subjects else "PASS")
        assert result["repeatable"] == "true"
        assert result["normalized_netlist_sha256"] == result["repeat_normalized_netlist_sha256"]

    return results


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_passive_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    _run_native_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_passive_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_fuse_same_net_fault_and_control(tmp_path: Path, kicad_version: str) -> None:
    _run_native_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_fuse_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_ferrite_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    _run_native_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_ferrite_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_diode_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    _run_native_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_diode_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_crystal_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    _run_native_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_crystal_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_switch_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    _run_native_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_switch_same_net",
    )
