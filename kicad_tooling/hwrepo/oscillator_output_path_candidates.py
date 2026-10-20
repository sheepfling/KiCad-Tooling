"""Build review candidates from project-mapped oscillator output paths."""

from __future__ import annotations

import hashlib

from .design_lint_types import Candidate
from .models import NetlistContract
from .oscillator_output_path_models import OscillatorOutputPathMap
from .oscillator_output_paths import oscillator_output_path_mismatches


def oscillator_output_path_candidates(
    observed: NetlistContract,
    path_map: OscillatorOutputPathMap | None,
) -> tuple[Candidate, ...]:
    """Report only deviations from an explicitly authored oscillator topology."""
    if path_map is None:
        return ()
    map_sha256 = hashlib.sha256(path_map.model_dump_json().encode("utf-8")).hexdigest()
    return tuple(
        Candidate(
            rule_id="oscillator.output_load_path_mismatch",
            subject=f"{mismatch.path_id}: mapped oscillator output path differs",
            message=(
                "The source-bound native netlist differs from the project-authored oscillator "
                "output path. Review the mapped module pin, fitted load pins, and any required "
                "series resistor and value range. This check does not assert that every clock "
                "output needs a resistor or establish signal integrity."
            ),
            evidence={
                "path_id": (mismatch.path_id,),
                "basis": (mismatch.basis,),
                "oscillator_output_pin": (mismatch.oscillator_output_pin,),
                "expected_topology": (mismatch.topology,),
                "load_pins": mismatch.load_pins,
                "series_resistor": (
                    () if mismatch.series_resistor is None else (mismatch.series_resistor,)
                ),
                "map_sha256": (map_sha256,),
                "issues": mismatch.issues,
            },
        )
        for mismatch in oscillator_output_path_mismatches(path_map, observed)
    )
