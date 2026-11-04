"""Same-net two-pin findings retain their exact typed scan records."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.component_role_models import ComponentRoleBinding, ComponentRolePin
from kicad_tooling.hwrepo.component_roles import component_role_binding_evidence
from kicad_tooling.hwrepo.design_lint_two_pin_candidate_evidence import (
    TwoPinComponentFindingEvidence,
    TwoPinSameNetCandidate,
    project_two_pin_component_evidence,
)
from kicad_tooling.hwrepo.two_pin_components import TwoPinComponentOnSameNet


@pytest.mark.parametrize(
    ("kind", "rule_id", "kind_field"),
    [
        pytest.param("diode", "component.two_pin_diode_same_net", "component_kind", id="diode"),
        pytest.param(
            "crystal", "component.two_pin_crystal_same_net", "component_kind", id="crystal"
        ),
        pytest.param("fuse", "component.two_pin_fuse_same_net", "component_kind", id="fuse"),
        pytest.param(
            "polyfuse", "component.two_pin_fuse_same_net", "component_kind", id="polyfuse"
        ),
        pytest.param(
            "ferrite_bead", "component.two_pin_ferrite_same_net", "component_kind", id="ferrite"
        ),
        pytest.param("switch", "component.two_pin_switch_same_net", "component_kind", id="switch"),
        pytest.param(
            "resistor", "component.two_pin_passive_same_net", "passive_kind", id="resistor"
        ),
        pytest.param(
            "capacitor", "component.two_pin_passive_same_net", "passive_kind", id="capacitor"
        ),
        pytest.param(
            "inductor", "component.two_pin_passive_same_net", "passive_kind", id="inductor"
        ),
        pytest.param(
            "varistor", "component.two_pin_passive_same_net", "passive_kind", id="varistor"
        ),
        pytest.param(
            "thermistor", "component.two_pin_passive_same_net", "passive_kind", id="thermistor"
        ),
    ],
)
def test_two_pin_projection_preserves_rule_and_kind_specific_fields(
    kind: str,
    rule_id: str,
    kind_field: str,
) -> None:
    source = TwoPinComponentFindingEvidence(
        TwoPinComponentOnSameNet(
            reference="R1",
            symbol=f"Device:{kind}",
            value="10k",
            kind=kind,
            pin_numbers=("1", "2"),
            net="BYPASSED",
        )
    )
    candidate = TwoPinSameNetCandidate.from_source_evidence(
        source,
        subject="R1: same-net two-pin review",
        message="Review the bypassed component.",
    )

    assert candidate.rule_id == rule_id
    assert dict(project_two_pin_component_evidence(source).evidence) == {
        "symbol": (f"Device:{kind}",),
        "value": ("10k",),
        kind_field: (kind,),
        "net": ("BYPASSED",),
        "pin_assignments": ("R1.1 -> BYPASSED", "R1.2 -> BYPASSED"),
    }
    assert candidate.source_evidence is source


def test_two_pin_projection_keeps_authored_role_binding_evidence() -> None:
    binding = ComponentRoleBinding(
        part_id="custom-capacitor-1",
        symbol="Custom:TwoPin",
        footprint="Custom:Package",
        role="capacitor",
        pins=(
            ComponentRolePin(number="1", function="CAP+", electrical_type="passive"),
            ComponentRolePin(number="2", function="CAP-", electrical_type="passive"),
        ),
        basis="reviewed component datasheet",
    )
    source = TwoPinComponentFindingEvidence(
        TwoPinComponentOnSameNet(
            reference="C7",
            symbol="Custom:TwoPin",
            value="1uF",
            kind="capacitor",
            pin_numbers=("1", "2"),
            net="BYPASSED",
            role_binding=binding,
        )
    )

    evidence = project_two_pin_component_evidence(source).evidence

    assert evidence["classified_role"] == ("capacitor",)
    assert evidence["role_part_id"] == ("custom-capacitor-1",)
    assert evidence["role_pin_inventory"] == ("1=CAP+/passive", "2=CAP-/passive")
    assert (
        evidence["role_binding_sha256"]
        == component_role_binding_evidence(binding)["role_binding_sha256"]
    )


def test_two_pin_finding_rejects_a_projection_mismatch() -> None:
    source = TwoPinComponentFindingEvidence(
        TwoPinComponentOnSameNet("F1", "Device:Fuse", "0R", "fuse", ("1", "2"), "+3V3")
    )

    with pytest.raises(ValueError, match="typed source projection"):
        TwoPinSameNetCandidate(
            rule_id="component.two_pin_fuse_same_net",
            subject="review",
            message="inspect",
            evidence={"net": ("wrong",)},
            source_evidence=source,
        )


def test_two_pin_source_rejects_kinds_owned_by_other_candidate_routes() -> None:
    with pytest.raises(ValueError, match="Unsupported same-net component kind"):
        TwoPinComponentFindingEvidence(
            TwoPinComponentOnSameNet("D1", "Device:LED", "red", "led", ("1", "2"), "N1")
        )
