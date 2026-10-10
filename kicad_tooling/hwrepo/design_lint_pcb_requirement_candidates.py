"""Theme-specific candidate translators for PCB measurements and rule coverage."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import (
    PcbKeepoutCoverageReport,
)
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageReport,
    PcbSignalPathRuleCoverageReport,
)
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
)


def pcb_requirement_coverage_candidates(
    *,
    pcb_switching_loop_coverage: PcbSwitchingLoopCoverageReport | None = None,
    pcb_differential_pair_coverage: PcbDifferentialPairRuleCoverageReport | None = None,
    pcb_signal_path_coverage: PcbSignalPathRuleCoverageReport | None = None,
    pcb_keepout_coverage: PcbKeepoutCoverageReport | None = None,
    pcb_rf_module_antenna_coverage: PcbRfModuleAntennaCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Translate authored PCB requirement coverage gaps into review candidates."""
    found: list[Candidate] = []
    if pcb_switching_loop_coverage is not None:
        for entry in pcb_switching_loop_coverage.entries:
            if entry.status == "COMPLETE" and entry.maximum_area_um2 is not None:
                continue
            area = (
                "unavailable"
                if entry.loop_area_twice_nm2 is None
                else f"{entry.loop_area_twice_nm2 / 2_000_000_000_000:.6f} mm^2"
            )
            found.append(
                Candidate(
                    rule_id="pcb.switching_loop_geometry",
                    subject=f"{entry.id}: return net {entry.return_net}",
                    message=(
                        "Review the mapped switching-current loop, measured trace chains, and "
                        "return-plane evidence. The area is a polygon through authored pad "
                        "centers; trace lengths use native endpoint geometry. Neither establishes "
                        "the full current path or estimates parasitics, emissions, stability, or "
                        "electrical performance."
                    ),
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
                            "not configured"
                            if entry.maximum_area_um2 is None
                            else str(entry.maximum_area_um2),
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
                            ()
                            if entry.return_island_index is None
                            else (str(entry.return_island_index),)
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
            )
    if pcb_differential_pair_coverage is not None:
        for entry in pcb_differential_pair_coverage.entries:
            if entry.status != "INCOMPLETE":
                continue
            constraint_evidence = tuple(
                f"{item.constraint}: {item.status}"
                + ("" if item.issue is None else f" ({item.issue})")
                for item in entry.constraints
                if item.status != "COVERED"
            )
            found.append(
                Candidate(
                    rule_id="pcb.differential_pair_rule_coverage",
                    subject=f"{entry.id}: {entry.positive_net} / {entry.negative_net}",
                    message=(
                        "This project-authored differential-pair requirement is missing an exact, "
                        "active native DRC rule or supported pair identity. Review the pair map, "
                        "KiCad rule file, and ignored-check settings."
                    ),
                    evidence={
                        "positive_net": (entry.positive_net,),
                        "negative_net": (entry.negative_net,),
                        "pair_selector": (entry.pair_selector,),
                        "basis": (entry.basis,),
                        "constraints": constraint_evidence,
                        "issues": entry.issues,
                    },
                )
            )
    if pcb_signal_path_coverage is not None:
        for entry in pcb_signal_path_coverage.entries:
            if entry.status != "INCOMPLETE":
                continue
            subject = (
                f"{entry.id}: {entry.net} {entry.from_pad} to {entry.to_pad}"
                if entry.kind == "path"
                else f"{entry.id}: {entry.from_pad_pattern} to {entry.to_pad_pattern} bundle"
            )
            constraint_evidence = tuple(
                f"{item.constraint}: {item.status}"
                + ("" if item.issue is None else f" ({item.issue})")
                for item in entry.constraints
                if item.status != "COVERED"
            )
            found.append(
                Candidate(
                    rule_id="pcb.signal_path_rule_coverage",
                    subject=subject,
                    message=(
                        "This mapped PCB signal-path requirement lacks exact active native DRC "
                        "coverage or its mapped pads do not match source-bound board evidence. "
                        "Review the path map, native rule, and endpoint connectivity."
                    ),
                    evidence={
                        "basis": (entry.basis,),
                        "constraints": constraint_evidence,
                        "issues": entry.issues,
                        "path_ids": entry.path_ids,
                    },
                )
            )
    if pcb_keepout_coverage is not None:
        for entry in pcb_keepout_coverage.entries:
            if entry.status != "INCOMPLETE":
                continue
            observed_restrictions = tuple(
                f"{name}={value}"
                for name, value in (
                    ("tracks", entry.observed_forbids_tracks),
                    ("vias", entry.observed_forbids_vias),
                    ("pads", entry.observed_forbids_pads),
                    ("zone_fills", entry.observed_forbids_zone_fills),
                    ("footprints", entry.observed_forbids_footprints),
                )
                if value is not None
            )
            found.append(
                Candidate(
                    rule_id="pcb.keepout_intent_coverage",
                    subject=f"{entry.id}: named keepout {entry.name}",
                    message=(
                        "This named PCB keepout differs from its project-reviewed geometry, "
                        "copper-layer, or restriction signature. Review the independent source "
                        "requirement and the native rule area before updating either record."
                    ),
                    evidence={
                        "basis": (entry.basis,),
                        "expected_geometry_sha256": (entry.expected_geometry_sha256,),
                        "observed_geometry_sha256": (
                            ()
                            if entry.observed_geometry_sha256 is None
                            else (entry.observed_geometry_sha256,)
                        ),
                        "expected_layers": entry.expected_layers,
                        "observed_layers": entry.observed_layers,
                        "observed_restrictions": observed_restrictions,
                        "issues": entry.issues,
                    },
                )
            )
    if pcb_rf_module_antenna_coverage is not None:
        for entry in pcb_rf_module_antenna_coverage.entries:
            if entry.status != "INCOMPLETE":
                continue
            found.append(
                Candidate(
                    rule_id="pcb.rf_module_antenna_keepout_coverage",
                    subject=f"{entry.reference}: {entry.disposition} antenna requirement",
                    message=(
                        "This RF module does not match the project-authored schematic and PCB "
                        "identity, fitted state, feed net, or placement-relative antenna keepout. "
                        "Review the independent module documentation and native source evidence."
                    ),
                    evidence={
                        "basis": (entry.basis,),
                        "disposition": (entry.disposition,),
                        "expected_symbol": (entry.expected_symbol,),
                        "observed_symbol": (
                            () if entry.observed_symbol is None else (entry.observed_symbol,)
                        ),
                        "expected_footprint": (entry.expected_footprint,),
                        "observed_schematic_footprint": (
                            ()
                            if entry.observed_schematic_footprint is None
                            else (entry.observed_schematic_footprint,)
                        ),
                        "observed_board_footprint": (
                            ()
                            if entry.observed_board_footprint is None
                            else (entry.observed_board_footprint,)
                        ),
                        "expected_part_id": (
                            () if entry.expected_part_id is None else (entry.expected_part_id,)
                        ),
                        "observed_part_id": (
                            () if entry.observed_part_id is None else (entry.observed_part_id,)
                        ),
                        "rf_feed_pad": (() if entry.rf_feed_pad is None else (entry.rf_feed_pad,)),
                        "expected_rf_feed_net": (
                            ()
                            if entry.expected_rf_feed_net is None
                            else (entry.expected_rf_feed_net,)
                        ),
                        "observed_schematic_rf_feed_nets": (entry.observed_schematic_rf_feed_nets),
                        "observed_board_rf_feed_net": (
                            ()
                            if entry.observed_board_rf_feed_net is None
                            else (entry.observed_board_rf_feed_net,)
                        ),
                        "expected_keepout_name": (
                            ()
                            if entry.expected_keepout_name is None
                            else (entry.expected_keepout_name,)
                        ),
                        "expected_geometry_sha256": (
                            ()
                            if entry.expected_geometry_sha256 is None
                            else (entry.expected_geometry_sha256,)
                        ),
                        "observed_geometry_sha256": (
                            ()
                            if entry.observed_geometry_sha256 is None
                            else (entry.observed_geometry_sha256,)
                        ),
                        "issues": entry.issues,
                    },
                )
            )
    return tuple(found)
