"""Typed source and report projection for switching-loop review candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_switching_loop_models import PcbSwitchingLoopCoverageEntry, PcbSwitchingLoopCoverageReport

RULE_ID: DesignLintRuleId = "pcb.switching_loop_geometry"


@dataclass(frozen=True, slots=True)
class PcbSwitchingLoopFindingEvidence:
    """A mapped loop measurement with its complete source-bound coverage report."""

    report: PcbSwitchingLoopCoverageReport
    entry: PcbSwitchingLoopCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Switching-loop finding evidence requires scanned coverage")
        if self.entry not in self.report.entries:
            raise ValueError("Switching-loop finding must belong to the source report")
        if self.entry.status == "COMPLETE" and self.entry.maximum_area_um2 is not None:
            raise ValueError("Acceptable bounded switching-loop coverage emits no finding")


def project_pcb_switching_loop_evidence(
    source: PcbSwitchingLoopFindingEvidence,
) -> CandidateEvidenceProjection:
    """Keep the established measurement and evidence-boundary fields."""
    entry = source.entry
    area = (
        "unavailable"
        if entry.loop_area_twice_nm2 is None
        else f"{entry.loop_area_twice_nm2 / 2_000_000_000_000:.6f} mm^2"
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "loop_pad_order": entry.loop_pads,
            "pad_center_polygon_area": (area,),
            "trace_route_status": (entry.route_status,),
            "trace_route_edges": tuple(
                f"{item.edge_index}: {item.from_pad} to {item.to_pad}; "
                f"{item.status}; length "
                f"{item.length_nm if item.length_nm is not None else 'unavailable'} nm; "
                f"tracks {', '.join(item.track_uuids) or 'none'}"
                + (
                    f"; filled zone {item.plane_zone_uuid}, island "
                    f"{item.plane_island_index}; contour doubled area "
                    f"{item.plane_island_area_twice_nm2} nm^2"
                    if item.plane_zone_uuid is not None
                    else ""
                )
                + ("; " + item.issue if item.issue is not None else "")
                for item in entry.route_edges
            ),
            "maximum_area_um2": (
                "not configured" if entry.maximum_area_um2 is None else str(entry.maximum_area_um2),
            ),
            "area_exceeds_limit": (
                "not evaluated"
                if entry.area_exceeds_limit is None
                else str(entry.area_exceeds_limit).lower(),
            ),
            "return_net": (entry.return_net,),
            "return_plane_layer": (entry.return_plane_layer,),
            "return_plane_pads": entry.return_plane_pads,
            "return_plane_status": (entry.return_plane_status,),
            "return_zone_uuid": (
                () if entry.return_zone_uuid is None else (entry.return_zone_uuid,)
            ),
            "return_island_index": (
                () if entry.return_island_index is None else (str(entry.return_island_index),)
            ),
            "coverage_status": (entry.status,),
            "basis": (entry.basis,),
            "issues": entry.issues,
            "metric": (
                "Absolute shoelace area of project-ordered native pad centers; "
                + "trace lengths follow uniquely resolved native track chains; "
                + "plane edges identify one shared filled island and can report its "
                + "native contour area",
            ),
            "validation_boundary": (
                "component internals, current distribution, parasitics, hardware, "
                + "and simulation remain outside this measurement",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbSwitchingLoopCandidate(Candidate):
    """Switching-loop finding retaining its exact measurement and source report."""

    source_evidence: PcbSwitchingLoopFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbSwitchingLoopFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbSwitchingLoopCandidate:
        projection = project_pcb_switching_loop_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_switching_loop_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Switching-loop rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Switching-loop evidence must match its projection")
