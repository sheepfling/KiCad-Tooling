"""Source-bound candidate records for mapped connector-pin reviews."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.connector_coverage import source_matched_connector_pin_evidence
from kicad_tooling.hwrepo.connector_mapped_interface_pins import (
    unassigned_mapped_interface_signal_pins,
)
from kicad_tooling.hwrepo.design_lint_connector_mapped_interface_candidate_evidence import (
    MappedInterfacePinCandidate,
    MappedInterfacePinFindingEvidence,
)
from tests.connector_mapped_interface_support import CATALOG_SHA256, interface_coverage
from tests.design_lint_fixtures.connector_mapped_interface_signal import (
    mapped_interface_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
    pytest.mark.evidence_lint,
]


def test_unassigned_signal_candidate_retains_exact_matched_sources() -> None:
    observed = mapped_interface_netlist()
    coverage = interface_coverage(observed)

    candidate = unassigned_mapped_interface_signal_pins(observed, coverage)[0]
    mapped_pin = source_matched_connector_pin_evidence(observed, coverage)["J1.2"]

    assert isinstance(candidate, MappedInterfacePinCandidate)
    assert candidate.source_evidence.observed is observed
    assert candidate.source_evidence.coverage is coverage
    assert candidate.source_evidence.mapped_pin == mapped_pin
    assert candidate.evidence == {
        "component_pin": ("J1.2",),
        "interface_pin_number": ("2",),
        "interface_signal": ("UART_RX",),
        "interface_role": ("signal",),
        "native_pin_function": ("Pin_2",),
        "native_pin_electrical_type": ("input",),
        "assigned_nets": (),
        "interface_catalog_sha256": (CATALOG_SHA256,),
    }


def test_stale_netlist_cannot_be_attached_to_a_current_mapped_pin_record() -> None:
    observed = mapped_interface_netlist()
    coverage = interface_coverage(observed)
    mapped_pin = source_matched_connector_pin_evidence(observed, coverage)["J1.2"]
    stale = observed.model_copy(
        update={"pin_functions": {**observed.pin_functions, "J1.2": "Changed_Function"}}
    )

    with pytest.raises(ValueError, match="current source evidence"):
        MappedInterfacePinFindingEvidence(
            observed=stale,
            coverage=coverage,
            mapped_pin=mapped_pin,
            rule_id="connector.mapped_interface_signal_unassigned",
        )


def test_rail_clue_must_match_the_single_source_net_and_rule() -> None:
    observed = mapped_interface_netlist(target_net="VCC")
    coverage = interface_coverage(observed)
    mapped_pin = source_matched_connector_pin_evidence(observed, coverage)["J1.2"]

    with pytest.raises(ValueError, match="net-label clue"):
        MappedInterfacePinFindingEvidence(
            observed=observed,
            coverage=coverage,
            mapped_pin=mapped_pin,
            rule_id="connector.mapped_interface_signal_on_named_rail",
            net_label_role_clue="return-like",
        )
