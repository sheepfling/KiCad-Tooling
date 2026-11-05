"""Verify diode and polarized-capacitor findings retain their native source."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.component_diode_rail_orientation import (
    diodes_with_anode_below_cathode_on_named_rails,
)
from kicad_tooling.hwrepo.component_polarized_capacitor_orientation import (
    polarized_capacitors_on_reversed_named_rails,
)
from kicad_tooling.hwrepo.design_lint_component_polarity_candidate_evidence import (
    ComponentPolarityCandidate,
    DiodeRailOrientationEvidence,
    PolarizedCapacitorRailOrientationEvidence,
)
from tests.design_lint_fixtures.diode_rail_orientation import netlist as diode_netlist
from tests.design_lint_fixtures.polarized_capacitor import netlist as capacitor_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.evidence_lint]


def test_diode_candidate_retains_current_native_anode_cathode_and_rail_evidence() -> None:
    observed = diode_netlist()
    candidate = diodes_with_anode_below_cathode_on_named_rails(observed)[0]

    assert isinstance(candidate, ComponentPolarityCandidate)
    assert isinstance(candidate.source_evidence, DiodeRailOrientationEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["anode_pin"] == ("D1.2",)
    assert candidate.evidence["anode_net"] == ("+3V3",)
    assert candidate.evidence["cathode_pin"] == ("D1.1",)
    assert candidate.evidence["cathode_net"] == ("+5V",)

    repaired = diode_netlist(anode_net="+5V", cathode_net="+3V3")
    with pytest.raises(ValueError, match="current native assignment"):
        replace(candidate.source_evidence, observed=repaired)


def test_polarized_capacitor_candidate_retains_current_terminal_and_rail_evidence() -> None:
    observed = capacitor_netlist()
    candidate = polarized_capacitors_on_reversed_named_rails(observed)[0]

    assert isinstance(candidate, ComponentPolarityCandidate)
    assert isinstance(candidate.source_evidence, PolarizedCapacitorRailOrientationEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["positive_terminal_pin"] == ("C1.1",)
    assert candidate.evidence["positive_terminal_net"] == ("-5V",)
    assert candidate.evidence["negative_terminal_pin"] == ("C1.2",)
    assert candidate.evidence["negative_terminal_net"] == ("+5V",)

    repaired = capacitor_netlist(positive_terminal_net="+5V", negative_terminal_net="-5V")
    with pytest.raises(ValueError, match="current native assignment"):
        replace(candidate.source_evidence, observed=repaired)


def test_polarity_candidate_rejects_report_evidence_that_does_not_match_source() -> None:
    candidate = diodes_with_anode_below_cathode_on_named_rails(diode_netlist())[0]

    with pytest.raises(ValueError, match="typed projection"):
        ComponentPolarityCandidate(
            rule_id=candidate.rule_id,
            subject=candidate.subject,
            message=candidate.message,
            evidence={"anode_net": ("OTHER",)},
            source_evidence=candidate.source_evidence,
        )
