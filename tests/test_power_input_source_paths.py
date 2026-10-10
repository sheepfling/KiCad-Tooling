"""Power-input source-path topology heuristic fault and control cases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.power_pin_paths import power_inputs_without_supported_source_paths
from tests.design_lint_fixtures.power_input_paths import (
    RULE_ID,
    lint_report,
    series_diode_netlist,
    series_jumper_netlist,
    series_three_pin_jumper_netlist,
    source_path_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]


def test_wrong_rail_with_fitted_decoupling_is_reviewed_without_authored_map() -> None:
    report = lint_report(source_path_netlist(wrong_rail=True))
    findings = [item for item in report.findings if item.rule_id == RULE_ID]
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].subject == "VLOAD: power-input source-path review"
    assert findings[0].evidence == {
        "net": ("VLOAD",),
        "power_input_pins": ("U2.1",),
        "fitted_capacitors_to_return": ("C1",),
        "recognized_source_nets": ("VIN",),
        "source_anchor_state": ("recognized",),
    }
    assert "does not prove that a connection is required" in findings[0].message


@pytest.mark.parametrize(
    "netlist",
    (
        pytest.param(source_path_netlist(), id="ferrite"),
        pytest.param(
            source_path_netlist(series_symbol="Device:R", series_value="0R"), id="zero-ohm"
        ),
        pytest.param(
            source_path_netlist(series_symbol="Device:R", series_value="1R"), id="one-ohm"
        ),
        pytest.param(source_path_netlist(source_less_name_only=True), id="named-rail-anchor"),
    ),
)
def test_valid_ferrite_low_resistance_and_named_rail_paths_are_controls(netlist) -> None:
    assert RULE_ID not in {item.rule_id for item in candidates(netlist)}


@pytest.mark.parametrize("symbol", ("Device:D", "Device:D_Schottky"))
def test_forward_series_diodes_with_exact_native_identity_and_pin_roles_are_controls(
    symbol,
) -> None:
    netlist = series_diode_netlist(symbol=symbol)
    assert RULE_ID not in {item.rule_id for item in candidates(netlist)}


def test_exact_fitted_bridged_solder_jumper_is_a_bidirectional_control() -> None:
    netlist = series_jumper_netlist()
    assert RULE_ID not in {item.rule_id for item in candidates(netlist)}


@pytest.mark.parametrize(
    "netlist",
    (
        pytest.param(
            series_three_pin_jumper_netlist(
                symbol="Jumper:SolderJumper_3_Bridged12", source_pin="1", load_pin="2"
            ),
            id="bridged-12",
        ),
        pytest.param(
            series_three_pin_jumper_netlist(
                symbol="Jumper:SolderJumper_3_Bridged123", source_pin="1", load_pin="3"
            ),
            id="bridged-123",
        ),
    ),
)
def test_exact_three_terminal_bridge_topologies_are_recognized(netlist) -> None:
    assert RULE_ID not in {item.rule_id for item in candidates(netlist)}


def test_bridged12_does_not_infer_a_path_to_terminal_three() -> None:
    netlist = series_three_pin_jumper_netlist(
        symbol="Jumper:SolderJumper_3_Bridged12", source_pin="1", load_pin="3"
    )
    assert power_inputs_without_supported_source_paths(netlist)


@pytest.mark.parametrize(
    "netlist",
    (
        pytest.param(series_jumper_netlist(symbol="Jumper:SolderJumper_2_Open"), id="open-two-pin"),
        pytest.param(
            series_three_pin_jumper_netlist(symbol="Jumper:SolderJumper_3_Open"),
            id="open-three-pin",
        ),
        pytest.param(series_three_pin_jumper_netlist(dnp=True), id="dnp-three-pin"),
        pytest.param(
            series_three_pin_jumper_netlist(pin_numbers=("1", "2", "4")),
            id="wrong-three-pin-inventory",
        ),
        pytest.param(
            series_three_pin_jumper_netlist(pin_functions=("A", "B", "C")),
            id="wrong-three-pin-roles",
        ),
        pytest.param(
            series_three_pin_jumper_netlist(unassigned_pins=frozenset({"3"})),
            id="unassigned-terminal",
        ),
        pytest.param(series_jumper_netlist(dnp=True), id="dnp-bridged"),
        pytest.param(series_jumper_netlist(pin_numbers=("1", "3")), id="wrong-two-pin-inventory"),
        pytest.param(series_jumper_netlist(pin_functions=("A", "X")), id="unsupported-role"),
        pytest.param(series_jumper_netlist(pin_functions=("A", "A")), id="duplicate-role"),
    ),
)
def test_open_dnp_or_incompletely_mapped_solder_jumpers_remain_review_candidates(netlist) -> None:
    assert power_inputs_without_supported_source_paths(netlist)


@pytest.mark.parametrize(
    ("netlist", "expected"),
    (
        pytest.param(series_diode_netlist(reverse=True), True, id="reverse"),
        pytest.param(series_diode_netlist(dnp=True), True, id="dnp"),
        pytest.param(series_diode_netlist(symbol="Device:D_Zener"), True, id="unsupported-symbol"),
        pytest.param(
            series_diode_netlist(pin_functions=("K", "X")), True, id="unsupported-pin-roles"
        ),
        pytest.param(series_diode_netlist(pin_functions=("K", "K")), True, id="duplicate-pin-role"),
        pytest.param(series_diode_netlist(), False, id="forward-control"),
    ),
)
def test_reverse_dnp_unsupported_and_unmapped_diodes_do_not_count_as_source_paths(
    netlist, expected
) -> None:
    assert bool(power_inputs_without_supported_source_paths(netlist)) == expected


@pytest.mark.parametrize(
    ("netlist", "expected"),
    (
        pytest.param(
            source_path_netlist(series_symbol="Device:R", series_value="1.1R"),
            True,
            id="over-one-ohm",
        ),
        pytest.param(source_path_netlist(series_dnp=True), True, id="dnp-path"),
        pytest.param(
            source_path_netlist(series_symbol="Synthetic:Link"), True, id="unsupported-link-symbol"
        ),
        pytest.param(
            source_path_netlist(wrong_rail=True, capacitor_dnp=True), False, id="dnp-capacitor"
        ),
        pytest.param(
            source_path_netlist(wrong_rail=True, capacitor_present=False),
            False,
            id="no-return-capacitor",
        ),
        pytest.param(
            source_path_netlist(wrong_rail=True, source_present=False), True, id="no-source-anchor"
        ),
    ),
)
def test_only_recognized_fitted_paths_and_supported_metadata_count(netlist, expected) -> None:
    assert bool(power_inputs_without_supported_source_paths(netlist)) == expected


@pytest.mark.parametrize(
    "netlist",
    (
        pytest.param(
            source_path_netlist(series_symbol="Device:D", series_value="Schottky"),
            id="diode-without-native-role-map",
        ),
        pytest.param(
            source_path_netlist(series_symbol="Device:Jumper", series_value="Link"),
            id="generic-jumper",
        ),
        pytest.param(
            source_path_netlist(series_symbol="Custom:Ferrite_Bead", series_value="600R@100M"),
            id="custom-ferrite-symbol",
        ),
    ),
)
def test_unmapped_diode_generic_jumper_and_custom_library_paths_remain_review_candidates(
    netlist,
) -> None:
    assert RULE_ID in {item.rule_id for item in candidates(netlist)}
