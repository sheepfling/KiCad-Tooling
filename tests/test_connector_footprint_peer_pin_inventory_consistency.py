"""Source-bound review of pin inventory differences across exact-part peers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_pin_inventory_consistency import (
    connector_footprint_peer_pin_inventory_disagreements,
)
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import lint_report, peer_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]

RULE_ID = "connector.footprint_peer_pin_inventory_disagreement"


def _source(
    *,
    part_ids: tuple[str | None, str | None] = ("SYNTHETIC-PART", "SYNTHETIC-PART"),
    extra_reference: str = "J2",
    extra_numbers: tuple[str, ...] = ("3",),
    anchor_assignments: tuple[str | None, str | None] = ("RETURN", "RETURN"),
    target_assignments: tuple[str | None, str | None] = ("DATA", "DATA"),
    extra_function: str = "VBUS",
    extra_electrical_type: str = "power_in",
    extra_assignment: str | None = "VBUS_NET",
    common_functions: tuple[tuple[str, str], tuple[str, str]] = (
        ("Pin_1", "Pin_1"),
        ("Pin_2", "Pin_2"),
    ),
    common_types: tuple[tuple[str, str], tuple[str, str]] = (
        ("passive", "passive"),
        ("passive", "passive"),
    ),
    missing_metadata_pin: str | None = None,
    dnp: tuple[str, ...] = (),
    same_symbol: bool = False,
):
    observed = peer_netlist(
        assignments=(anchor_assignments, target_assignments),
        part_id=part_ids[0],
        dnp=dnp,
    )
    components = dict(observed.components)
    components["J1"] = components["J1"].model_copy(update={"part_id": part_ids[0]})
    components["J2"] = components["J2"].model_copy(update={"part_id": part_ids[1]})
    pin_numbers = dict(observed.component_pin_numbers)
    pin_numbers[extra_reference] = (*pin_numbers[extra_reference], *extra_numbers)
    pin_functions = {
        **observed.pin_functions,
        "J1.1": common_functions[0][0],
        "J2.1": common_functions[0][1],
        "J1.2": common_functions[1][0],
        "J2.2": common_functions[1][1],
    }
    electrical_types = {
        **observed.pin_electrical_types,
        "J1.1": common_types[0][0],
        "J2.1": common_types[0][1],
        "J1.2": common_types[1][0],
        "J2.2": common_types[1][1],
    }
    nets = dict(observed.nets)
    for number in extra_numbers:
        pin = f"{extra_reference}.{number}"
        pin_functions[pin] = extra_function
        electrical_types[pin] = extra_electrical_type
        if extra_assignment is not None:
            nets[extra_assignment] = (pin,)
    if missing_metadata_pin is not None:
        pin_functions.pop(missing_metadata_pin, None)
        electrical_types.pop(missing_metadata_pin, None)
    symbols = dict(observed.component_symbols)
    if same_symbol:
        symbols["J2"] = symbols["J1"]
    return observed.model_copy(
        update={
            "components": components,
            "component_pin_numbers": pin_numbers,
            "pin_functions": pin_functions,
            "pin_electrical_types": electrical_types,
            "nets": nets,
            "component_symbols": symbols,
        }
    )


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_one_named_pin_inventory_difference_is_localized() -> None:
    observed = _source()

    (finding,) = _findings(lint_report(observed))

    assert finding.mode == "review"
    assert finding.subject == "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 3"
    assert finding.evidence["peer_identity_basis"] == ("part_id",)
    assert finding.evidence["peer_pin_inventories"] == ("J1=1,2", "J2=1,2,3")
    assert finding.evidence["extra_pin"] == ("J2.3",)
    assert finding.evidence["extra_pin_function"] == ("VBUS",)
    assert finding.evidence["extra_pin_electrical_type"] == ("power_in",)
    assert finding.evidence["extra_pin_assignments"] == ("J2.3=VBUS_NET",)
    assert finding.evidence["common_anchor_assignments"] == ("J1.1=RETURN", "J2.1=RETURN")
    assert (
        "does not establish whether the pin is missing or intentionally omitted" in finding.message
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "source",
    (
        pytest.param(_source(extra_numbers=()), id="matching-inventory"),
        pytest.param(_source(part_ids=(None, None)), id="missing-part-id"),
        pytest.param(_source(part_ids=("SYNTHETIC-PART", "OTHER-PART")), id="different-part-id"),
        pytest.param(
            _source(
                anchor_assignments=("RETURN_A", "RETURN_B"),
                target_assignments=("DATA_A", "DATA_B"),
            ),
            id="no-common-net-anchor",
        ),
        pytest.param(
            _source(common_functions=(("GND", "RETURN"), ("Pin_2", "Pin_2"))),
            id="common-function-metadata-disagrees",
        ),
        pytest.param(
            _source(common_types=(("passive", "input"), ("passive", "passive"))),
            id="common-electrical-type-metadata-disagrees",
        ),
        pytest.param(_source(extra_function="Pin_3"), id="generic-extra-pin-function"),
        pytest.param(_source(extra_electrical_type="~"), id="missing-extra-pin-type"),
        pytest.param(_source(missing_metadata_pin="J2.3"), id="missing-extra-pin-function"),
        pytest.param(_source(extra_assignment=None), id="unassigned-extra-pin"),
        pytest.param(_source(extra_numbers=("3", "4")), id="multiple-inventory-differences"),
        pytest.param(_source(dnp=("J2",)), id="dnp-peer"),
        pytest.param(_source(same_symbol=True), id="same-native-symbol"),
    ),
)
def test_incomplete_or_nonmatching_inventory_evidence_stays_quiet(source) -> None:
    assert connector_footprint_peer_pin_inventory_disagreements(source) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_pin_inventory_difference_is_localized_when_other_peer_has_extra_pin() -> None:
    (finding,) = connector_footprint_peer_pin_inventory_disagreements(_source(extra_reference="J1"))

    assert finding.evidence["extra_pin"] == ("J1.3",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_can_block_disable_or_ignore_the_exact_finding() -> None:
    observed = _source()
    default_finding = _findings(lint_report(observed))[0]
    blocked = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project promotes the exact-part symbol-inventory review.",
                ),
            )
        ),
    )
    disabled = lint_report(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project documents an approved pin subset symbol.",
                ),
            )
        ),
    )
    ignored = lint_report(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=default_finding.fingerprint,
                    reason="Synthetic project accepts this exact symbol inventory variation.",
                ),
            )
        ),
    )

    assert _findings(blocked)[0].mode == "block"
    assert _findings(disabled)[0].disposition == "RULE_OFF"
    assert _findings(ignored)[0].disposition == "IGNORED"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_finding_is_stable_under_source_mapping_reordering() -> None:
    observed = _source()
    shuffled = observed.model_copy(
        update={
            "components": dict(reversed(tuple(observed.components.items()))),
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(observed.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )

    first = _findings(lint_report(observed))[0]
    second = _findings(lint_report(shuffled))[0]

    assert (first.fingerprint, first.evidence) == (second.fingerprint, second.evidence)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_candidate_fields_cannot_be_forged_away_from_native_source() -> None:
    (candidate,) = connector_footprint_peer_pin_inventory_disagreements(_source())

    with pytest.raises(ValueError, match="must match its native source evidence"):
        replace(candidate, evidence={**candidate.evidence, "extra_pin": ("J2.4",)})
