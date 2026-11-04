"""Typed source and report projections for LED topology findings."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.component_roles import component_role_binding_digest
from kicad_tooling.hwrepo.design_lint_led_candidate_evidence import (
    LedTopologyCandidate,
    project_led_candidate_evidence,
)
from kicad_tooling.hwrepo.led_heuristics import (
    DirectLedRailBridge,
    LedOutputWithoutVisibleSeriesResistor,
)
from tests.design_lint_fixtures.component_roles import custom_led_role_map

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.evidence_lint]


def test_direct_rail_bridge_candidate_retains_source_and_existing_wire_fields() -> None:
    source = DirectLedRailBridge(
        reference="D1",
        symbol="Device:LED",
        pins=("D1.1", "D1.2"),
        positive_net="+3V3",
        return_net="GND",
    )

    candidate = LedTopologyCandidate.from_source_evidence(
        source,
        subject="D1: LED directly spans supply and return",
        message="Review this direct rail bridge.",
    )

    assert candidate.source_evidence is source
    assert candidate.rule_id == "component.led_directly_across_supply_and_return"
    assert candidate.evidence == {
        "symbol": ("Device:LED",),
        "led_pins": ("D1.1", "D1.2"),
        "positive_net": ("+3V3",),
        "return_net": ("GND",),
    }
    assert project_led_candidate_evidence(source).evidence == candidate.evidence


def test_output_driven_candidate_retains_role_binding_and_its_digest() -> None:
    binding = custom_led_role_map().entries[0]
    source = LedOutputWithoutVisibleSeriesResistor(
        reference="D1",
        symbol=binding.symbol,
        led_pins=("D1.1", "D1.2"),
        output_pins=("U1.1",),
        output_pin_types=("U1.1=output",),
        driven_net="GPIO_LED",
        opposite_net="GND",
        opposite_net_role="return",
        role_binding=binding,
        role_binding_sha256=component_role_binding_digest(binding),
    )

    candidate = LedTopologyCandidate.from_source_evidence(
        source,
        subject="D1: LED directly shares an output net and a rail",
        message="Review the output-driven LED path.",
    )

    assert candidate.source_evidence is source
    assert candidate.rule_id == "component.led_directly_driven_from_output"
    assert candidate.evidence == {
        "symbol": (binding.symbol,),
        "led_pins": ("D1.1", "D1.2"),
        "output_pins": ("U1.1",),
        "output_pin_types": ("U1.1=output",),
        "driven_net": ("GPIO_LED",),
        "opposite_net": ("GND",),
        "opposite_net_role": ("return",),
        "classified_role": ("led",),
        "role_part_id": (binding.part_id,),
        "role_symbol": (binding.symbol,),
        "role_footprint": (binding.footprint,),
        "role_pin_inventory": ("1=A/passive", "2=K/passive"),
        "role_basis": (binding.basis,),
        "role_binding_sha256": (component_role_binding_digest(binding),),
    }


def test_output_driven_projection_rejects_stale_role_digest_and_incomplete_topology() -> None:
    binding = custom_led_role_map().entries[0]
    source = LedOutputWithoutVisibleSeriesResistor(
        reference="D1",
        symbol=binding.symbol,
        led_pins=("D1.1", "D1.2"),
        output_pins=("U1.1",),
        output_pin_types=("U1.1=output",),
        driven_net="GPIO_LED",
        opposite_net="GND",
        opposite_net_role="return",
        role_binding=binding,
        role_binding_sha256="stale-digest",
    )

    with pytest.raises(ValueError, match="exact binding and digest"):
        project_led_candidate_evidence(source)

    incomplete = LedOutputWithoutVisibleSeriesResistor(
        reference="D1",
        symbol="Device:LED",
        led_pins=("D1.1", "D1.1"),
        output_pins=("U1.1",),
        output_pin_types=("U1.1=output",),
        driven_net="GPIO_LED",
        opposite_net="GND",
        opposite_net_role="return",
    )
    with pytest.raises(ValueError, match="complete rail-spanning path"):
        project_led_candidate_evidence(incomplete)
