"""Power-input source-anchor and connector-scope review cases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.models import ComponentContract, DesignLintIgnore, DesignLintPolicy
from kicad_tooling.hwrepo.power_pin_paths import power_inputs_without_supported_source_paths
from tests.design_lint_fixtures.power_input_paths import (
    RULE_ID,
    external_source_netlist,
    lint_report,
    power_path_map,
    regulator_source_netlist,
    source_path_netlist,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]


def test_unrecognized_external_connector_source_becomes_a_coverage_review() -> None:
    netlist = external_source_netlist(power_out=False)
    report = lint_report(netlist)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert finding.evidence["recognized_source_nets"] == ()
    assert finding.evidence["source_anchor_state"] == ("not_recognized",)
    assert "custom rail names, external connector supplies" in finding.message


def test_external_connector_power_out_is_a_source_anchor_control() -> None:
    netlist = external_source_netlist(power_out=True)
    assert RULE_ID not in {item.rule_id for item in candidates(netlist)}


def test_dnp_external_power_out_does_not_anchor_the_assembly() -> None:
    netlist = external_source_netlist(power_out=True, source_dnp=True)
    finding = next(item for item in candidates(netlist) if item.rule_id == RULE_ID)
    assert finding.evidence["recognized_source_nets"] == ()
    assert finding.evidence["source_anchor_state"] == ("not_recognized",)


def test_isolated_external_supply_keeps_its_return_separate_and_reviewable() -> None:
    untyped_external = external_source_netlist(power_out=False, isolated_return=True)
    report = lint_report(untyped_external)
    finding = next(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert untyped_external.nets["ISO_RETURN"] == ("C1.2", "J1.2")
    assert "GND" not in untyped_external.nets
    ignored = lint_report(
        untyped_external,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records an intentionally isolated external supply",
                ),
            )
        ),
    )
    assert ignored.status == "PASS"
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )
    typed_external = external_source_netlist(power_out=True, isolated_return=True)
    assert typed_external.nets["ISO_RETURN"] == ("C1.2", "J1.2")
    assert RULE_ID not in {item.rule_id for item in candidates(typed_external)}


@pytest.mark.parametrize(
    ("symbol", "expected"),
    (
        pytest.param("Vendor:Power_Capacitor", True, id="recognizable-custom-capacitor"),
        pytest.param("Vendor:CAP123", False, id="opaque-custom-symbol"),
    ),
)
def test_recognized_custom_capacitor_name_counts_but_arbitrary_symbol_does_not(
    symbol, expected
) -> None:
    netlist = source_path_netlist(wrong_rail=True, capacitor_symbol=symbol)
    assert (RULE_ID in {item.rule_id for item in candidates(netlist)}) is expected


@pytest.mark.parametrize(
    ("regulator_dnp", "expected_finding"),
    (
        pytest.param(False, False, id="fitted-regulator-anchor"),
        pytest.param(True, True, id="dnp-regulator-not-an-anchor"),
    ),
)
def test_fitted_regulator_output_is_an_anchor_but_dnp_output_is_not(
    regulator_dnp, expected_finding
) -> None:
    netlist = regulator_source_netlist(regulator_dnp=regulator_dnp)
    findings = [item for item in candidates(netlist) if item.rule_id == RULE_ID]
    assert bool(findings) is expected_finding
    if expected_finding:
        assert findings[0].evidence["recognized_source_nets"] == ("VIN",)


def test_connector_power_inputs_are_outside_this_review() -> None:
    source = source_path_netlist(wrong_rail=True)
    components = dict(source.components)
    components.pop("U2")
    components["J2"] = ComponentContract(value="Synthetic connector", footprint="")
    symbols = dict(source.component_symbols)
    symbols.pop("U2")
    symbols["J2"] = "Connector_Generic:Conn_01x02"
    pin_numbers = dict(source.component_pin_numbers)
    pin_numbers.pop("U2")
    pin_numbers["J2"] = ("1", "2")
    nets = {
        net: tuple("J2.1" if pin == "U2.1" else pin for pin in pins)
        for net, pins in source.nets.items()
    }
    connector = source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "nets": nets,
            "pin_electrical_types": {"U1.1": "power_out", "J2.1": "power_in"},
        }
    )
    assert RULE_ID not in {item.rule_id for item in candidates(connector)}


def test_standard_connector_identity_under_nonstandard_reference_is_excluded() -> None:
    source = source_path_netlist(wrong_rail=True)
    components = dict(source.components)
    components["U7"] = components.pop("U2")
    symbols = dict(source.component_symbols)
    symbols["U7"] = "Connector_Generic:Conn_01x02"
    symbols.pop("U2")
    pin_numbers = dict(source.component_pin_numbers)
    pin_numbers["U7"] = pin_numbers.pop("U2")
    nets = {
        net: tuple("U7.1" if pin == "U2.1" else pin for pin in pins)
        for net, pins in source.nets.items()
    }
    standard_connector = source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "nets": nets,
            "pin_electrical_types": {"U1.1": "power_out", "U7.1": "power_in"},
        }
    )
    assert RULE_ID not in {item.rule_id for item in candidates(standard_connector)}
    custom_connector = standard_connector.model_copy(
        update={"component_symbols": {**symbols, "U7": "Custom:Interface"}}
    )
    assert RULE_ID in {item.rule_id for item in candidates(custom_connector)}
    assert (
        power_inputs_without_supported_source_paths(
            custom_connector, declared_connector_references=("U7",)
        )
        == ()
    )


def test_project_map_covers_its_endpoint_without_duplicate_heuristic() -> None:
    report = lint_report(
        source_path_netlist(wrong_rail=True), DesignLintPolicy(power_path_map=power_path_map())
    )
    ids = {item.rule_id for item in report.findings}
    assert "power.mapped_series_path_mismatch" in ids
    assert RULE_ID not in ids
