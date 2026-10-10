"""Format source-bound PCB lint coverage evidence."""

from __future__ import annotations

from .models import DesignLintReport


def _format_polygon_area_mm2(area_twice_nm2: int | None) -> str:
    if area_twice_nm2 is None:
        return "unavailable"
    millionths = (area_twice_nm2 + 1_000_000) // 2_000_000
    return f"{millionths // 1_000_000}.{millionths % 1_000_000:06d} mm^2"


def pcb_coverage_report_lines(report: DesignLintReport) -> list[str]:
    """Render PCB measurement, geometry, and native-rule coverage sections."""
    lines: list[str] = []
    decoupling = report.pcb_decoupling

    lines.append(
        f"PCB decoupling coverage: {decoupling.status} (mode: {decoupling.mode or 'not configured'})"
    )

    if decoupling.board_path is not None:
        lines.append(
            f"  Board: {decoupling.board_path} (SHA-256 {decoupling.board_sha256 or 'unavailable'})"
        )

    if decoupling.snapshot_path is not None:
        lines.append(
            f"  Native geometry: {decoupling.snapshot_path} (SHA-256 {decoupling.snapshot_sha256 or 'unavailable'})"
        )

    for entry in decoupling.entries:
        lines.append(
            f"  {entry.id}: {entry.status}; IC supply {entry.ic_supply_pad}; "
            f"selected capacitors {', '.join(entry.selected_capacitors) or 'none'}"
        )
        for candidate in entry.candidates:
            distance = (
                "unavailable"
                if candidate.distance_nm is None
                else f"{candidate.distance_nm // 1000}.{candidate.distance_nm % 1000:03d} um"
            )
            lines.append(
                f"    {candidate.reference}: {distance}; "
                f"eligible={'yes' if candidate.eligible else 'no'}"
            )

    if decoupling.issue is not None:
        lines.append(f"  Issue: {decoupling.issue}")

    protection_path = report.pcb_protection_path

    lines.append(
        f"PCB protection-path coverage: {protection_path.status} "
        f"(mode: {protection_path.mode or 'not configured'})"
    )

    if protection_path.board_path is not None:
        lines.append(
            f"  Board: {protection_path.board_path} "
            f"(SHA-256 {protection_path.board_sha256 or 'unavailable'})"
        )

    if protection_path.snapshot_path is not None:
        lines.append(
            f"  Native geometry: {protection_path.snapshot_path} "
            f"(SHA-256 {protection_path.snapshot_sha256 or 'unavailable'})"
        )

    for entry in protection_path.entries:
        distance = (
            "unavailable"
            if entry.connector_to_protection_distance_nm is None
            else f"{entry.connector_to_protection_distance_nm} nm"
        )
        via_measurement = (
            "not configured"
            if entry.reference_vias_within_radius is None
            else f"{entry.reference_vias_within_radius} within {entry.reference_via_radius_um} um"
        )
        lines.append(
            f"  {entry.id}: {entry.status}; {entry.connector_signal_pad} to "
            f"{entry.protection_signal_pad} {distance}; reference pad "
            f"{entry.protection_reference_pad}, connected vias "
            f"{entry.connected_reference_via_count}, radius count {via_measurement}"
        )
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if protection_path.issue is not None:
        lines.append(f"  Issue: {protection_path.issue}")

    track_width = report.pcb_track_width

    lines.append(
        f"PCB track-width coverage: {track_width.status} "
        f"(mode: {track_width.mode or 'not configured'})"
    )

    if track_width.board_path is not None:
        lines.append(
            f"  Board: {track_width.board_path} "
            f"(SHA-256 {track_width.board_sha256 or 'unavailable'})"
        )

    if track_width.snapshot_path is not None:
        lines.append(
            f"  Native geometry: {track_width.snapshot_path} "
            f"(SHA-256 {track_width.snapshot_sha256 or 'unavailable'})"
        )

    for entry in track_width.entries:
        lines.append(
            f"  {entry.id}: {entry.status}; net {entry.net}; minimum {entry.minimum_width_um} um"
        )
        for item in entry.tracks:
            width = f"{item.width_nm // 1000}.{item.width_nm % 1000:03d} um"
            state = "below minimum" if item.below_minimum else "meets minimum"
            lines.append(
                f"    {item.track_uuid} {item.layer}: {width}; {state}; "
                f"start {item.start_nm[0]},{item.start_nm[1]} nm; "
                f"end {item.end_nm[0]},{item.end_nm[1]} nm"
            )
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if track_width.issue is not None:
        lines.append(f"  Issue: {track_width.issue}")

    reference_plane = report.pcb_reference_plane

    lines.append(
        f"PCB reference-plane coverage: {reference_plane.status} "
        f"(mode: {reference_plane.mode or 'not configured'})"
    )

    if reference_plane.board_path is not None:
        lines.append(
            f"  Board: {reference_plane.board_path} "
            f"(SHA-256 {reference_plane.board_sha256 or 'unavailable'})"
        )

    if reference_plane.snapshot_path is not None:
        lines.append(
            f"  Native geometry: {reference_plane.snapshot_path} "
            f"(SHA-256 {reference_plane.snapshot_sha256 or 'unavailable'})"
        )

    for entry in reference_plane.entries:
        lines.append(
            f"  {entry.id}: {entry.status}; {entry.signal_net} on "
            f"{', '.join(entry.signal_layers)}; reference {entry.reference_net}; "
            f"minimum centerline coverage {entry.minimum_referenced_fraction}; "
            f"minimum track length {entry.minimum_track_length_um} um; "
            "short-track review "
            f"{'enabled' if entry.review_excluded_short_tracks else 'disabled'}"
        )
        for item in entry.tracks:
            fraction = f"{item.covered_fraction_numerator}/{item.covered_fraction_denominator}"
            state = "below minimum" if item.below_minimum else "meets minimum"
            lines.append(
                f"    {item.track_uuid}: {item.signal_layer} over {item.reference_layer}; "
                f"centerline coverage {fraction}; {state}; zones "
                f"{', '.join(item.reference_zone_uuids) or 'none'}"
            )
        if entry.excluded_short_track_uuids:
            lines.append(
                "    Excluded tracks below minimum length: "
                + ", ".join(entry.excluded_short_track_uuids)
            )
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if reference_plane.issue is not None:
        lines.append(f"  Issue: {reference_plane.issue}")

    switching_loop = report.pcb_switching_loop

    lines.append(
        f"PCB switching-loop coverage: {switching_loop.status} "
        f"(mode: {switching_loop.mode or 'not configured'})"
    )

    if switching_loop.board_path is not None:
        lines.append(
            f"  Board: {switching_loop.board_path} "
            f"(SHA-256 {switching_loop.board_sha256 or 'unavailable'})"
        )

    if switching_loop.snapshot_path is not None:
        lines.append(
            f"  Native geometry: {switching_loop.snapshot_path} "
            f"(SHA-256 {switching_loop.snapshot_sha256 or 'unavailable'})"
        )

    for entry in switching_loop.entries:
        area = _format_polygon_area_mm2(entry.loop_area_twice_nm2)
        limit = (
            "not configured" if entry.maximum_area_um2 is None else f"{entry.maximum_area_um2} um^2"
        )
        lines.append(
            f"  {entry.id}: {entry.status}; pad-center polygon {area}; limit {limit}; "
            f"return plane {entry.return_net} on {entry.return_plane_layer}: "
            f"{entry.return_plane_status}; trace-route coverage {entry.route_status}"
        )
        if entry.return_zone_uuid is not None:
            lines.append(
                f"    Filled zone {entry.return_zone_uuid}, island {entry.return_island_index}"
            )
        for route_edge in entry.route_edges:
            length = "unavailable" if route_edge.length_nm is None else f"{route_edge.length_nm} nm"
            tracks = ", ".join(route_edge.track_uuids) or "none"
            detail = (
                f"    Route edge {route_edge.edge_index} {route_edge.from_pad} to "
                f"{route_edge.to_pad}: {route_edge.kind} {route_edge.status}; "
                f"length {length}; tracks {tracks}"
            )
            if route_edge.plane_zone_uuid is not None:
                contour_area = (
                    "unavailable"
                    if route_edge.plane_island_area_twice_nm2 is None
                    else f"{route_edge.plane_island_area_twice_nm2} nm^2"
                )
                detail += (
                    f"; filled zone {route_edge.plane_zone_uuid}, "
                    f"island {route_edge.plane_island_index}; contour doubled area {contour_area}"
                )
            if route_edge.issue is not None:
                detail += f"; {route_edge.issue}"
            lines.append(detail)
        for issue in entry.issues:
            lines.append(f"    Review: {issue}")

    if switching_loop.issue is not None:
        lines.append(f"  Coverage issue: {switching_loop.issue}")

    pair_rules = report.pcb_differential_pair_rules

    lines.append(
        "PCB differential-pair DRC rule coverage: "
        f"{pair_rules.status} (mode: {pair_rules.mode or 'not configured'})"
    )

    if pair_rules.project_path is not None:
        lines.append(
            f"  Project settings: {pair_rules.project_path} "
            f"(SHA-256 {pair_rules.project_sha256 or 'unavailable'})"
        )

    if pair_rules.rules_path is not None:
        lines.append(
            f"  Native rules: {pair_rules.rules_path} "
            f"(SHA-256 {pair_rules.rules_sha256 or 'absent'})"
        )

    if pair_rules.board_path is not None:
        lines.append(
            f"  Board: {pair_rules.board_path} (SHA-256 {pair_rules.board_sha256 or 'unavailable'})"
        )

    if pair_rules.native_drc_path is not None:
        lines.append(
            f"  Native DRC: {pair_rules.native_drc_path} "
            f"(SHA-256 {pair_rules.native_drc_sha256 or 'unavailable'})"
        )

    if pair_rules.kicad_version is not None:
        lines.append(f"  KiCad version: {pair_rules.kicad_version}")

    for entry in pair_rules.entries:
        lines.append(
            f"  {entry.id}: {entry.status}; {entry.positive_net} / {entry.negative_net}; "
            f"selector {entry.pair_selector}"
        )
        for item in entry.constraints:
            expected = f"min={item.expected_min_nm}, max={item.expected_max_nm} nm"
            observed = f"min={item.observed_min_nm}, max={item.observed_max_nm} nm"
            rules = ", ".join(item.rule_names) or "none"
            lines.append(
                f"    {item.constraint}: {item.status}; expected {expected}; "
                f"observed {observed}; rules {rules}"
            )
            if item.issue is not None:
                lines.append(f"      Issue: {item.issue}")
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if pair_rules.issue is not None:
        lines.append(f"  Coverage issue: {pair_rules.issue}")

    signal_paths = report.pcb_signal_path_rules

    lines.append(
        "PCB signal-path DRC rule coverage: "
        f"{signal_paths.status} (mode: {signal_paths.mode or 'not configured'})"
    )

    if signal_paths.project_path is not None:
        lines.append(
            f"  Project settings: {signal_paths.project_path} "
            f"(SHA-256 {signal_paths.project_sha256 or 'unavailable'})"
        )

    if signal_paths.rules_path is not None:
        lines.append(
            f"  Native rules: {signal_paths.rules_path} "
            f"(SHA-256 {signal_paths.rules_sha256 or 'absent'})"
        )

    if signal_paths.board_path is not None:
        lines.append(
            f"  Board: {signal_paths.board_path} "
            f"(SHA-256 {signal_paths.board_sha256 or 'unavailable'})"
        )

    if signal_paths.native_drc_path is not None:
        lines.append(
            f"  Native DRC: {signal_paths.native_drc_path} "
            f"(SHA-256 {signal_paths.native_drc_sha256 or 'unavailable'})"
        )

    if signal_paths.pcb_snapshot_path is not None:
        lines.append(
            f"  Native PCB snapshot: {signal_paths.pcb_snapshot_path} "
            f"(SHA-256 {signal_paths.pcb_snapshot_sha256 or 'unavailable'})"
        )

    if signal_paths.kicad_version is not None:
        lines.append(f"  KiCad version: {signal_paths.kicad_version}")

    for entry in signal_paths.entries:
        if entry.kind == "path":
            identity = f"{entry.net}: {entry.from_pad} to {entry.to_pad}"
        else:
            identity = (
                f"{entry.from_pad_pattern} to {entry.to_pad_pattern}; "
                f"members {', '.join(entry.path_ids)}"
            )
        lines.append(f"  {entry.id}: {entry.status}; {identity}")
        for item in entry.constraints:
            expected = f"min={item.expected_min_nm}, max={item.expected_max_nm} nm"
            observed = f"min={item.observed_min_nm}, max={item.observed_max_nm} nm"
            rules = ", ".join(item.rule_names) or "none"
            lines.append(
                f"    {item.constraint}: {item.status}; expected {expected}; "
                f"observed {observed}; rules {rules}"
            )
            if item.issue is not None:
                lines.append(f"      Issue: {item.issue}")
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if signal_paths.issue is not None:
        lines.append(f"  Coverage issue: {signal_paths.issue}")

    keepouts = report.pcb_keepout_coverage

    lines.append(
        f"PCB keepout intent coverage: {keepouts.status} "
        f"(mode: {keepouts.mode or 'not configured'})"
    )

    if keepouts.board_path is not None:
        lines.append(
            f"  Board: {keepouts.board_path} (SHA-256 {keepouts.board_sha256 or 'unavailable'})"
        )

    if keepouts.snapshot_path is not None:
        lines.append(
            f"  Native PCB snapshot: {keepouts.snapshot_path} "
            f"(SHA-256 {keepouts.snapshot_sha256 or 'unavailable'})"
        )

    for entry in keepouts.entries:
        observed_geometry = entry.observed_geometry_sha256 or "unavailable"
        observed_layers = ", ".join(entry.observed_layers) or "none"
        lines.append(
            f"  {entry.id} ({entry.name}): {entry.status}; "
            f"geometry {observed_geometry}; layers {observed_layers}"
        )
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if keepouts.issue is not None:
        lines.append(f"  Coverage issue: {keepouts.issue}")

    rf_antennas = report.pcb_rf_module_antenna_coverage

    lines.append(
        f"PCB RF module antenna coverage: {rf_antennas.status} "
        f"(mode: {rf_antennas.mode or 'not configured'})"
    )

    if rf_antennas.board_path is not None:
        lines.append(
            f"  Board: {rf_antennas.board_path} "
            f"(SHA-256 {rf_antennas.board_sha256 or 'unavailable'})"
        )

    if rf_antennas.snapshot_path is not None:
        lines.append(
            f"  Native PCB snapshot: {rf_antennas.snapshot_path} "
            f"(SHA-256 {rf_antennas.snapshot_sha256 or 'unavailable'})"
        )

    for entry in rf_antennas.entries:
        lines.append(
            f"  {entry.reference} ({entry.disposition}): {entry.status}; "
            f"symbol {entry.observed_symbol or 'unknown'}; "
            f"schematic footprint {entry.observed_schematic_footprint or 'unknown'}; "
            f"board footprint {entry.observed_board_footprint or 'unknown'}"
        )
        if entry.rf_feed_pad is not None:
            lines.append(
                f"    RF feed: {entry.rf_feed_pad}; expected "
                f"{entry.expected_rf_feed_net or 'none'}; schematic "
                f"{', '.join(entry.observed_schematic_rf_feed_nets) or 'unconnected'}; "
                f"board {entry.observed_board_rf_feed_net or 'unconnected'}"
            )
        if entry.expected_keepout_name is not None:
            lines.append(
                f"    Keepout {entry.expected_keepout_name}: expected geometry "
                f"{entry.expected_geometry_sha256 or 'unavailable'}; observed "
                f"{entry.observed_geometry_sha256 or 'unavailable'}"
            )
        for issue in entry.issues:
            lines.append(f"    Coverage issue: {issue}")

    if rf_antennas.issue is not None:
        lines.append(f"  Coverage issue: {rf_antennas.issue}")
    return lines
