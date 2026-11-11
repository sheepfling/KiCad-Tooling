"""Source-bound review of custom DRC layer references."""

from __future__ import annotations

import re
from pathlib import Path

from .contracts import repo_path
from .design_lint_pcb_dru_layer_evidence import (
    PcbDruLayerCandidate,
    PcbDruLayerFindingEvidence,
    PcbDruLayerIssue,
    PcbDruLayerLocation,
)
from .design_lint_pcb_dru_rule_candidate_evidence import (
    is_supported_pcb_dru_kicad_version,
)
from .evidence import digest
from .kicad_sexpr import sexpr_atoms as _atoms
from .kicad_sexpr import sexpr_children as _children
from .pcb_drc_rule_parser import NativeDrcRuleDeclaration, native_rule_declarations
from .pcb_dru_rule_review import source_bound_project_input, source_bound_rule_file
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory

_STANDARD_LAYERS = frozenset(
    {
        "F.Cu",
        "B.Cu",
        "F.Adhes",
        "B.Adhes",
        "F.Paste",
        "B.Paste",
        "F.SilkS",
        "B.SilkS",
        "F.Mask",
        "B.Mask",
        "F.CrtYd",
        "B.CrtYd",
        "F.Fab",
        "B.Fab",
        "Edge.Cuts",
        "Margin",
        "Dwgs.User",
        "Cmts.User",
        "Eco1.User",
        "Eco2.User",
        "Rescue",
    }
    | {f"In{number}.Cu" for number in range(1, 31)}
)
_DISPLAY_ALIASES = {
    "F.Adhesive": "F.Adhes",
    "B.Adhesive": "B.Adhes",
    "F.Silkscreen": "F.SilkS",
    "B.Silkscreen": "B.SilkS",
    "F.Courtyard": "F.CrtYd",
    "B.Courtyard": "B.CrtYd",
    "User.Drawings": "Dwgs.User",
    "User.Comments": "Cmts.User",
    "User.Eco1": "Eco1.User",
    "User.Eco2": "Eco2.User",
    "?.Silkscreen": "?.SilkS",
}
_CONDITION_LAYER = re.compile(r"(?:\.Layer\s*==\s*|\.existsOnLayer\s*\(\s*)['\"]([^'\"]+)['\"]")


def _board_layer_inventory(source: str) -> tuple[frozenset[str], dict[str, str]]:
    """Read canonical and display layer names from the saved board layer table."""
    roots = _children(source, 0, len(source))
    if len(roots) != 1 or _atoms(source, roots[0])[:1] != ("kicad_pcb",):
        raise ValueError("Expected one kicad_pcb root for custom DRC layer review")
    root = roots[0]
    layer_sections = [
        node
        for node in _children(source, root.start + 1, root.end - 1)
        if _atoms(source, node)[:1] == ("layers",)
    ]
    if len(layer_sections) != 1:
        raise ValueError("Expected one top-level board layer inventory")
    names: list[str] = []
    display_aliases: dict[str, str] = {}
    for node in _children(source, layer_sections[0].start + 1, layer_sections[0].end - 1):
        atoms = _atoms(source, node)
        if len(atoms) >= 2 and atoms[0].isdigit() and atoms[1]:
            names.append(atoms[1])
            if len(atoms) >= 4 and atoms[3] and atoms[3] != atoms[1]:
                display_aliases[atoms[3]] = atoms[1]
    if not names or len(names) != len(set(names)):
        raise ValueError("Board layer inventory must contain unique named layers")
    return frozenset(names), display_aliases


def _rule_layer_references(
    rule: NativeDrcRuleDeclaration,
) -> tuple[tuple[str, PcbDruLayerLocation], ...]:
    """Return direct layer clauses and supported layer comparisons in rule conditions."""
    references: list[tuple[str, PcbDruLayerLocation]] = [
        (name, "layer_clause") for name in rule.layers
    ]
    if rule.condition is not None:
        references.extend(
            (match.group(1), "condition") for match in _CONDITION_LAYER.finditer(rule.condition)
        )
    unique: dict[tuple[str, PcbDruLayerLocation], None] = {}
    for layer_name, location in references:
        unique.setdefault((layer_name, location), None)
    return tuple(unique)


def _layer_issue(
    layer_name: str,
    location: PcbDruLayerLocation,
    board_layers: frozenset[str],
    display_aliases: dict[str, str],
) -> PcbDruLayerIssue | None:
    canonical = display_aliases.get(layer_name) or _DISPLAY_ALIASES.get(layer_name)
    if canonical is not None:
        return PcbDruLayerIssue(
            layer_name=layer_name,
            canonical_layer=canonical,
            kind="display_alias",
            location=location,
        )
    if layer_name in board_layers:
        return None
    if layer_name in _STANDARD_LAYERS or re.fullmatch(
        r"(?:User\.[1-9]|In(?:[1-9]|[12][0-9]|30)\.Cu)", layer_name
    ):
        return PcbDruLayerIssue(
            layer_name=layer_name,
            kind="layer_not_in_board",
            location=location,
        )
    if "*" in layer_name or "?" in layer_name:
        return None
    return PcbDruLayerIssue(
        layer_name=layer_name,
        kind="unknown_layer",
        location=location,
    )


def _candidate_message(issues: tuple[PcbDruLayerIssue, ...]) -> str:
    messages: list[str] = []
    for issue in issues:
        if issue.kind == "display_alias":
            messages.append(
                f"{issue.layer_name!r} is a display-name spelling; use the stable "
                f"file-format name {issue.canonical_layer!r}."
            )
        elif issue.kind == "layer_not_in_board":
            messages.append(
                f"{issue.layer_name!r} is not in the current board's saved layer inventory; "
                "confirm the rule is intended for another stackup or board variant."
            )
        else:
            messages.append(
                f"{issue.layer_name!r} is neither a recognized KiCad layer name nor present "
                "in the current board's saved layer inventory."
            )
    return (
        "Review this custom DRC rule's layer references. "
        + " ".join(messages)
        + " A source-level finding does not establish that the rule fails on every KiCad setup."
    )


def custom_drc_layer_reference_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[PcbDruLayerCandidate, ...]:
    """Review risky display aliases and layer references absent from a board source."""
    if not is_supported_pcb_dru_kicad_version(config.kicad_version):
        return ()
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    source = source_file.local_path.read_text(encoding="utf-8")
    if "${" in source:
        return ()

    board_relative = Path(str(config.project)).with_suffix(".kicad_pcb").as_posix()
    root = root.resolve()
    board_source = source_bound_project_input(root, board_relative, "board", source_hashes)
    board_path = repo_path(root, board_relative)
    board_layers, display_aliases = _board_layer_inventory(board_path.read_text(encoding="utf-8"))
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    if digest(board_path) != board_source.source_sha256:
        raise ValueError("KiCad board changed during design-lint inspection")

    candidates: list[PcbDruLayerCandidate] = []
    for rule in native_rule_declarations(source):
        issues = tuple(
            issue
            for layer_name, location in _rule_layer_references(rule)
            if (issue := _layer_issue(layer_name, location, board_layers, display_aliases))
            is not None
        )
        if not issues:
            continue
        evidence = PcbDruLayerFindingEvidence(
            source_file=source_file,
            board_source=board_source,
            rule_name=rule.name,
            rule_ordinal=rule.ordinal,
            issues=issues,
        )
        candidates.append(
            PcbDruLayerCandidate.from_source_evidence(
                evidence,
                message=_candidate_message(issues),
            )
        )
    return tuple(candidates)
