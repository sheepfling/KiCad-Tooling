"""Source-bound lint for generic pin-function metadata across exact-part peers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.connector_footprint_peer_pin_function_metadata import (
    connector_footprint_peer_pin_function_metadata_gaps,
)
from kicad_tooling.hwrepo.connector_identity import has_meaningful_pin_function
from kicad_tooling.hwrepo.models import DesignLintIgnore, DesignLintPolicy, DesignLintRuleOverride
from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.connector_footprint_peer_pin_function_metadata_support import (
    metadata_peer_netlist as _source,
)
from tests.connector_footprint_peer_support import lint_report

RULE_ID = "connector.footprint_peer_pin_function_metadata_incomplete"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _findings(
    observed: NetlistContract,
    policy: DesignLintPolicy | None = None,
) -> tuple:
    return tuple(item for item in lint_report(observed, policy).findings if item.rule_id == RULE_ID)


@pytest.mark.parametrize("function", (None, "", "  ", "~", "Pin_2"))
def test_missing_or_generic_function_names_are_not_meaningful(function: str | None) -> None:
    assert not has_meaningful_pin_function(function)


def test_named_function_is_meaningful() -> None:
    assert has_meaningful_pin_function("UART_TX")


def test_generic_function_peer_is_localized_with_exact_assignment_and_anchor() -> None:
    observed = _source()

    (finding,) = _findings(observed)

    assert finding.mode == "review"
    assert finding.subject == "Synthetic two-contact connector [Synthetic:Connector_2x1] pin 2"
    assert finding.evidence["peer_identity_basis"] == ("part_id",)
    assert finding.evidence["generic_function_peers"] == ("J1",)
    assert finding.evidence["named_function"] == ("UART_TX",)
    assert finding.evidence["peer_pin_functions"] == ("J1.2=Pin_2", "J2.2=UART_TX")
    assert finding.evidence["peer_pin_electrical_types"] == (
        "J1.2=passive",
        "J2.2=passive",
    )
    assert finding.evidence["assignments"] == ("J1.2=DATA", "J2.2=DATA")
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "do not establish which function is correct" in finding.message
    assert "pin must be connected" in finding.message


def test_generic_function_peer_is_detected_on_either_connector() -> None:
    (finding,) = _findings(_source(generic_peer="J2"))

    assert finding.evidence["generic_function_peers"] == ("J2",)
    assert finding.evidence["peer_pin_functions"] == ("J1.2=UART_TX", "J2.2=Pin_2")


@pytest.mark.parametrize("missing_peer", ("J1", "J2"))
def test_missing_peer_function_is_reviewed_on_a_common_assignment(missing_peer: str) -> None:
    observed = _source(
        generic_peer="none",
        missing_function_pins=(f"{missing_peer}.2",),
    )

    (finding,) = _findings(observed)

    assert finding.mode == "review"
    assert finding.evidence["missing_function_peers"] == (missing_peer,)
    assert finding.evidence["generic_function_peers"] == ()
    assert finding.evidence["named_function"] == ("UART_TX",)
    assert finding.evidence["peer_pin_functions"] == (
        "J1.2=<missing>" if missing_peer == "J1" else "J1.2=UART_TX",
        "J2.2=<missing>" if missing_peer == "J2" else "J2.2=UART_TX",
    )
    assert finding.evidence["assignments"] == ("J1.2=DATA", "J2.2=DATA")
    assert finding.evidence["common_anchor_pin_numbers"] == ("1",)
    assert "omits its native function name" in finding.message
    assert "must be connected" in finding.message


@pytest.mark.parametrize(
    "observed",
    (
        pytest.param(_source(generic_peer="none"), id="matching-named-functions"),
        pytest.param(
            _source(named_functions=("Pin_2", "Pin_2")),
            id="matching-generic-functions",
        ),
        pytest.param(
            _source(anchor_functions=("Pin_1", "Pin_1")),
            id="no-meaningful-anchor",
        ),
        pytest.param(
            _source(anchor_functions=("GND", "RETURN")),
            id="multiple-function-mismatches",
        ),
        pytest.param(_source(part_ids=(None, None)), id="missing-part-id"),
        pytest.param(_source(part_ids=("SYNTHETIC-PART", "OTHER-PART")), id="different-part-id"),
        pytest.param(_source(dnp=("J2",)), id="dnp-peer"),
        pytest.param(_source(incomplete_inventory=True), id="incomplete-inventory"),
        pytest.param(_source(missing_metadata_pin="J2.2"), id="missing-pin-metadata"),
        pytest.param(
            _source(missing_function_pins=("J1.2", "J2.2")),
            id="both-peer-functions-missing",
        ),
        pytest.param(
            _source(
                generic_peer="J2",
                missing_function_pins=("J1.2",),
            ),
            id="missing-versus-generic-function",
        ),
        pytest.param(
            _source(missing_function_pins=("J1.1", "J2.1", "J1.2")),
            id="missing-target-and-no-meaningful-anchor",
        ),
        pytest.param(
            _source(missing_function_pins=("J1.1", "J1.2")),
            id="multiple-missing-function-differences",
        ),
        pytest.param(_source(target_types=("passive", "input")), id="type-disagreement"),
        pytest.param(_source(same_symbol=True), id="same-native-symbol"),
        pytest.param(
            _source(assignments=(("RETURN", "RETURN"), ("DATA_A", "DATA_B"))),
            id="split-target-assignment",
        ),
        pytest.param(
            _source(assignments=(("RETURN_A", "RETURN_B"), ("DATA", "DATA"))),
            id="no-common-anchor-assignment",
        ),
    ),
)
def test_incomplete_or_ambiguous_peer_evidence_stays_quiet(observed: NetlistContract) -> None:
    assert connector_footprint_peer_pin_function_metadata_gaps(observed) == ()


@pytest.mark.parametrize(
    "observed",
    (
        pytest.param(_source(), id="generic-function"),
        pytest.param(
            _source(generic_peer="none", missing_function_pins=("J1.2",)),
            id="missing-function",
        ),
    ),
)
def test_report_is_order_stable_and_common_function_clears_review(
    observed: NetlistContract,
) -> None:
    reordered = observed.model_copy(
        update={
            "nets": dict(reversed(tuple(observed.nets.items()))),
            "components": dict(reversed(tuple(observed.components.items()))),
            "component_symbols": dict(reversed(tuple(observed.component_symbols.items()))),
            "pin_functions": dict(reversed(tuple(observed.pin_functions.items()))),
            "pin_electrical_types": dict(reversed(tuple(observed.pin_electrical_types.items()))),
        }
    )

    (original,) = _findings(observed)
    (reversed_finding,) = _findings(reordered)
    assert (original.fingerprint, original.evidence) == (
        reversed_finding.fingerprint,
        reversed_finding.evidence,
    )

    common = _source(generic_peer="none")
    assert _findings(common) == ()


@pytest.mark.parametrize(
    "observed",
    (
        pytest.param(_source(), id="generic-function"),
        pytest.param(
            _source(generic_peer="none", missing_function_pins=("J1.2",)),
            id="missing-function",
        ),
    ),
)
def test_project_can_block_disable_or_exactly_ignore_the_finding(
    observed: NetlistContract,
) -> None:
    default = _findings(observed)[0]
    blocked = _findings(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic project promotes this connector metadata review.",
                ),
            )
        ),
    )
    disabled = _findings(
        observed,
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic project does not compare these alternate symbols.",
                ),
            )
        ),
    )
    ignored = _findings(
        observed,
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=default.fingerprint,
                    reason="Synthetic peer metadata was reviewed.",
                ),
            )
        ),
    )

    assert blocked[0].mode == "block"
    assert disabled[0].disposition == "RULE_OFF"
    assert ignored[0].disposition == "IGNORED"


def test_candidate_cannot_be_rebound_to_changed_source_rows() -> None:
    observed = _source()
    candidate = connector_footprint_peer_pin_function_metadata_gaps(observed)[0]
    evidence = candidate.source_evidence
    with pytest.raises(ValueError, match="match current native pin rows"):
        replace(evidence, observations=tuple(reversed(evidence.observations)))
