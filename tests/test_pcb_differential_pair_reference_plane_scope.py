"""Review explicit differential-pair maps with missing plane-map scope."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_candidate_aggregation import fingerprint
from kicad_tooling.hwrepo.design_lint_pcb_measurement_candidates import (
    pcb_measurement_coverage_candidates,
)
from kicad_tooling.hwrepo.design_lint_types import Candidate
from kicad_tooling.hwrepo.pcb_drc_models import (
    PcbDifferentialPairRuleRequirement,
    PcbDrcMinMaxRequirement,
)
from kicad_tooling.hwrepo.pcb_pair_reference_plane_scope import (
    PcbDifferentialPairPlaneScopeCandidate,
)
from kicad_tooling.hwrepo.pcb_reference_plane_models import (
    PcbReferencePlaneMap,
    PcbReferencePlaneRequirement,
)
from tests.test_pcb_drc_coverage import pair_map

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.return_path_lint]


RULE = "pcb.differential_pair_reference_plane_scope_missing"


def reference_map(*signal_nets: str) -> PcbReferencePlaneMap:
    return PcbReferencePlaneMap(
        basis="Synthetic independent reference-plane coverage review",
        requirements=tuple(
            PcbReferencePlaneRequirement(
                id=f"{net.casefold().replace('+', 'plus')}-plane",
                basis=f"Synthetic scope for {net}",
                signal_net=net,
                signal_layers=("F.Cu",),
                reference_net="GND",
                minimum_track_length_um=1,
                minimum_referenced_fraction=0.9,
            )
            for net in signal_nets
        ),
    )


def candidates(
    *,
    plane_map: PcbReferencePlaneMap | None,
    is_pcb_project: bool = True,
) -> tuple[Candidate, ...]:
    return pcb_measurement_coverage_candidates(
        pcb_differential_pair_rule_map=pair_map(),
        pcb_reference_plane_map=plane_map,
        is_pcb_project=is_pcb_project,
    )


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_explicit_pair_without_reference_plane_scope_is_reviewable() -> None:
    (finding,) = candidates(plane_map=None)

    assert isinstance(finding, PcbDifferentialPairPlaneScopeCandidate)
    assert finding.rule_id == RULE
    assert finding.evidence["missing_reference_plane_nets"] == ("USB_D_P", "USB_D_N")
    assert finding.evidence["reference_plane_map_sha256"] == ("absent",)
    assert "does not require a reference net, common ground, layer, or threshold" in finding.message


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_partial_plane_map_names_only_the_omitted_pair_net() -> None:
    (finding,) = candidates(plane_map=reference_map("usb_d_p"))

    assert finding.evidence["missing_reference_plane_nets"] == ("USB_D_N",)
    assert finding.evidence["positive_net"] == ("USB_D_P",)
    assert finding.evidence["negative_net"] == ("USB_D_N",)


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_both_pair_nets_in_plane_map_are_a_quiet_control() -> None:
    assert candidates(plane_map=reference_map("USB_D_P", "USB_D_N")) == ()


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_no_pair_map_and_non_pcb_projects_are_out_of_scope() -> None:
    assert pcb_measurement_coverage_candidates(is_pcb_project=True) == ()
    assert candidates(plane_map=None, is_pcb_project=False) == ()


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_candidate_projection_keeps_source_maps_and_is_stable() -> None:
    first = candidates(plane_map=reference_map("USB_D_P"))
    second = candidates(plane_map=reference_map("USB_D_P"))

    assert first == second
    candidate = first[0]
    assert isinstance(candidate, PcbDifferentialPairPlaneScopeCandidate)
    assert candidate.source_evidence.pair_map is not None
    assert candidate.source_evidence.reference_plane_map is not None
    legacy_projection = Candidate(
        rule_id=candidate.rule_id,
        subject=candidate.subject,
        message=candidate.message,
        evidence=candidate.evidence,
    )
    assert fingerprint(candidate) == fingerprint(legacy_projection)


@pytest.mark.design_lint_rule(rule_id=RULE)
def test_pair_and_plane_requirement_order_does_not_change_candidate_order() -> None:
    authored_pairs = pair_map()
    serial_pair = PcbDifferentialPairRuleRequirement(
        id="serial-data",
        basis="Synthetic independent serial pair",
        positive_net="SERIAL_P",
        negative_net="SERIAL_N",
        pair_selector="SERIAL_",
        track_width=PcbDrcMinMaxRequirement(min_nm=250_000),
    )
    ordered_pairs = authored_pairs.model_copy(
        update={"requirements": (*authored_pairs.requirements, serial_pair)}
    )
    reordered_pairs = ordered_pairs.model_copy(
        update={"requirements": tuple(reversed(ordered_pairs.requirements))}
    )
    authored_planes = reference_map("USB_D_P", "SERIAL_P")
    reordered_planes = authored_planes.model_copy(
        update={"requirements": tuple(reversed(authored_planes.requirements))}
    )

    ordered = pcb_measurement_coverage_candidates(
        pcb_differential_pair_rule_map=ordered_pairs,
        pcb_reference_plane_map=authored_planes,
        is_pcb_project=True,
    )
    reordered = pcb_measurement_coverage_candidates(
        pcb_differential_pair_rule_map=reordered_pairs,
        pcb_reference_plane_map=reordered_planes,
        is_pcb_project=True,
    )

    def semantic_findings(items: tuple[Candidate, ...]) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return tuple(
            (item.subject, item.evidence["missing_reference_plane_nets"]) for item in items
        )

    assert semantic_findings(ordered) == semantic_findings(reordered)
    assert tuple(item.subject for item in ordered) == tuple(
        sorted(
            (item.subject for item in ordered),
            key=lambda value: (value.casefold(), value),
        )
    )
