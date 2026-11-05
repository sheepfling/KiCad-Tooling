"""Source-binding regressions for complementary line pins on named rails."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.can_line_named_rail import can_line_on_named_rail_candidates
from kicad_tooling.hwrepo.design_lint_named_rail_line_candidate_evidence import (
    CanLineNamedRailEvidence,
    NamedRailLineCandidate,
    Rs485LineNamedRailEvidence,
)
from kicad_tooling.hwrepo.named_rail_pin_evidence import NamedRailPinSource
from kicad_tooling.hwrepo.rs485_line_named_rail import rs485_line_on_named_rail_candidates
from tests.design_lint_fixtures.can_line_named_rail import can_line_named_rail_netlist
from tests.design_lint_fixtures.rs485_line_named_rail import rs485_line_named_rail_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.evidence_lint]


def test_can_line_candidate_retains_and_rechecks_its_complementary_pin() -> None:
    candidate = can_line_on_named_rail_candidates(can_line_named_rail_netlist())[0]
    assert isinstance(candidate, NamedRailLineCandidate)
    source = candidate.source_evidence
    assert isinstance(source, CanLineNamedRailEvidence)
    assert isinstance(source.pin, NamedRailPinSource)
    assert source.peer.pin == "U1.2"
    assert candidate.evidence["complementary_line_function"] == ("CANL",)

    pin_functions = dict(source.pin.observed.pin_functions)
    pin_functions["U1.2"] = "CANH"
    changed = source.pin.observed.model_copy(update={"pin_functions": pin_functions})
    changed_pin = NamedRailPinSource(observed=changed, evidence=source.pin.evidence)
    with pytest.raises(ValueError, match="current native pair"):
        replace(source, pin=changed_pin)


def test_rs485_line_candidate_retains_and_rechecks_pair_and_identity() -> None:
    candidate = rs485_line_on_named_rail_candidates(rs485_line_named_rail_netlist())[0]
    assert isinstance(candidate, NamedRailLineCandidate)
    source = candidate.source_evidence
    assert isinstance(source, Rs485LineNamedRailEvidence)
    assert isinstance(source.pin, NamedRailPinSource)
    assert source.peer.pin == "U1.2"
    assert candidate.evidence["identity_basis"] == (
        "Synthetic:Rs485Transceiver RS-485 transceiver",
    )

    pin_functions = dict(source.pin.observed.pin_functions)
    pin_functions["U1.2"] = "A"
    changed = source.pin.observed.model_copy(update={"pin_functions": pin_functions})
    changed_pin = NamedRailPinSource(observed=changed, evidence=source.pin.evidence)
    with pytest.raises(ValueError, match="current native pair"):
        replace(source, pin=changed_pin)
