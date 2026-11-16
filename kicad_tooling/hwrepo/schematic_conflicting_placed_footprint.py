"""Source-bound review of conflicting Footprint fields on placed symbols."""

from __future__ import annotations

from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .kicad_sexpr import sexpr_atoms
from .project_models import ProjectConfig, ProjectKind
from .schematic_geometry_source import (
    schematic_direct_property_value_lines,
    schematic_nodes,
    schematic_property,
    schematic_root,
)
from .schematic_source_tree import verified_schematic_sources
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "schematic.conflicting_placed_footprint_properties"
_SUPPORTED_KICAD_VERSION = "10.0.8"
_UNPARSEABLE_SOURCE_ERRORS = frozenset(
    {"Malformed KiCad schematic source", "Expected one kicad_sch root"}
)


def source_bound_conflicting_placed_footprint_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review placed symbols with conflicting direct Footprint properties."""
    if config.kind is ProjectKind.PCB_ONLY or config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    schematic_path = Path(config.project).with_suffix(".kicad_sch").as_posix()
    project_directory = Path(schematic_path).parent.as_posix()
    try:
        source_tree = verified_schematic_sources(
            root,
            schematic_path,
            project_directory,
            source_hashes,
        )
    except ValueError as exc:
        if str(exc) in _UNPARSEABLE_SOURCE_ERRORS:
            return ()
        raise

    candidates: list[Candidate] = []
    for source_file in source_tree.source_files:
        document = schematic_root(source_file.contents)
        text = document.text
        for symbol in schematic_nodes(text, document.root, "symbol"):
            footprint_properties = schematic_direct_property_value_lines(
                text,
                symbol,
                "Footprint",
            )
            footprints = tuple(value for value, _line in footprint_properties)
            if len(footprints) < 2 or len(set(footprints)) < 2:
                continue

            reference = schematic_property(text, symbol, "Reference") or "<unknown>"
            uuid_nodes = schematic_nodes(text, symbol, "uuid")
            symbol_uuid = (
                sexpr_atoms(text, uuid_nodes[0])[1]
                if len(uuid_nodes) == 1 and len(sexpr_atoms(text, uuid_nodes[0])) == 2
                else "<unknown>"
            )

            property_lines = tuple(str(line) for _value, line in footprint_properties)
            first_line = property_lines[0]
            candidates.append(
                Candidate(
                    rule_id=_RULE_ID,
                    subject=f"{source_file.source_path}:{first_line}:{reference}",
                    message=(
                        f"Placed symbol {reference} has conflicting direct Footprint properties "
                        f"on lines {', '.join(property_lines)}; review the footprint KiCad will "
                        "export before using this schematic."
                    ),
                    evidence={
                        "source_path": (source_file.source_path,),
                        "source_sha256": (source_file.source_sha256,),
                        "reference": (reference,),
                        "symbol_uuid": (symbol_uuid,),
                        "footprints": footprints,
                        "property_lines": property_lines,
                        "property_count": (str(len(footprints)),),
                    },
                )
            )
    return tuple(candidates)
