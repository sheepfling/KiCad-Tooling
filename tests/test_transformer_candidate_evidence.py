"""Transformer candidates retain named winding observations and source netlists."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kicad_tooling.hwrepo.design_lint_component_transformer_candidate_evidence import (
    TransformerCandidate,
    TransformerWindingGroupsShareNetEvidence,
    TransformerWindingSameNetEvidence,
    project_transformer_evidence,
)
from kicad_tooling.hwrepo.design_lint_component_transformers import (
    transformer_winding_groups_share_net_candidates,
    transformer_winding_same_net_candidates,
)
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
]


def _transformer(nets: dict[str, tuple[str, ...]]) -> NetlistContract:
    return NetlistContract(
        components={
            "T1": ComponentContract(
                value="Synthetic transformer",
                footprint="Synthetic:Transformer",
            )
        },
        nets=nets,
        component_symbols={"T1": "Transformer:TRANSF1"},
        component_pin_numbers={"T1": ("1", "2", "3", "4")},
    )


def test_same_winding_candidate_retains_named_group_and_exact_netlist() -> None:
    observed = _transformer(
        {
            "WINDING_1": ("T1.1", "T1.2"),
            "WINDING_2A": ("T1.3",),
            "WINDING_2B": ("T1.4",),
        }
    )

    candidate = transformer_winding_same_net_candidates(observed)[0]
    assert isinstance(candidate, TransformerCandidate)
    source = candidate.source_evidence
    assert isinstance(source, TransformerWindingSameNetEvidence)
    assert source.transformer.observed is observed
    assert source.winding.name == "winding_1"
    assert source.winding.pin_numbers == ("1", "2")
    assert project_transformer_evidence(source).evidence == candidate.evidence
    assert candidate.evidence["pin_assignments"] == (
        "T1.1 -> WINDING_1",
        "T1.2 -> WINDING_1",
    )


def test_cross_winding_candidate_retains_exact_shared_terminal_records() -> None:
    observed = _transformer(
        {
            "SHARED": ("T1.1", "T1.3"),
            "WINDING_1_RETURN": ("T1.2",),
            "WINDING_2_RETURN": ("T1.4",),
        }
    )

    candidate = transformer_winding_groups_share_net_candidates(observed)[0]
    assert isinstance(candidate, TransformerCandidate)
    source = candidate.source_evidence

    assert isinstance(source, TransformerWindingGroupsShareNetEvidence)
    assert source.transformer.observed is observed
    assert tuple(item.pin_number for item in source.first_pin_assignments) == ("1",)
    assert tuple(item.pin_number for item in source.second_pin_assignments) == ("3",)
    assert project_transformer_evidence(source).evidence == candidate.evidence
    assert candidate.evidence["first_winding_pins"] == ("T1.1",)
    assert candidate.evidence["second_winding_pins"] == ("T1.3",)


def test_transformer_source_and_candidate_reject_projection_mismatches() -> None:
    observed = _transformer(
        {
            "WINDING_1": ("T1.1", "T1.2"),
            "WINDING_2A": ("T1.3",),
            "WINDING_2B": ("T1.4",),
        }
    )
    candidate = transformer_winding_same_net_candidates(observed)[0]
    assert isinstance(candidate, TransformerCandidate)
    source = candidate.source_evidence
    assert isinstance(source, TransformerWindingSameNetEvidence)

    with pytest.raises(ValueError, match="source terminals"):
        replace(source, net="WRONG")
    with pytest.raises(ValueError, match="typed source projection"):
        replace(candidate, evidence={"net": ("WRONG",)})
