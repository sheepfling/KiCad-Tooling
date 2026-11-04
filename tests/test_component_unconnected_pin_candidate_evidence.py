"""Typed source and report projections for unconnected component power pins."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.component_pin_patterns import (
    UnconnectedGenericPowerInputComponentPin,
    UnconnectedGenericPowerOutputComponentPin,
    UnconnectedNamedComponentPin,
    UnconnectedNamedComponentPinCategory,
    unconnected_generic_power_input_component_pins,
    unconnected_generic_power_output_component_pins,
    unconnected_named_component_pins,
)
from kicad_tooling.hwrepo.design_lint import candidates, fingerprint
from kicad_tooling.hwrepo.design_lint_component_unconnected_pin_candidate_evidence import (
    UnconnectedComponentPinCandidate,
    project_unconnected_component_pin_evidence,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from tests.design_lint_fixtures import (
    generic_component_power_input_netlist,
    generic_component_power_output_netlist,
    unconnected_component_power_pins,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.evidence_lint]


@pytest.mark.parametrize(
    ("category", "rule_id"),
    [
        ("supply", "component.unconnected_supply_pin"),
        ("return", "component.unconnected_return_pin"),
    ],
)
def test_named_pin_candidates_retain_source_and_preserve_open_pin_evidence(
    category: UnconnectedNamedComponentPinCategory,
    rule_id: str,
) -> None:
    source = UnconnectedNamedComponentPin(
        pin="U1.3",
        function="VDD" if category == "supply" else "GND",
        category=category,
    )
    candidate = UnconnectedComponentPinCandidate.from_source_evidence(
        source,
        subject=f"{source.pin}: {source.function}",
        message=(
            f"This component's named {category} pin has no net assignment. "
            "Review whether the pin is intentionally unused or a connection is missing."
        ),
    )

    assert candidate.source_evidence is source
    assert candidate.rule_id == rule_id
    assert candidate.evidence == {"U1.3": ()}
    assert project_unconnected_component_pin_evidence(source).evidence == {"U1.3": ()}


@pytest.mark.parametrize(
    ("source", "rule_id", "expected_evidence"),
    [
        (
            UnconnectedGenericPowerInputComponentPin(
                pin="U1.1",
                symbol="Synthetic:GenericPowerInputComponent",
                function="1",
                electrical_type="power_in",
            ),
            "component.unconnected_power_input",
            {
                "symbol": ("Synthetic:GenericPowerInputComponent",),
                "pin_electrical_type": ("power_in",),
                "U1.1": (),
                "native_pin_function": ("1",),
            },
        ),
        (
            UnconnectedGenericPowerOutputComponentPin(
                pin="U1.2",
                symbol="Synthetic:GenericPowerOutputComponent",
                function=None,
                electrical_type="power_out",
            ),
            "component.unconnected_power_output",
            {
                "symbol": ("Synthetic:GenericPowerOutputComponent",),
                "pin_electrical_type": ("power_out",),
                "U1.2": (),
            },
        ),
    ],
)
def test_generic_power_pin_candidates_preserve_optional_function_evidence(
    source: UnconnectedGenericPowerInputComponentPin | UnconnectedGenericPowerOutputComponentPin,
    rule_id: str,
    expected_evidence: dict[str, tuple[str, ...]],
) -> None:
    candidate = UnconnectedComponentPinCandidate.from_source_evidence(
        source,
        subject=f"{source.pin}: generic native power pin is unassigned",
        message="Review whether this pin is intentionally open.",
    )

    assert candidate.source_evidence is source
    assert candidate.rule_id == rule_id
    assert candidate.evidence == expected_evidence


def test_candidate_rejects_rule_or_wire_evidence_that_disagrees_with_source() -> None:
    source = UnconnectedNamedComponentPin(pin="U1.3", function="VDD", category="supply")

    with pytest.raises(ValueError, match="source evidence"):
        UnconnectedComponentPinCandidate(
            rule_id="component.unconnected_return_pin",
            subject="U1.3: VDD",
            message="Review the open pin.",
            evidence={"U1.3": ()},
            source_evidence=source,
        )
    with pytest.raises(ValueError, match="typed projection"):
        UnconnectedComponentPinCandidate(
            rule_id="component.unconnected_supply_pin",
            subject="U1.3: VDD",
            message="Review the open pin.",
            evidence={"U1.4": ()},
            source_evidence=source,
        )


def test_aggregate_candidates_retain_all_four_unconnected_pin_source_types() -> None:
    named_netlist = unconnected_component_power_pins()
    named_sources = {
        source.category: source for source in unconnected_named_component_pins(named_netlist)
    }
    power_input_netlist = generic_component_power_input_netlist()
    power_output_netlist = generic_component_power_output_netlist()
    cases = (
        (
            named_netlist,
            "component.unconnected_supply_pin",
            named_sources["supply"],
        ),
        (
            named_netlist,
            "component.unconnected_return_pin",
            named_sources["return"],
        ),
        (
            power_input_netlist,
            "component.unconnected_power_input",
            unconnected_generic_power_input_component_pins(power_input_netlist)[0],
        ),
        (
            power_output_netlist,
            "component.unconnected_power_output",
            unconnected_generic_power_output_component_pins(power_output_netlist)[0],
        ),
    )

    for observed, rule_id, expected_source in cases:
        candidate = next(item for item in candidates(observed) if item.rule_id == rule_id)
        assert isinstance(candidate, UnconnectedComponentPinCandidate)
        assert candidate.source_evidence == expected_source
        legacy_projection = Candidate(
            rule_id=candidate.rule_id,
            subject=candidate.subject,
            message=candidate.message,
            evidence=candidate.evidence,
        )
        assert fingerprint(candidate) == fingerprint(legacy_projection)
