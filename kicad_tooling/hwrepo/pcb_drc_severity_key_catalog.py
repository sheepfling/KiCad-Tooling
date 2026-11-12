"""Exact KiCad PCB DRC rule-severity setting keys."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

KICAD_10_0_8_DRC_SEVERITY_KEYS = frozenset(
    {
        "annular_width",
        "clearance",
        "connection_width",
        "copper_edge_clearance",
        "copper_sliver",
        "courtyards_overlap",
        "creepage",
        "diff_pair_gap_out_of_range",
        "diff_pair_uncoupled_length_too_long",
        "drill_out_of_range",
        "duplicate_footprints",
        "extra_footprint",
        "footprint",
        "footprint_filters_mismatch",
        "footprint_symbol_field_mismatch",
        "footprint_symbol_mismatch",
        "footprint_type_mismatch",
        "hole_clearance",
        "hole_to_hole",
        "holes_co_located",
        "invalid_outline",
        "isolated_copper",
        "item_on_disabled_layer",
        "items_not_allowed",
        "length_out_of_range",
        "lib_footprint_issues",
        "lib_footprint_mismatch",
        "malformed_courtyard",
        "microvia_drill_out_of_range",
        "mirrored_text_on_front_layer",
        "missing_courtyard",
        "missing_footprint",
        "missing_tuning_profile",
        "net_conflict",
        "nonmirrored_text_on_back_layer",
        "npth_inside_courtyard",
        "padstack",
        "pth_inside_courtyard",
        "shorting_items",
        "silk_edge_clearance",
        "silk_over_copper",
        "silk_overlap",
        "skew_out_of_range",
        "solder_mask_bridge",
        "starved_thermal",
        "text_height",
        "text_on_edge_cuts",
        "text_thickness",
        "through_hole_pad_without_hole",
        "too_many_vias",
        "track_angle",
        "track_dangling",
        "track_not_centered_on_via",
        "track_on_post_machined_layer",
        "track_segment_length",
        "track_width",
        "tracks_crossing",
        "tuning_profile_track_geometries",
        "unconnected_items",
        "unresolved_variable",
        "via_dangling",
        "zones_intersect",
    }
)

# KiCad 10.0.8 migrates these saved spellings to current settings during load.
KICAD_10_0_8_DRC_SEVERITY_MIGRATION_KEYS = frozenset(
    {"hole_near_hole", "legacy_no_courtyard_defined", "legacy_courtyards_overlap"}
)

PCB_DRC_RULE_SEVERITY_KEYS_BY_KICAD_VERSION: Mapping[str, frozenset[str]] = MappingProxyType(
    {"10.0.8": KICAD_10_0_8_DRC_SEVERITY_KEYS | KICAD_10_0_8_DRC_SEVERITY_MIGRATION_KEYS}
)
