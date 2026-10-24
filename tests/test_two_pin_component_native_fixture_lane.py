"""Source-hashed native regressions for same-net component lint."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from kicad_tooling.ci_hosted import TWO_PIN_COMPONENT_FIXTURE_CASES
from kicad_tooling.ci_hosted_two_pin_components import (
    TWO_PIN_COMPONENT_CANDIDATE_KINDS,
    two_pin_component_fixture_cases_for_rules,
)
from tests.design_lint_fixtures.two_pin_component_native import run_native_two_pin_rule_fixture
from tests.design_lint_fixtures.two_pin_component_sources import (
    TWO_PIN_COMPONENT_SOURCE_HASHES,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]

_EXPECTED_SOURCE_HASHES = TWO_PIN_COMPONENT_SOURCE_HASHES


def test_native_fixture_sources_are_hash_pinned_under_the_fixture_root() -> None:
    fixture_root = Path(__file__).resolve().parents[1] / "tests/fixtures/design_lint"
    case_sources = {filename for filename, _, _ in TWO_PIN_COMPONENT_FIXTURE_CASES.values()}
    assert case_sources == set(_EXPECTED_SOURCE_HASHES)
    assert len(TWO_PIN_COMPONENT_FIXTURE_CASES) == 42
    for filename, expected_digest in _EXPECTED_SOURCE_HASHES.items():
        source = (fixture_root / filename).resolve()
        assert source.is_relative_to(fixture_root.resolve())
        assert source.is_file()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_digest


@pytest.mark.design_lint_rule(rule_id="component.two_pin_buzzer_same_net")
def test_native_candidate_kind_map_covers_every_fixture_rule() -> None:
    fixture_rule_ids = {rule_id for _, rule_id, _ in TWO_PIN_COMPONENT_FIXTURE_CASES.values()}
    assert set(TWO_PIN_COMPONENT_CANDIDATE_KINDS) == fixture_rule_ids
    assert TWO_PIN_COMPONENT_CANDIDATE_KINDS["component.two_pin_buzzer_same_net"] == frozenset(
        {"buzzer"}
    )
    assert TWO_PIN_COMPONENT_CANDIDATE_KINDS["component.two_pin_speaker_same_net"] == frozenset(
        {"speaker"}
    )
    assert TWO_PIN_COMPONENT_CANDIDATE_KINDS["component.two_pin_motor_same_net"] == frozenset(
        {"motor"}
    )
    assert TWO_PIN_COMPONENT_CANDIDATE_KINDS["component.two_pin_solar_cell_same_net"] == frozenset(
        {"solar_cell"}
    )


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


def test_led_native_fixture_scope_contains_only_led_fault_and_control() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_led_same_net",))
    assert set(selected) == {"same-net-led", "distinct-nets-led"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {"component.two_pin_led_same_net"}
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


def test_buzzer_native_fixture_scope_contains_only_buzzer_fault_and_control() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_buzzer_same_net",))
    assert set(selected) == {"same-net-buzzer", "distinct-nets-buzzer"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {"component.two_pin_buzzer_same_net"}
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


def test_speaker_native_fixture_scope_contains_only_speaker_fault_and_control() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_speaker_same_net",))
    assert set(selected) == {"same-net-speaker", "distinct-nets-speaker"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {
        "component.two_pin_speaker_same_net"
    }
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


@pytest.mark.design_lint_rule(rule_id="component.two_pin_battery_same_net")
def test_battery_native_fixture_scope_contains_only_battery_fault_and_control() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_battery_same_net",))
    assert set(selected) == {"same-net-battery", "distinct-nets-battery"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {
        "component.two_pin_battery_same_net"
    }
    assert TWO_PIN_COMPONENT_CANDIDATE_KINDS["component.two_pin_battery_same_net"] == frozenset(
        {"battery"}
    )
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


@pytest.mark.design_lint_rule(rule_id="component.two_pin_motor_same_net")
def test_motor_native_fixture_scope_contains_only_motor_fault_and_control() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_motor_same_net",))
    assert set(selected) == {"same-net-motor", "distinct-nets-motor"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {"component.two_pin_motor_same_net"}
    assert TWO_PIN_COMPONENT_CANDIDATE_KINDS["component.two_pin_motor_same_net"] == frozenset(
        {"motor"}
    )
    assert any(subjects for _, _, subjects in selected.values())
    assert any(not subjects for _, _, subjects in selected.values())


@pytest.mark.design_lint_rule(rule_id="component.two_pin_solar_cell_same_net")
def test_solar_cell_native_fixture_scope_contains_only_solar_cell_fault_and_control() -> None:
    selected = two_pin_component_fixture_cases_for_rules(("component.two_pin_solar_cell_same_net",))
    assert set(selected) == {"same-net-solar-cell", "distinct-nets-solar-cell"}
    assert {rule_id for _, rule_id, _ in selected.values()} == {
        "component.two_pin_solar_cell_same_net"
    }
    assert TWO_PIN_COMPONENT_CANDIDATE_KINDS["component.two_pin_solar_cell_same_net"] == frozenset(
        {"solar_cell"}
    )
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
    run_native_two_pin_rule_fixture(
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
    run_native_two_pin_rule_fixture(
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
    run_native_two_pin_rule_fixture(
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
    run_native_two_pin_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_diode_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id="component.two_pin_led_same_net")
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_led_same_net_fault_and_control(tmp_path: Path, kicad_version: str) -> None:
    run_native_two_pin_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_led_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id="component.two_pin_buzzer_same_net")
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_buzzer_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    run_native_two_pin_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_buzzer_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id="component.two_pin_speaker_same_net")
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_speaker_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    run_native_two_pin_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_speaker_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id="component.two_pin_battery_same_net")
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_battery_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    run_native_two_pin_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_battery_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id="component.two_pin_motor_same_net")
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_motor_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    run_native_two_pin_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_motor_same_net",
    )


@pytest.mark.native_kicad
@pytest.mark.slow
@pytest.mark.design_lint_rule(rule_id="component.two_pin_solar_cell_same_net")
@pytest.mark.skipif(
    os.environ.get("KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES") != "1",
    reason="native two-pin component fixtures run in the digest-pinned package acceptance lane",
)
@pytest.mark.parametrize("kicad_version", ("10.0.0", "10.0.5"))
def test_native_two_pin_solar_cell_same_net_fault_and_control(
    tmp_path: Path, kicad_version: str
) -> None:
    run_native_two_pin_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_solar_cell_same_net",
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
    run_native_two_pin_rule_fixture(
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
    run_native_two_pin_rule_fixture(
        tmp_path,
        kicad_version=kicad_version,
        rule_id="component.two_pin_switch_same_net",
    )
