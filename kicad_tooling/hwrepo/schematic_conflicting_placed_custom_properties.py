"""Review conflicting duplicate user fields on placed schematic symbols."""

from __future__ import annotations

from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .kicad_sexpr import sexpr_atoms
from .project_models import ProjectConfig, ProjectKind
from .schematic_geometry_source import schematic_nodes, schematic_property, schematic_root
from .schematic_source_tree import verified_schematic_sources
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "schematic.conflicting_placed_custom_properties"
_SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.0", "10.0.5", "10.0.8"})
_RESERVED_FIELD_NAMES = frozenset(
    {"reference", "value", "footprint", "datasheet", "description", "dnp"}
)
_UNPARSEABLE_SOURCE_ERRORS = frozenset(
    {"Malformed KiCad schematic source", "Expected one kicad_sch root"}
)


def source_bound_conflicting_placed_custom_property_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review conflicting duplicate custom fields on source-hashed placed symbols."""
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
            properties: dict[str, list[tuple[str, int]]] = {}
            for node in schematic_nodes(text, symbol, "property"):
                atoms = sexpr_atoms(text, node)
                if len(atoms) != 3:
                    continue
                name = atoms[1]
                normalized_name = name.casefold()
                if (
                    not name
                    or normalized_name in _RESERVED_FIELD_NAMES
                    or normalized_name.startswith("ki_")
                ):
                    continue
                line = text.count("\n", 0, node.start) + 1
                properties.setdefault(name, []).append((atoms[2], line))

            reference = schematic_property(text, symbol, "Reference") or "<unknown>"
            uuid_nodes = schematic_nodes(text, symbol, "uuid")
            symbol_uuid = (
                sexpr_atoms(text, uuid_nodes[0])[1]
                if len(uuid_nodes) == 1 and len(sexpr_atoms(text, uuid_nodes[0])) == 2
                else "<unknown>"
            )
            for name, entries in properties.items():
                values = tuple(value for value, _line in entries)
                if len(values) < 2 or len(set(values)) < 2:
                    continue
                lines = tuple(str(line) for _value, line in entries)
                candidates.append(
                    Candidate(
                        rule_id=_RULE_ID,
                        subject=(f"{source_file.source_path}:{lines[0]}:{reference}:{name}"),
                        message=(
                            f"Placed symbol {reference} has conflicting direct custom field "
                            f"{name!r} on lines {', '.join(lines)}. Native exports retain "
                            "only one value in the measured KiCad versions, and the selected "
                            "value differs by version; review the intended field value."
                        ),
                        evidence={
                            "source_path": (source_file.source_path,),
                            "source_sha256": (source_file.source_sha256,),
                            "reference": (reference,),
                            "symbol_uuid": (symbol_uuid,),
                            "property_name": (name,),
                            "property_values": values,
                            "property_lines": lines,
                            "property_count": (str(len(values)),),
                        },
                    )
                )
    return tuple(candidates)
