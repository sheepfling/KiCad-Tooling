"""BJT base findings keep typed evidence bound to their native netlist."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.component_bjt_base_bias import bjts_without_visible_emitter_bias
from kicad_tooling.hwrepo.component_bjt_base_drive import bjts_with_direct_output_base_drive
from kicad_tooling.hwrepo.design_lint_bjt_base_candidate_evidence import (
    BjtBaseBiasEvidence,
    BjtBaseCandidate,
    BjtBaseDirectDriveEvidence,
)
from tests.design_lint_fixtures.bjt_base_bias import bjt_base_bias_netlist
from tests.design_lint_fixtures.bjt_base_drive import bjt_base_drive_netlist

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.evidence_lint]


def test_base_bias_candidate_retains_exact_source_and_rejects_mismatched_net() -> None:
    observed = bjt_base_bias_netlist()
    candidate = bjts_without_visible_emitter_bias(observed)[0]

    assert isinstance(candidate, BjtBaseCandidate)
    assert isinstance(candidate.source_evidence, BjtBaseBiasEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["base_net"] == ("BASE",)

    with pytest.raises(ValueError, match="current native assignment"):
        replace(candidate.source_evidence, base_net="OTHER")


def test_direct_drive_candidate_revalidates_current_output_peers() -> None:
    observed = bjt_base_drive_netlist()
    candidate = bjts_with_direct_output_base_drive(observed)[0]

    assert isinstance(candidate, BjtBaseCandidate)
    assert isinstance(candidate.source_evidence, BjtBaseDirectDriveEvidence)
    assert candidate.source_evidence.observed is observed
    assert candidate.evidence["output_pins"] == ("U1.1",)
    assert candidate.evidence["output_pin_types"] == ("U1.1=output",)

    with pytest.raises(ValueError, match="current base net"):
        replace(candidate.source_evidence, output_peers=(("U1.2", "output"),))


def test_candidate_wire_fields_must_match_the_typed_bjt_source() -> None:
    candidate = bjts_with_direct_output_base_drive(bjt_base_drive_netlist())[0]
    assert isinstance(candidate, BjtBaseCandidate)
    source = candidate.source_evidence
    assert isinstance(source, BjtBaseDirectDriveEvidence)

    with pytest.raises(ValueError, match="typed source projection"):
        BjtBaseCandidate(
            rule_id="component.bjt_base_direct_drive",
            subject="synthetic BJT base",
            message="Review source identity.",
            evidence={"base_net": ("WRONG",)},
            source_evidence=source,
        )
