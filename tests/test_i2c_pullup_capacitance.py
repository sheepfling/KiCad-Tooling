"""Source-bound mapped capacitance checks for I2C pull-up windows."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.bus_heuristics import i2c_pullup_checks
from kicad_tooling.hwrepo.i2c_pullup_models import (
    I2cPullupCapacitanceContributorRequirement,
    I2cPullupCapacitanceScope,
)
from kicad_tooling.hwrepo.models import ElectricalCheck
from tests.design_lint_fixtures.i2c_arrays import (
    array_netlist_with_capacitor,
    array_requirement_with_capacitance_scope,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint]

CAPACITANCE_SCOPE = "i2c-pullup/main/sda/electrical-window/capacitance-scope"


def _check(
    *,
    value: str = "10p",
    part_id: str | None = "SYNTHETIC-CAP-10P",
    return_net: str = "GND",
    extra_capacitor: bool = False,
    maximum_effective_capacitance_pf: float = 12.0,
    maximum_residual_capacitance_pf: float = 25.0,
) -> ElectricalCheck:
    requirement = array_requirement_with_capacitance_scope(
        maximum_effective_capacitance_pf=maximum_effective_capacitance_pf,
        maximum_residual_capacitance_pf=maximum_residual_capacitance_pf,
    )
    observed = array_netlist_with_capacitor(
        value=value,
        part_id=part_id,
        return_net=return_net,
        extra_capacitor=extra_capacitor,
    )
    return next(
        check for check in i2c_pullup_checks(requirement, observed) if check.id == CAPACITANCE_SCOPE
    )


def test_exact_fitted_capacitor_and_residual_bound_pass() -> None:
    check = _check()

    assert check.status == "PASS"
    assert check.observed == 37.0
    assert "C1≤12pF" in check.detail
    assert "total upper bound 37.0pF versus bus maximum 50.0pF" in check.detail


def test_unmapped_capacitor_on_the_bus_line_fails_scope() -> None:
    check = _check(extra_capacitor=True)

    assert check.status == "FAIL"
    assert "unmapped fitted capacitors on I2C_SDA: C2" in check.detail


def test_changed_part_identity_fails_mapped_capacitor() -> None:
    check = _check(part_id="SYNTHETIC-CAP-22P")

    assert check.status == "FAIL"
    assert "C1 PART_ID is SYNTHETIC-CAP-22P" in check.detail


def test_changed_symbol_footprint_or_pin_inventory_fails_exact_mapping() -> None:
    requirement = array_requirement_with_capacitance_scope()
    cases = (
        (
            {"component_symbols": {"C1": "Device:R"}},
            "C1 symbol is Device:R; expected Device:C",
        ),
        (
            {
                "components": {
                    "C1": array_netlist_with_capacitor()
                    .components["C1"]
                    .model_copy(update={"footprint": "Synthetic:0402"})
                }
            },
            "C1 footprint is Synthetic:0402; expected Synthetic:0603",
        ),
        (
            {"component_pin_numbers": {"C1": ("1", "2", "3")}},
            "C1 native pins are ('1', '2', '3')",
        ),
    )

    for update, expected_issue in cases:
        observed = array_netlist_with_capacitor().model_copy(update=update)
        check = next(
            item
            for item in i2c_pullup_checks(requirement, observed)
            if item.id == CAPACITANCE_SCOPE
        )

        assert check.status == "FAIL"
        assert expected_issue in check.detail


def test_nominal_value_outside_reviewed_range_fails_mapped_capacitor() -> None:
    check = _check(value="22p")

    assert check.status == "FAIL"
    assert "C1 nominal capacitance is 22pF, outside 5.0–15.0pF" in check.detail


def test_wrong_return_net_fails_exact_pin_mapping() -> None:
    check = _check(return_net="GND_ALT")

    assert check.status == "FAIL"
    assert "C1.2=('GND_ALT',)" in check.detail
    assert "expected I2C_SDA and GND" in check.detail


def test_accounted_effective_capacitance_cannot_exceed_bus_maximum() -> None:
    check = _check(maximum_effective_capacitance_pf=30.0)

    assert check.status == "FAIL"
    assert "mapped effective capacitance plus residual bound is 55.0pF" in check.detail


def test_dnp_mapped_capacitor_cannot_satisfy_a_required_contributor() -> None:
    requirement = array_requirement_with_capacitance_scope()
    observed = array_netlist_with_capacitor().model_copy(update={"dnp_components": ("C1",)})

    check = next(
        item for item in i2c_pullup_checks(requirement, observed) if item.id == CAPACITANCE_SCOPE
    )

    assert check.status == "FAIL"
    assert "C1 is DNP but required as a capacitance contributor" in check.detail


def test_capacitance_check_is_stable_when_native_maps_are_reordered() -> None:
    requirement = array_requirement_with_capacitance_scope()
    observed = array_netlist_with_capacitor(extra_capacitor=True)
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "components": dict(reversed(tuple(observed.components.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
        }
    )

    original_check = next(
        check for check in i2c_pullup_checks(requirement, observed) if check.id == CAPACITANCE_SCOPE
    )
    reordered_check = next(
        check
        for check in i2c_pullup_checks(requirement, reordered)
        if check.id == CAPACITANCE_SCOPE
    )

    assert original_check == reordered_check


def test_capacitance_contract_rejects_noncapacitor_references() -> None:
    source = array_requirement_with_capacitance_scope().buses[0].sda.electrical_window
    assert source is not None
    assert source.capacitance_scope is not None
    contributor = source.capacitance_scope.contributors[0].model_dump()
    contributor["reference"] = "R1"
    contributor["signal_pin"] = "R1.1"
    contributor["return_pin"] = "R1.2"

    with pytest.raises(ValidationError, match="C-prefixed"):
        I2cPullupCapacitanceContributorRequirement.model_validate(contributor)


def test_capacitance_contract_rejects_duplicate_casefolded_references() -> None:
    source = array_requirement_with_capacitance_scope().buses[0].sda.electrical_window
    assert source is not None
    assert source.capacitance_scope is not None
    contributor = source.capacitance_scope.contributors[0].model_dump()
    second = {**contributor, "reference": "c1", "signal_pin": "c1.1", "return_pin": "c1.2"}
    scope = source.capacitance_scope.model_dump()
    scope["contributors"] = (contributor, second)

    with pytest.raises(ValidationError, match="references must be unique"):
        I2cPullupCapacitanceScope.model_validate(scope)
