"""Constraint names documented or accepted by KiCad 10.0 custom DRC rules."""

from __future__ import annotations

import re

KICAD_10_0_CUSTOM_DRC_CONSTRAINT_TYPES = frozenset(
    {
        "annular_width",
        "assertion",
        "bridged_mask",
        "clearance",
        "connection_width",
        "courtyard_clearance",
        "creepage",
        "diff_pair_gap",
        "diff_pair_uncoupled",
        "disallow",
        "edge_clearance",
        "hole",
        "hole_clearance",
        "hole_size",
        "hole_to_hole",
        "length",
        "mechanical_clearance",
        "mechanical_hole_clearance",
        "min_resolved_spokes",
        "physical_clearance",
        "physical_hole_clearance",
        "silk_clearance",
        "skew",
        "solder_mask_expansion",
        "solder_mask_sliver",
        "solder_paste_abs_margin",
        "solder_paste_rel_margin",
        "text_height",
        "text_thickness",
        "thermal_relief_gap",
        "thermal_spoke_width",
        "track_angle",
        "track_segment_length",
        "track_width",
        "via_count",
        "via_dangling",
        "via_diameter",
        "zone_connection",
    }
)

_SUPPORTED_KICAD_VERSION = re.compile(r"10\.0\.\d+\Z")


def supports_kicad_10_0_constraint_registry(version: str) -> bool:
    """Use this release-scoped vocabulary only with KiCad 10.0.x projects."""
    return _SUPPORTED_KICAD_VERSION.fullmatch(version) is not None
