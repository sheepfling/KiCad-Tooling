"""Same-net two-pin findings retain their exact typed scan records."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.component_role_models import (
    ComponentRoleBinding,
    ComponentRoleMap,
    ComponentRolePin,
)
from kicad_tooling.hwrepo.component_roles import component_role_binding_report_fields
from kicad_tooling.hwrepo.design_lint_two_pin_candidate_evidence import (
    TwoPinComponentFindingEvidence,
    TwoPinSameNetCandidate,
    project_two_pin_component_evidence,
)
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.two_pin_buzzers import two_pin_buzzer_same_net_candidates
from kicad_tooling.hwrepo.two_pin_components import (
    TwoPinComponentOnSameNet,
    two_pin_components_on_same_net,
)

_SYMBOLS = {
    "diode": "Device:D",
    "crystal": "Device:Crystal",
    "fuse": "Device:Fuse",
    "polyfuse": "Device:Polyfuse",
    "ferrite_bead": "Device:FerriteBead",
    "switch": "Switch:SW_SPST",
    "led": "Device:LED",
    "buzzer": "Device:Buzzer",
    "speaker": "Device:Speaker",
    "battery": "Device:Battery",
    "motor": "Motor:Motor_DC",
    "solar_cell": "Device:Solar_Cell",
    "thermocouple": "Device:Thermocouple",
    "resistor": "Device:R",
    "capacitor": "Device:C",
    "inductor": "Device:L",
    "varistor": "Device:Varistor",
    "thermistor": "Device:Thermistor",
}


def _two_pin_scan(
    kind: str,
    *,
    role_binding: ComponentRoleBinding | None = None,
    net: str = "BYPASSED",
    value: str = "10k",
) -> tuple[NetlistContract, TwoPinComponentOnSameNet]:
    reference = "C7" if role_binding is not None else "R1"
    symbol = role_binding.symbol if role_binding is not None else _SYMBOLS[kind]
    pin_numbers = (
        tuple(pin.number for pin in role_binding.pins) if role_binding is not None else ("1", "2")
    )
    footprint = role_binding.footprint if role_binding is not None else "Synthetic:TwoPin"
    part_id = role_binding.part_id if role_binding is not None else None
    components = {reference: ComponentContract(value=value, footprint=footprint, part_id=part_id)}
    nets = {net: tuple(f"{reference}.{number}" for number in pin_numbers)}
    observed = NetlistContract(
        components=components,
        nets=nets,
        component_symbols={reference: symbol},
        component_pin_numbers={reference: pin_numbers},
        pin_functions=(
            {}
            if role_binding is None
            else {f"{reference}.{pin.number}": pin.function for pin in role_binding.pins}
        ),
        pin_electrical_types=(
            {}
            if role_binding is None
            else {f"{reference}.{pin.number}": pin.electrical_type for pin in role_binding.pins}
        ),
    )
    role_map = None if role_binding is None else ComponentRoleMap(entries=(role_binding,))
    findings = two_pin_components_on_same_net(observed, role_map)
    assert len(findings) == 1
    return observed, findings[0]


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
        pytest.param("led", "component.two_pin_led_same_net", None, id="led"),
        pytest.param("buzzer", "component.two_pin_buzzer_same_net", None, id="buzzer"),
        pytest.param("speaker", "component.two_pin_speaker_same_net", None, id="speaker"),
        pytest.param("battery", "component.two_pin_battery_same_net", None, id="battery"),
        pytest.param("motor", "component.two_pin_motor_same_net", None, id="motor"),
        pytest.param("solar_cell", "component.two_pin_solar_cell_same_net", None, id="solar-cell"),
        pytest.param(
            "thermocouple", "component.two_pin_thermocouple_same_net", None, id="thermocouple"
        ),
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
    kind_field: str | None,
) -> None:
    observed, component = _two_pin_scan(kind, value="10k")
    source = TwoPinComponentFindingEvidence(component)
    candidate = TwoPinSameNetCandidate.from_source_evidence(
        source,
        subject="R1: same-net two-pin review",
        message="Review the bypassed component.",
    )

    assert candidate.rule_id == rule_id
    expected_evidence = {
        "symbol": (component.symbol,),
        "value": ("10k",),
        "net": ("BYPASSED",),
        "pin_assignments": ("R1.1 -> BYPASSED", "R1.2 -> BYPASSED"),
    }
    if kind_field is not None:
        expected_evidence[kind_field] = (kind,)

    assert dict(project_two_pin_component_evidence(source).evidence) == expected_evidence
    assert candidate.source_evidence is source
    assert component.source_netlist is observed


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
    _, component = _two_pin_scan("capacitor", role_binding=binding, value="1uF")
    source = TwoPinComponentFindingEvidence(component)

    evidence = project_two_pin_component_evidence(source).evidence

    assert tuple(evidence) == (
        "symbol",
        "value",
        "net",
        "pin_assignments",
        "passive_kind",
        "classified_role",
        "role_part_id",
        "role_symbol",
        "role_footprint",
        "role_pin_inventory",
        "role_basis",
        "role_binding_sha256",
    )
    assert evidence["classified_role"] == ("capacitor",)
    assert evidence["role_part_id"] == ("custom-capacitor-1",)
    assert evidence["role_pin_inventory"] == ("1=CAP+/passive", "2=CAP-/passive")
    assert (
        evidence["role_binding_sha256"]
        == component_role_binding_report_fields(binding)["role_binding_sha256"]
    )


def test_two_pin_finding_rejects_a_projection_mismatch() -> None:
    _, component = _two_pin_scan("fuse", net="+3V3")
    source = TwoPinComponentFindingEvidence(component)

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
            TwoPinComponentOnSameNet(
                "D1", "Custom:Unsupported", "red", "unsupported", ("1", "2"), "N1"
            )
        )


def test_two_pin_evidence_rejects_a_different_netlist_source() -> None:
    observed, component = _two_pin_scan("buzzer")
    other_source, _ = _two_pin_scan("buzzer", net="OTHER")

    with pytest.raises(ValueError, match="retained source netlist"):
        TwoPinComponentFindingEvidence(replace(component, source_netlist=other_source))

    candidate = two_pin_buzzer_same_net_candidates((component,))[0]
    assert isinstance(candidate, TwoPinSameNetCandidate)
    assert candidate.source_evidence.component.source_netlist is observed
