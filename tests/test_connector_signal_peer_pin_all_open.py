"""Opt-in review for generic signal contacts left open on every connector peer."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_peer_pin_all_open import (
    all_open_generic_connector_peer_pin_candidates,
)
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.models import DesignLintPolicy
from tests.design_lint_fixtures import coach
from tests.design_lint_fixtures.connector_peer_pin_all_open import (
    generic_open_part_id_peer_netlist,
    generic_open_peer_netlist,
    review_generic_peer_pin_policy,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
]

RULE_ID = "connector.generic_peer_pin_all_open"
SIGNAL_PIN_TYPES = (
    "input",
    "output",
    "bidirectional",
    "tri_state",
    "open_collector",
    "open_emitter",
)


@pytest.mark.parametrize("pin_type", SIGNAL_PIN_TYPES)
def test_all_open_generic_signal_peer_pin_is_opt_in_review(pin_type: str) -> None:
    source = generic_open_peer_netlist(target_pin_type=pin_type)

    default_report = evaluate(
        "synthetic-all-open-signal-peer-pin", coach(source), DesignLintPolicy()
    )
    default_finding = next(item for item in default_report.findings if item.rule_id == RULE_ID)
    assert default_report.status == "PASS"
    assert default_finding.mode == "off"

    report = evaluate(
        "synthetic-all-open-signal-peer-pin",
        coach(source),
        review_generic_peer_pin_policy(),
    )
    findings = tuple(item for item in report.findings if item.rule_id == RULE_ID)
    assert report.status == "REVIEW"
    assert len(findings) == 1
    assert findings[0].subject == (
        f"Lint:GenericSignalPort pin 2: generic {pin_type} signal contact is open on every peer"
    )
    assert findings[0].evidence["pin_electrical_type"] == (pin_type,)
    assert findings[0].evidence["shared_anchor_contacts"] == ("J1.1 / J2.1 / J3.1 -> +5V",)


def test_cross_symbol_signal_peers_require_matching_part_identity_and_pin_type() -> None:
    source = generic_open_part_id_peer_netlist(
        references=("J1", "J2"),
        target_pin_type="input",
    )

    candidates = all_open_generic_connector_peer_pin_candidates(source)
    assert len(candidates) == 1
    assert candidates[0].evidence["peer_identity_basis"] == ("part_id",)
    assert candidates[0].evidence["pin_electrical_type"] == ("input",)
    assert candidates[0].evidence["peer_symbols"] == (
        "Lint:GenericSignalPortLeft",
        "Lint:GenericSignalPortRight",
    )

    mismatched = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "J2.2": "output",
            }
        }
    )
    assert all_open_generic_connector_peer_pin_candidates(mismatched) == ()


def test_signal_peer_can_use_absent_native_pin_function_metadata() -> None:
    source = generic_open_peer_netlist(target_pin_type="input")
    source = source.model_copy(
        update={
            "pin_functions": {
                pin: function
                for pin, function in source.pin_functions.items()
                if not pin.endswith(".2")
            }
        }
    )

    candidates = all_open_generic_connector_peer_pin_candidates(source)

    assert len(candidates) == 1
    assert candidates[0].evidence["pin_electrical_type"] == ("input",)


@pytest.mark.parametrize("pin_type", SIGNAL_PIN_TYPES)
def test_common_signal_assignment_clears_the_all_open_prompt(pin_type: str) -> None:
    source = generic_open_peer_netlist(
        open_pin_assignments=False,
        target_pin_type=pin_type,
    )

    assert all_open_generic_connector_peer_pin_candidates(source) == ()


@pytest.mark.parametrize("pin_type", SIGNAL_PIN_TYPES)
def test_signal_peers_without_a_shared_anchor_are_quiet(pin_type: str) -> None:
    source = generic_open_peer_netlist(
        anchor_nets=("PORT_A", "PORT_B", "PORT_C"),
        target_pin_type=pin_type,
    )

    assert all_open_generic_connector_peer_pin_candidates(source) == ()


def test_named_signal_function_and_power_types_stay_with_specific_rules() -> None:
    generic_input = generic_open_peer_netlist(target_pin_type="input")
    named_input = generic_input.model_copy(
        update={
            "pin_functions": {
                **generic_input.pin_functions,
                "J1.2": "AUXILIARY",
                "J2.2": "AUXILIARY",
                "J3.2": "AUXILIARY",
            }
        }
    )
    assert all_open_generic_connector_peer_pin_candidates(named_input) == ()

    for pin_type in ("power_in", "power_out", "free", "unspecified"):
        source = generic_open_peer_netlist(target_pin_type=pin_type)
        assert all_open_generic_connector_peer_pin_candidates(source) == ()
        part_id_source = generic_open_part_id_peer_netlist(
            references=("J1", "J2"),
            target_pin_type=pin_type,
        )
        assert all_open_generic_connector_peer_pin_candidates(part_id_source) == ()


def test_exact_symbol_signal_peers_require_a_matching_pin_type() -> None:
    source = generic_open_peer_netlist(target_pin_type="input")
    mismatched = source.model_copy(
        update={
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "J2.2": "output",
            }
        }
    )

    assert all_open_generic_connector_peer_pin_candidates(mismatched) == ()


@pytest.mark.parametrize("pin_type", SIGNAL_PIN_TYPES)
def test_signal_candidate_fingerprint_is_stable_under_input_reordering(pin_type: str) -> None:
    source = generic_open_peer_netlist(target_pin_type=pin_type)
    reordered = source.model_copy(
        update={
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
