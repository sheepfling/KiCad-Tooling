"""Source-bound review of native pin-function disagreements across exact-part peers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_pin_function_consistency import (
    connector_footprint_peer_pin_function_disagreements,
)
from kicad_tooling.hwrepo.connector_footprint_peer_pin_type_consistency import (
    connector_footprint_peer_pin_electrical_type_disagreements,
)
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from tests.connector_footprint_peer_support import lint_report, peer_netlist

RULE_ID = "connector.footprint_peer_pin_function_disagreement"
pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.interface_lint]


def _source(
    *,
    anchor_functions: tuple[str, str] = ("GND", "GND"),
    functions: tuple[str, str] = ("UART_RX", "UART_TX"),
    target_types: tuple[str, str] = ("passive", "passive"),
    anchor_types: tuple[str, str] = ("passive", "passive"),
    assignments: tuple[tuple[str | None, str | None], ...] = (
        ("RETURN", "RETURN"),
        ("DATA", "DATA"),
    ),
    part_ids: tuple[str | None, str | None] = ("SYNTHETIC-PART", "SYNTHETIC-PART"),
    dnp: tuple[str, ...] = (),
    incomplete_inventory: bool = False,
    missing_metadata_pin: str | None = None,
    same_symbol: bool = False,
):
    observed = peer_netlist(
        assignments=assignments,
        functions=(anchor_functions[0], functions[0]),
        electrical_types=(anchor_types[0], target_types[0]),
        part_id=part_ids[0].strip() if part_ids[0] else None,
        dnp=dnp,
        incomplete_inventory=incomplete_inventory,
        missing_metadata_pin=missing_metadata_pin,
    )
    pin_functions = {
        **observed.pin_functions,
        "J2.1": anchor_functions[1],
        "J2.2": functions[1],
    }
    electrical_types = {
        **observed.pin_electrical_types,
        "J2.1": anchor_types[1],
        "J2.2": target_types[1],
    }
    if missing_metadata_pin is not None:
        pin_functions.pop(missing_metadata_pin, None)
        electrical_types.pop(missing_metadata_pin, None)
    components = dict(observed.components)
    components["J1"] = components["J1"].model_copy(update={"part_id": part_ids[0]})
    components["J2"] = components["J2"].model_copy(update={"part_id": part_ids[1]})
    symbols = dict(observed.component_symbols)
    if same_symbol:
        symbols["J2"] = symbols["J1"]
    return observed.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "pin_functions": pin_functions,
            "pin_electrical_types": electrical_types,
        }
    )


def _findings(report):
    return tuple(item for item in report.findings if item.rule_id == RULE_ID)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_one_meaningful_function_mismatch_on_a_common_part_pin_is_localized() -> None:
    observed = _source()

    (finding,) = _findings(lint_report(observed))

    assert finding.mode == "review"
    assert finding.subject == "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2"
    assert finding.evidence["peer_identity_basis"] == ("part_id",)
    assert finding.evidence["part_id"] == ("SYNTHETIC-PART",)
    assert finding.evidence["peer_pin_functions"] == ("J1.2=UART_RX", "J2.2=UART_TX")
    assert finding.evidence["peer_pin_electrical_types"] == (
        "J1.2=passive",
        "J2.2=passive",
    )
    assert finding.evidence["assignments"] == ("J1.2=DATA", "J2.2=DATA")
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "do not establish which function is correct" in finding.message
    assert connector_footprint_peer_pin_electrical_type_disagreements(observed) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize(
    "source",
    (
        pytest.param(_source(functions=("UART_RX", "UART_RX")), id="matching-function"),
        pytest.param(_source(functions=("UART_RX", "uart_rx")), id="casefold-match"),
        pytest.param(_source(functions=("Pin_2", "UART_TX")), id="generic-function-control"),
        pytest.param(
            _source(anchor_functions=("GND", "RETURN")), id="multiple-function-mismatches"
        ),
        pytest.param(_source(part_ids=(None, None)), id="missing-part-id"),
        pytest.param(_source(part_ids=("SYNTHETIC-PART", "OTHER-PART")), id="different-part-id"),
        pytest.param(
            _source(assignments=(("RETURN_A", "RETURN_B"), ("DATA", "DATA"))),
            id="no-common-anchor",
        ),
        pytest.param(
            _source(assignments=(("RETURN", "RETURN"), ("DATA_A", "DATA_B"))),
            id="split-target-belongs-to-assignment-review",
        ),
        pytest.param(
            _source(assignments=(("RETURN", "RETURN"), ("DATA", None))),
            id="open-target",
        ),
        pytest.param(
            _source(functions=("UART_RX", "UART_TX"), target_types=("passive", "power_in")),
            id="simultaneous-type-mismatch",
        ),
        pytest.param(
            _source(functions=("UART_RX", "UART_TX"), anchor_types=("passive", "input")),
            id="anchor-type-mismatch",
        ),
        pytest.param(
            _source(functions=("UART_RX", "UART_TX"), incomplete_inventory=True),
            id="incomplete-inventory",
        ),
        pytest.param(
            _source(functions=("UART_RX", "UART_TX"), missing_metadata_pin="J2.2"),
            id="missing-metadata",
        ),
        pytest.param(_source(dnp=("J2",)), id="dnp-peer"),
        pytest.param(_source(same_symbol=True), id="same-native-symbol"),
    ),
)
def test_incomplete_or_nonmatching_peer_evidence_stays_quiet(source) -> None:
    assert connector_footprint_peer_pin_function_disagreements(source) == ()


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_part_ids_match_after_trim_and_casefold() -> None:
    observed = _source(part_ids=(" synthetic-part ", "SYNTHETIC-PART"))

    (candidate,) = connector_footprint_peer_pin_function_disagreements(observed)

    assert candidate.evidence["part_id"] == ("SYNTHETIC-PART",)


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
                    reason="Synthetic project promotes this part-symbol consistency review.",
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
                    reason="Synthetic project documents the approved symbol variation.",
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
                    reason="Synthetic project accepts this exact reviewed pin-function variant.",
                ),
            )
        ),
    )

    assert blocked.status == "FAIL"
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
    (candidate,) = connector_footprint_peer_pin_function_disagreements(_source())

    with pytest.raises(ValueError, match="must match its native source evidence"):
        replace(candidate, evidence={**candidate.evidence, "assignments": ("J1.2=OTHER",)})
