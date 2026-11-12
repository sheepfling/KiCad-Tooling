"""Source-bound integrity checks for embedded schematic library symbols."""

from __future__ import annotations

from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .project_models import ProjectConfig, ProjectKind
from .schematic_geometry_source import (
    schematic_library_symbols,
    schematic_nodes,
    schematic_property,
    schematic_root,
    schematic_scalar,
)
from .schematic_source_tree import verified_schematic_sources
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "schematic.missing_embedded_symbol_definition"
_SUPPORTED_KICAD_VERSION = "10.0.5"
_UNPARSEABLE_SOURCE_ERRORS = frozenset(
    {"Malformed KiCad schematic source", "Expected one kicad_sch root"}
)


def missing_embedded_library_symbol_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Find placed symbols whose exact library IDs have no embedded definition."""
    if config.kind is ProjectKind.PCB_ONLY or config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return ()

    primary_path = Path(config.project).with_suffix(".kicad_sch").as_posix()
    project_directory = Path(primary_path).parent.as_posix()
    try:
        source_tree = verified_schematic_sources(
            root,
            primary_path,
            project_directory,
            source_hashes,
        )
    except ValueError as exc:
        if str(exc) in _UNPARSEABLE_SOURCE_ERRORS:
            return ()
        raise

    candidates: list[Candidate] = []
    for source_file in source_tree.source_files:
        try:
            document = schematic_root(source_file.contents)
        except ValueError as exc:
            if str(exc) in _UNPARSEABLE_SOURCE_ERRORS:
                continue
            raise
        text = document.text
        sections = schematic_nodes(text, document.root, "lib_symbols")
        if len(sections) > 1:
            continue
        try:
            embedded = schematic_library_symbols(text, document.root) if sections else {}
        except ValueError:
            continue
        embedded_ids = tuple(sorted(embedded))
        for symbol in schematic_nodes(text, document.root, "symbol"):
            try:
                library_id = schematic_scalar(text, symbol, "lib_id")
            except ValueError:
                continue
            if library_id in embedded:
                continue

            uuid_nodes = schematic_nodes(text, symbol, "uuid")
            symbol_uuid = (
                schematic_scalar(text, symbol, "uuid") if len(uuid_nodes) == 1 else "<unknown>"
            )
            reference = schematic_property(text, symbol, "Reference") or "<unknown>"
            source_line = text.count("\n", 0, symbol.start) + 1
            candidates.append(
                Candidate(
                    rule_id=_RULE_ID,
                    subject=f"{source_file.source_path}:{source_line}:{reference}",
                    message=(
                        f"Placed symbol {reference} references embedded library ID "
                        f"{library_id!r}, but this schematic has no matching definition."
                    ),
                    evidence={
                        "source_path": (source_file.source_path,),
                        "source_sha256": (source_file.source_sha256,),
                        "source_line": (str(source_line),),
                        "reference": (reference,),
                        "symbol_uuid": (symbol_uuid,),
                        "library_id": (library_id,),
                        "embedded_library_ids": embedded_ids or ("<none>",),
                    },
                )
            )
    return tuple(candidates)
