"""Source-bound review for documented deprecated custom DRC functions."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from .design_lint_pcb_dru_deprecated_function_evidence import (
    PcbDruDeprecatedFunction,
    PcbDruDeprecatedFunctionCandidate,
    PcbDruDeprecatedFunctionFindingEvidence,
    PcbDruDeprecatedFunctionUse,
)
from .design_lint_pcb_dru_rule_candidate_evidence import (
    is_supported_pcb_dru_kicad_version,
)
from .evidence import digest
from .pcb_drc_rule_parser import NativeDrcRuleDeclaration, native_rule_declarations
from .pcb_dru_rule_review import source_bound_rule_file
from .project_models import ProjectConfig
from .source_state_models import SourceHashInventory

_REPLACEMENTS: dict[str, str] = {
    "insideArea": "intersectsArea",
    "insideCourtyard": "intersectsCourtyard",
    "insideFrontCourtyard": "intersectsFrontCourtyard",
    "insideBackCourtyard": "intersectsBackCourtyard",
    "memberOf": "memberOfGroup",
}


def _deprecated_condition_function_uses(
    condition: str,
) -> tuple[PcbDruDeprecatedFunctionUse, ...]:
    """Find exact function calls outside quoted string arguments."""
    uses: list[PcbDruDeprecatedFunctionUse] = []
    index = 0
    quote: str | None = None
    while index < len(condition):
        char = condition[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if not (char.isalpha() or char == "_"):
            index += 1
            continue
        start = index
        index += 1
        while index < len(condition) and (condition[index].isalnum() or condition[index] == "_"):
            index += 1
        name = condition[start:index]
        following = index
        while following < len(condition) and condition[following].isspace():
            following += 1
        replacement = _REPLACEMENTS.get(name)
        if replacement is not None and following < len(condition) and condition[following] == "(":
            uses.append(
                PcbDruDeprecatedFunctionUse(
                    function=cast(PcbDruDeprecatedFunction, name),
                    replacement=replacement,
                    condition_offset=start,
                )
            )
    return tuple(uses)


def _rule_deprecated_functions(
    rule: NativeDrcRuleDeclaration,
) -> tuple[PcbDruDeprecatedFunctionUse, ...]:
    if rule.condition is None:
        return ()
    return _deprecated_condition_function_uses(rule.condition)


def _review_message(uses: tuple[PcbDruDeprecatedFunctionUse, ...]) -> str:
    recommendations = ", ".join(f"{use.function}() → {use.replacement}()" for use in uses)
    return (
        "Review this custom DRC condition's deprecated function calls. KiCad documents these "
        f"replacements: {recommendations}. Confirm that an update preserves the intended match."
    )


def custom_drc_deprecated_condition_function_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[PcbDruDeprecatedFunctionCandidate, ...]:
    """Review each source-bound named rule that calls a deprecated function."""
    if not is_supported_pcb_dru_kicad_version(config.kicad_version):
        return ()
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    source = source_file.local_path.read_text(encoding="utf-8")
    if "${" in source:
        return ()
    rules = native_rule_declarations(source)
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")

    candidates: list[PcbDruDeprecatedFunctionCandidate] = []
    for rule in rules:
        uses = _rule_deprecated_functions(rule)
        if not uses:
            continue
        evidence = PcbDruDeprecatedFunctionFindingEvidence(
            source_file=source_file,
            rule_name=rule.name,
            rule_ordinal=rule.ordinal,
            uses=uses,
        )
        candidates.append(
            PcbDruDeprecatedFunctionCandidate.from_source_evidence(
                evidence,
                message=_review_message(uses),
            )
        )
    return tuple(candidates)
