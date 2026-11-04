"""Control candidate projections retain their typed scan sources."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.control_input_inventory import (
    ControlInputBiasGap,
    UnconnectedControlInput,
)
from kicad_tooling.hwrepo.design_lint import fingerprint
from kicad_tooling.hwrepo.design_lint_control_candidate_evidence import ControlCandidate
from kicad_tooling.hwrepo.design_lint_control_candidates import scan_control_candidates
from kicad_tooling.hwrepo.design_lint_control_inputs import ControlCandidateInputs
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.open_drain_heuristics import OpenOutputBiasGap
from tests.design_lint_fixtures import control_input_pins

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.power_lint]


def _scan(observed: NetlistContract) -> tuple[ControlCandidate, ...]:
    result = scan_control_candidates(ControlCandidateInputs.from_legacy_arguments(observed, None))
    return tuple(item for item in result.candidates if isinstance(item, ControlCandidate))


def _assert_fingerprint_matches_public_candidate(candidate: ControlCandidate) -> None:
    public_candidate = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(public_candidate)


def test_unconnected_control_candidate_retains_inventory_record() -> None:
    candidate = next(
        item
        for item in _scan(control_input_pins())
        if item.rule_id == "control.unconnected_control_input" and item.subject.startswith("U1.1:")
    )

    assert candidate.source_evidence == UnconnectedControlInput(
        pin="U1.1",
        function="~{RESET}",
        family="reset",
        electrical_type="input",
    )
    assert candidate.evidence == {
        "U1.1": (),
        "function": ("~{RESET}",),
        "family": ("reset",),
        "electrical_type": ("input",),
    }
    _assert_fingerprint_matches_public_candidate(candidate)


def test_connected_control_candidate_retains_bias_gap_record() -> None:
    candidate = next(
        item
        for item in _scan(control_input_pins(connected=True, visible_bias=False))
        if item.rule_id == "control.connected_control_input_without_visible_bias"
        and item.evidence["net"] == ("RESET_LINE",)
    )

    assert isinstance(candidate.source_evidence, ControlInputBiasGap)
    assert candidate.source_evidence.net == "RESET_LINE"
    assert candidate.evidence == {
        "net": ("RESET_LINE",),
        "control_inputs": (
            "U1.1: ~{RESET} (reset, input)",
            "U1.10: IOEXP_RST_N (reset, input)",
            "U1.13: PERST (reset, input)",
            "U1.8: RST# (reset, input)",
        ),
        "output_capable_peers": (),
    }
    _assert_fingerprint_matches_public_candidate(candidate)


def test_open_output_candidate_retains_heuristic_gap_record() -> None:
    observed = NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic open output", footprint=""),
            "U2": ComponentContract(value="Synthetic input", footprint=""),
        },
        nets={"ALERT_N": ("U1.1", "U2.1"), "+3V3": (), "GND": ()},
        pin_functions={"U1.1": "ALERT_N", "U2.1": "ALERT_N"},
        pin_electrical_types={"U1.1": "open_collector", "U2.1": "input"},
    )
    candidate = next(
        item
        for item in _scan(observed)
        if item.rule_id == "signal.open_collector_input_without_visible_bias"
    )

    assert candidate.source_evidence == OpenOutputBiasGap(
        net="ALERT_N",
        bias="pull_up",
        output_pins=("U1.1",),
        input_pins=("U2.1",),
        visible_resistors=(),
    )
    assert candidate.evidence == {
        "net": ("ALERT_N",),
        "expected_bias": ("pull-up to a recognized positive rail",),
        "open_output_pins": ("U1.1",),
        "input_pins": ("U2.1",),
        "visible_resistors_on_signal_net": (),
    }
    _assert_fingerprint_matches_public_candidate(candidate)


def test_control_candidate_rejects_a_drifted_report_projection() -> None:
    source = OpenOutputBiasGap(
        net="ALERT_N",
        bias="pull_up",
        output_pins=("U1.1",),
        input_pins=("U2.1",),
        visible_resistors=(),
    )
    with pytest.raises(ValueError, match="typed source projection"):
        ControlCandidate(
            rule_id="signal.open_collector_input_without_visible_bias",
            subject="ALERT_N",
            message="review",
            evidence={"net": ("OTHER",)},
            source_evidence=source,
        )
