"""Focused component peer-pin regression cases."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.models import (
    NetlistContract,
)
from tests.component_peer_pin_support import (
    INPUT_RULE_ID,
    RULE_ID,
    component_peer_coverage,
    lint_report,
    peer_component_pin_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint]


@pytest.mark.parametrize(
    ("observed", "rule_id", "expected_status"),
    (
        pytest.param(
            peer_component_pin_netlist(symbols={"U1": "Synthetic:A", "U2": "Synthetic:B"}),
            RULE_ID,
            "NO_COMPARABLE_PEERS",
            id="different-symbols",
        ),
        pytest.param(
            peer_component_pin_netlist(missing_inventory=("U2",)),
            RULE_ID,
            "INCOMPLETE_PIN_INVENTORY",
            id="missing-inventory",
        ),
        pytest.param(
            peer_component_pin_netlist(pin_electrical_types=("input", "output")),
            RULE_ID,
            "NO_MATCHING_PIN_TYPES",
            id="nonmatching-native-types",
        ),
        pytest.param(
            peer_component_pin_netlist(
                pin_electrical_types=("input", "input"),
                pin_functions=(None, "IN"),
            ),
            INPUT_RULE_ID,
            "NO_COMPATIBLE_PIN_FUNCTIONS",
            id="missing-required-functions",
        ),
        pytest.param(
            peer_component_pin_netlist(ambiguous_pins=("U1",)),
            RULE_ID,
            "NO_UNAMBIGUOUS_ASSIGNMENTS",
            id="ambiguous-assignment",
        ),
        pytest.param(
            peer_component_pin_netlist(
                references=("U1", "U2", "U3", "U4"),
                pin_nets=("VOUT", None, "VOUT", None),
                symbols={
                    "U1": "Synthetic:Complete",
                    "U2": "Synthetic:Complete",
                    "U3": "Synthetic:Incomplete",
                    "U4": "Synthetic:Incomplete",
                },
                missing_inventory=("U4",),
            ),
            RULE_ID,
            "PARTIALLY_EVALUATED",
            id="mixed-complete-and-incomplete-groups",
        ),
        pytest.param(
            peer_component_pin_netlist(
                references=("U1", "U2", "U3", "U4"),
                pin_nets=("VOUT", None, "VOUT", None),
                symbols={
                    "U1": "Synthetic:Complete",
                    "U2": "Synthetic:Complete",
                    "U3": "Synthetic:AliasA",
                    "U4": "Synthetic:AliasB",
                },
                part_ids={"U3": "SYNTHETIC-PART", "U4": "synthetic-part"},
                footprints={"U3": "Synthetic:Module", "U4": "Synthetic:OtherModule"},
            ),
            RULE_ID,
            "PARTIALLY_EVALUATED",
            id="valid-exact-peer-group-with-ineligible-part-id-alias-group",
        ),
    ),
)
def test_component_peer_coverage_explains_applicability_and_skips(
    observed: NetlistContract, rule_id: str, expected_status: str
) -> None:
    report = lint_report(observed)
    coverage = component_peer_coverage(report, rule_id)

    assert coverage.status == expected_status
    assert coverage.netlist_sha256 == report.netlist_sha256
    assert coverage.finding_count == sum(item.rule_id == rule_id for item in report.findings)
    if expected_status == "PARTIALLY_EVALUATED":
        if coverage.part_id_candidate_group_count:
            assert coverage.exact_symbol_peer_group_count == 1
            assert coverage.complete_pin_inventory_group_count == 1
            assert coverage.incomplete_pin_inventory_group_count == 0
            assert coverage.part_id_incomplete_component_identity_references == ("U3", "U4")
        else:
            assert coverage.exact_symbol_peer_group_count == 2
            assert coverage.complete_pin_inventory_group_count == 1
            assert coverage.incomplete_pin_inventory_group_count == 1
            assert coverage.incomplete_pin_inventory_references == ("U3", "U4")
        assert coverage.candidate_group_count == coverage.finding_count == 1


def test_component_peer_coverage_records_control_input_suppression() -> None:
    report = lint_report(
        peer_component_pin_netlist(
            pin_electrical_types=("input", "input"),
            pin_function="RESET_B",
        )
    )
    coverage = component_peer_coverage(report, INPUT_RULE_ID)

    assert coverage.status == "EVALUATED"
    assert coverage.candidate_group_count == 1
    assert coverage.finding_count == 0
    assert coverage.suppressed_candidate_count == 1


def test_native_fixture_sources_match_reviewed_digests() -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures/design_lint"
    expected = {
        "component-peer-power-output-native/control.kicad_sch": "3b41f81891115ae3e324694f46e41fbe44fb737c86555aa873333aa225b6f34b",
        "component-peer-power-output-native/fault.kicad_sch": "76cd57afa2e87980e9914a6508066e7197812bacd68241fe9e29ffd618bb9ff4",
        "component-peer-signal-output-native/control.kicad_sch": "bc5d93308322cd66b404bf058afde73b7b538e5590d84160d26b65af2e53f355",
        "component-peer-signal-output-native/fault.kicad_sch": "0d45eef6e2fc66da65781bb0e06d5c7601788aeb37489e60bf1302bfdad6a04a",
        "component-peer-signal-input-native/control.kicad_sch": "961527991bc45a4545bbf980a7540e81207c0012fa3fbe20772589970b507e15",
        "component-peer-signal-input-native/fault.kicad_sch": "9d3293d4c7d536549decad392096f118ad0f8cab6e62926572c9784f46f45275",
        "component-peer-bidirectional-native/control.kicad_sch": "1ea8f0a5b92fab8fafd0170adbe6b374f8bc9c24f38b00c00a0ceaafa70e2aa0",
        "component-peer-bidirectional-native/fault.kicad_sch": "5811d43e0298fb4bd8443bf849e8e75665e693561b4981786e768c0c895f4ea3",
    }

    assert {
        name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest() for name in expected
    } == expected


def test_power_output_native_fixture_readme_hashes_match_sources() -> None:
    fixture_dir = (
        Path(__file__).resolve().parent / "fixtures/design_lint/component-peer-power-output-native"
    )
    readme = (fixture_dir / "README.md").read_text(encoding="utf-8")
    for name in ("control.kicad_sch", "fault.kicad_sch"):
        digest = hashlib.sha256((fixture_dir / name).read_bytes()).hexdigest()
        assert f"- `{name}`: `{digest}`" in readme
