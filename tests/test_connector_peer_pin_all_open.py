"""Opt-in review for all-open generic passive connector peer pins."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_peer_pin_all_open import (
    all_open_generic_connector_peer_pin_candidates,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)
from tests.design_lint_fixtures import coach

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint]

_RULE_ID = "connector.generic_peer_pin_all_open"
_REFERENCES = ("J1", "J2", "J3")


def generic_open_peer_netlist(
    *,
    references: tuple[str, ...] = _REFERENCES,
    open_pin_assignments: bool = True,
    anchor_nets: tuple[str, ...] | None = None,
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    anchor_nets = anchor_nets or ("+5V",) * len(references)
    nets: dict[str, tuple[str, ...]] = {}
    for reference, net in zip(references, anchor_nets, strict=True):
        nets[net] = (*nets.get(net, ()), f"{reference}.1")
    if not open_pin_assignments:
        nets["GND"] = tuple(f"{reference}.2" for reference in references)
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic passive peer port", footprint="")
            for reference in references
        },
        nets=nets,
        dnp_components=dnp_references,
        component_symbols={reference: "Lint:PassiveGenericPort" for reference in references},
        component_pin_numbers={reference: ("1", "2") for reference in references},
        pin_functions={
            f"{reference}.{number}": f"Pin_{number}"
            for reference in references
            for number in ("1", "2")
        },
        pin_electrical_types={
            f"{reference}.{number}": "passive" for reference in references for number in ("1", "2")
        },
    )


def generic_open_part_id_peer_netlist(
    *,
    references: tuple[str, ...] = ("J1", "J2", "J3", "J4"),
    symbols: dict[str, str] | None = None,
) -> NetlistContract:
    left_symbol_count = max(1, (len(references) + 1) // 2)
    symbols = symbols or {
        reference: "Lint:PassiveGenericPortLeft"
        if index < left_symbol_count
        else "Lint:PassiveGenericPortRight"
        for index, reference in enumerate(references)
    }
    source = generic_open_peer_netlist(references=references)
    return source.model_copy(
        update={
            "components": {
                reference: ComponentContract(
                    value="Synthetic passive peer port",
                    footprint="Synthetic:PassiveGenericPort",
                    part_id="SYNTHETIC-PASSIVE-PORT-001",
                )
                for reference in references
            },
            "component_symbols": symbols,
        }
    )


def review_policy() -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=_RULE_ID,
                mode="review",
                reason="Synthetic project asks reviewers to disposition all-open generic peer contacts",
            ),
        )
    )


def test_all_open_generic_passive_peer_pin_is_opt_in_review() -> None:
    source = generic_open_peer_netlist()
    default_report = evaluate("synthetic-all-open-peer-pin", coach(source), DesignLintPolicy())
    default_finding = next(item for item in default_report.findings if item.rule_id == _RULE_ID)
    assert default_report.status == "PASS"
    assert default_finding.mode == "off"
    assert default_finding.disposition == "RULE_OFF"
    assert default_report.connector_peer_pin_coverage is not None
    assert default_report.connector_peer_pin_coverage.generic_peer_pin_all_open_finding_count == 1

    report = evaluate("synthetic-all-open-peer-pin", coach(source), review_policy())
    findings = tuple(item for item in report.findings if item.rule_id == _RULE_ID)
    assert report.status == "REVIEW"
    assert len(findings) == 1
    finding = findings[0]
    assert (
        finding.subject
        == "Lint:PassiveGenericPort pin 2: generic passive contact is open on every peer"
    )
    assert finding.evidence["J1.2"] == ()
    assert finding.evidence["J2.2"] == ()
    assert finding.evidence["J3.2"] == ()
    assert finding.evidence["shared_anchor_contacts"] == ("J1.1 / J2.1 / J3.1 -> +5V",)
    assert "does not identify this contact as signal, return, or power" in finding.message
    assert report.connector_peer_pin_coverage is not None
    assert report.connector_peer_pin_coverage.generic_peer_pin_all_open_finding_count == 1


def test_common_assignment_clears_the_all_open_prompt() -> None:
    report = evaluate(
        "synthetic-all-open-peer-pin-control",
        coach(generic_open_peer_netlist(open_pin_assignments=False)),
        review_policy(),
    )

    assert report.status == "PASS"
    assert _RULE_ID not in {item.rule_id for item in report.findings}


def test_unassigned_peers_without_a_shared_anchor_are_quiet() -> None:
    source = generic_open_peer_netlist(anchor_nets=("PORT_A", "PORT_B", "PORT_C"))

    assert all_open_generic_connector_peer_pin_candidates(source) == ()


def test_exact_symbol_peer_can_use_absent_native_pin_function_metadata() -> None:
    netlist = generic_open_peer_netlist()
    source = netlist.model_copy(
        update={
            "pin_functions": {
                pin: function
                for pin, function in netlist.pin_functions.items()
                if not pin.endswith(".2")
            }
        }
    )

    candidates = all_open_generic_connector_peer_pin_candidates(source)
    assert len(candidates) == 1
    assert candidates[0].evidence["pin_number"] == ("2",)


def test_guarded_part_id_aliases_prompt_once_for_an_all_open_generic_pin() -> None:
    source = generic_open_part_id_peer_netlist()

    candidates = all_open_generic_connector_peer_pin_candidates(source)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.subject == (
        "PART_ID SYNTHETIC-PASSIVE-PORT-001 pin 2: generic passive contact is open on every peer"
    )
    assert candidate.evidence["peer_identity_basis"] == ("part_id",)
    assert candidate.evidence["peer_identity"] == ("SYNTHETIC-PASSIVE-PORT-001",)
    assert candidate.evidence["peer_symbols"] == (
        "Lint:PassiveGenericPortLeft",
        "Lint:PassiveGenericPortRight",
    )
    assert candidate.evidence["J1.2"] == ()
    assert candidate.evidence["J2.2"] == ()
    assert candidate.evidence["J3.2"] == ()
    assert candidate.evidence["J4.2"] == ()
    assert candidate.evidence["shared_anchor_contacts"] == ("J1.1 / J2.1 / J3.1 / J4.1 -> +5V",)

    default_report = evaluate("synthetic-part-id-all-open", coach(source), DesignLintPolicy())
    review_report = evaluate("synthetic-part-id-all-open", coach(source), review_policy())
    assert default_report.status == "PASS"
    assert default_report.connector_peer_pin_coverage is not None
    assert default_report.connector_peer_pin_coverage.generic_peer_pin_all_open_finding_count == 1
    assert review_report.status == "REVIEW"
    assert tuple(item.rule_id for item in review_report.findings) == (_RULE_ID,)


def test_part_id_all_open_prompt_requires_matching_identity_and_peer_scope() -> None:
    references = ("J1", "J2")
    source = generic_open_part_id_peer_netlist(references=references)
    assert len(all_open_generic_connector_peer_pin_candidates(source)) == 1

    missing_identity = source.model_copy(
        update={
            "components": {
                reference: component.model_copy(update={"part_id": None})
                for reference, component in source.components.items()
            }
        }
    )
    assert all_open_generic_connector_peer_pin_candidates(missing_identity) == ()

    mismatched_value_components = dict(source.components)
    mismatched_value_components["J2"] = mismatched_value_components["J2"].model_copy(
        update={"value": "Different synthetic port"}
    )
    mismatched_value = source.model_copy(update={"components": mismatched_value_components})
    assert all_open_generic_connector_peer_pin_candidates(mismatched_value) == ()

    mismatched_function = source.model_copy(
        update={
            "pin_functions": {
                **source.pin_functions,
                "J2.2": "RETURN",
            }
        }
    )
    assert all_open_generic_connector_peer_pin_candidates(mismatched_function) == ()

    missing_function = source.model_copy(
        update={
            "pin_functions": {
                pin: function for pin, function in source.pin_functions.items() if pin != "J2.2"
            }
        }
    )
    assert all_open_generic_connector_peer_pin_candidates(missing_function) == ()

    mismatched_electrical_type = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "J2.2": "input",
            }
        }
    )
    assert all_open_generic_connector_peer_pin_candidates(mismatched_electrical_type) == ()

    different_anchor_nets = generic_open_part_id_peer_netlist(
        references=references,
    ).model_copy(update={"nets": {"PORT_A": ("J1.1",), "PORT_B": ("J2.1",)}})
    assert all_open_generic_connector_peer_pin_candidates(different_anchor_nets) == ()

    assert (
        all_open_generic_connector_peer_pin_candidates(
            source,
            peer_assignment_groups={
                "J1": ("interface-a", "Reviewed synthetic interface A"),
                "J2": ("interface-b", "Reviewed synthetic interface B"),
            },
        )
        == ()
    )


def test_distinct_reviewed_peer_groups_are_not_compared() -> None:
    source = generic_open_peer_netlist()
    groups = {
        "J1": ("port-a", "Reviewed synthetic interface A"),
        "J2": ("port-b", "Reviewed synthetic interface B"),
        "J3": ("port-c", "Reviewed synthetic interface C"),
    }

    assert (
        all_open_generic_connector_peer_pin_candidates(
            source,
            peer_assignment_groups=groups,
        )
        == ()
    )


@pytest.mark.parametrize(
    ("update", "expected_count"),
    (
        pytest.param({"dnp_components": ("J2", "J3")}, 0, id="dnp-peer-excluded"),
        pytest.param(
            {
                "pin_electrical_types": {
                    f"{reference}.{number}": "passive"
                    for reference in _REFERENCES
                    for number in ("1", "2")
                }
                | {"J1.2": "power_in"}
            },
            0,
            id="non-passive-role-excluded",
        ),
        pytest.param(
            {
                "pin_functions": {
                    **{f"{reference}.1": "Pin_1" for reference in _REFERENCES},
                    **{f"{reference}.2": "GND" for reference in _REFERENCES},
                }
            },
            0,
            id="named-role-excluded",
        ),
    ),
)
def test_specific_roles_and_population_controls_stay_out_of_generic_rule(
    update: dict[str, object], expected_count: int
) -> None:
    source = generic_open_peer_netlist().model_copy(update=update)

    assert len(all_open_generic_connector_peer_pin_candidates(source)) == expected_count


def test_candidate_fingerprint_is_stable_under_input_reordering() -> None:
    source = generic_open_peer_netlist()
    reordered = source.model_copy(
        update={
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )
    original_candidate = all_open_generic_connector_peer_pin_candidates(source)[0]
    reordered_candidate = all_open_generic_connector_peer_pin_candidates(reordered)[0]

    assert reordered_candidate == original_candidate
    assert fingerprint(reordered_candidate) == fingerprint(original_candidate)


def test_part_id_candidate_fingerprint_is_stable_under_input_reordering() -> None:
    source = generic_open_part_id_peer_netlist()
    reordered = source.model_copy(
        update={
            "components": dict(reversed(tuple(source.components.items()))),
            "nets": dict(reversed(tuple(source.nets.items()))),
            "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            "component_pin_numbers": dict(reversed(tuple(source.component_pin_numbers.items()))),
            "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
        }
    )

    original = all_open_generic_connector_peer_pin_candidates(source)[0]
    reordered_candidate = all_open_generic_connector_peer_pin_candidates(reordered)[0]
    assert reordered_candidate == original
    assert fingerprint(reordered_candidate) == fingerprint(original)


def test_rule_supports_block_off_and_exact_ignore_policy() -> None:
    source = generic_open_peer_netlist()
    report = evaluate("synthetic-all-open-peer-pin", coach(source), review_policy())
    finding = next(item for item in report.findings if item.rule_id == _RULE_ID)

    blocked = evaluate(
        "synthetic-all-open-peer-pin",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=_RULE_ID,
                    mode="block",
                    reason="Synthetic interface requires disposition",
                ),
            )
        ),
    )
    assert blocked.status == "FAIL"
    assert next(item for item in blocked.findings if item.rule_id == _RULE_ID).mode == "block"

    disabled = evaluate(
        "synthetic-all-open-peer-pin",
        coach(source),
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=_RULE_ID,
                    mode="off",
                    reason="Synthetic project reviewed the unused pin",
                ),
            )
        ),
    )
    assert disabled.status == "PASS"
    assert next(item for item in disabled.findings if item.rule_id == _RULE_ID).disposition == (
        "RULE_OFF"
    )

    ignored = evaluate(
        "synthetic-all-open-peer-pin",
        coach(source),
        DesignLintPolicy(
            rules=review_policy().rules,
            ignores=(
                DesignLintIgnore(
                    rule_id=_RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic review confirms this pin is intentionally unused",
                ),
            ),
        ),
    )
    assert ignored.status == "PASS"
    assert next(item for item in ignored.findings if item.rule_id == _RULE_ID).disposition == (
        "IGNORED"
    )
