"""Source-bound review of conflicting Reference fields on placed symbols."""

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

_RULE_ID: DesignLintRuleId = "schematic.conflicting_placed_reference_properties"
_SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5", "10.0.8"})
_UNPARSEABLE_SOURCE_ERRORS = frozenset(
    {"Malformed KiCad schematic source", "Expected one kicad_sch root"}
)


def source_bound_conflicting_placed_reference_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review placed symbols with conflicting direct Reference properties."""
    if config.kind is ProjectKind.PCB_ONLY or config.kicad_version not in _SUPPORTED_KICAD_VERSIONS:
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
            reference_properties = schematic_direct_property_value_lines(text, symbol, "Reference")
            values = tuple(value for value, _line in reference_properties)
            if len(values) < 2 or len(set(values)) < 2:
                continue

            reference = values[0] or schematic_property(text, symbol, "Reference") or "<unknown>"
            uuid_nodes = schematic_nodes(text, symbol, "uuid")
            symbol_uuid = (
                sexpr_atoms(text, uuid_nodes[0])[1]
                if len(uuid_nodes) == 1 and len(sexpr_atoms(text, uuid_nodes[0])) == 2
                else "<unknown>"
            )
            property_lines = tuple(str(line) for _value, line in reference_properties)
            candidates.append(
                Candidate(
                    rule_id=_RULE_ID,
                    subject=f"{source_file.source_path}:{property_lines[0]}:{reference}",
                    message=(
                        f"Placed symbol {reference} has conflicting direct Reference properties "
                        f"on lines {', '.join(property_lines)}; KiCad's native netlist uses the "
                        "instance-path reference and does not preserve these conflicting values. "
                        "Review the annotation before relying on exported references."
                    ),
                    evidence={
                        "source_path": (source_file.source_path,),
                        "source_sha256": (source_file.source_sha256,),
                        "reference": (reference,),
                        "symbol_uuid": (symbol_uuid,),
                        "property_values": values,
                        "property_lines": property_lines,
                        "property_count": (str(len(values)),),
                    },
                )
            )
    return tuple(candidates)
