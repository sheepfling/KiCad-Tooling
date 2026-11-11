"""Source-bound review candidates for custom PCB DRC rules."""

from __future__ import annotations

import re
from pathlib import Path

from .contracts import repo_path
from .design_lint_pcb_dru_rule_candidate_evidence import (
    PcbDruConflictingSeveritiesCandidate,
    PcbDruConflictingSeveritiesFindingEvidence,
    PcbDruInputRole,
    PcbDruRuleCandidate,
    PcbDruRuleFindingEvidence,
    PcbDruRuleSeverity,
    PcbDruRuleWithoutConstraintCandidate,
    PcbDruRuleWithoutConstraintFindingEvidence,
    PcbDruTextVariableCandidate,
    PcbDruTextVariableFindingEvidence,
    SourceBoundPcbDruInput,
    SourceBoundPcbDruRuleFile,
    is_supported_pcb_dru_kicad_version,
)
from .design_lint_pcb_dru_rule_name_evidence import (
    PcbDruCasefoldRuleNameCandidate,
    PcbDruCasefoldRuleNameFindingEvidence,
    PcbDruDuplicateRuleNameCandidate,
    PcbDruDuplicateRuleNameFindingEvidence,
)
from .design_lint_types import Candidate
from .evidence import digest
from .pcb_drc_rule_parser import (
    NativeDrcRuleDeclaration,
    NativeDrcRuleWithSeverity,
    NativeIgnoredDrcRule,
    native_ignored_rules,
    native_rule_declarations,
    native_rules_with_conflicting_severities,
    native_rules_with_severity,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_TEXT_VARIABLE = re.compile(r"\$\{([^{}]+)\}")


def source_bound_rule_file(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> SourceBoundPcbDruRuleFile | None:
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return None
    root = root.resolve()
    project_file = repo_path(root, config.project)
    relative = project_file.with_suffix(".kicad_dru").relative_to(root).as_posix()
    rules_file = repo_path(root, relative)
    expected_hash = source_hashes.get(relative)
    if not rules_file.exists():
        if expected_hash is not None:
            raise ValueError("Source-bound custom DRC rules disappeared during inspection")
        return None
    if not rules_file.is_file():
        raise ValueError("Custom DRC rules path is not a regular file")
    if expected_hash is None:
        raise ValueError("Custom DRC rules are outside source-bound project inputs")
    if digest(rules_file) != expected_hash:
        raise ValueError("Custom DRC rules differ from source-bound project inputs")
    return SourceBoundPcbDruRuleFile(
        source_path=relative,
        source_sha256=expected_hash,
        project_kind=config.kind,
        kicad_version=config.kicad_version,
        local_path=rules_file,
    )


def source_bound_project_input(
    root: Path,
    relative: str,
    role: PcbDruInputRole,
    source_hashes: SourceHashInventory,
) -> SourceBoundPcbDruInput:
    source_file = repo_path(root, relative)
    expected_hash = source_hashes.get(relative)
    if expected_hash is None:
        raise ValueError(f"KiCad {role} source is outside source-bound project inputs")
    if not source_file.is_file():
        raise ValueError(f"Source-bound KiCad {role} source disappeared during inspection")
    if digest(source_file) != expected_hash:
        raise ValueError(f"KiCad {role} source differs from source-bound project inputs")
    return SourceBoundPcbDruInput(
        source_path=relative,
        source_sha256=expected_hash,
        role=role,
    )


def _rule_candidate(
    source_file: SourceBoundPcbDruRuleFile,
    rule: NativeIgnoredDrcRule | NativeDrcRuleWithSeverity,
    severity: PcbDruRuleSeverity,
    *,
    message: str,
) -> PcbDruRuleCandidate:
    source_evidence = PcbDruRuleFindingEvidence(
        source_file=source_file,
        rule=rule,
        severity=severity,
    )
    return PcbDruRuleCandidate.from_source_evidence(
        source_evidence,
        subject=f"{source_file.source_path}#rule[{rule.ordinal}] {rule.name}",
        message=message,
    )


def ignored_custom_drc_rule_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Prompt for review of each source-bound rule declaring `(severity ignore)`.

    An explicit Ignore may be intentional. Findings therefore describe the
    authored declaration and ask for review without asserting it is a defect.
    """
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    source = source_file.local_path.read_text(encoding="utf-8")
    parsed_rules = native_ignored_rules(source)
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    return tuple(
        _rule_candidate(
            source_file,
            rule,
            "ignore",
            message=(
                f"Custom DRC rule {rule.name!r} explicitly declares `(severity ignore)`; "
                "confirm that suppressing this rule is intentional."
            ),
        )
        for rule in parsed_rules
    )


def excluded_custom_drc_rule_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Prompt for review of each source-bound rule declaring `(severity exclusion)`."""
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return ()
    if not is_supported_pcb_dru_kicad_version(config.kicad_version):
        return ()
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    source = source_file.local_path.read_text(encoding="utf-8")
    excluded_rules = native_rules_with_severity(source, "exclusion")
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    return tuple(
        _rule_candidate(
            source_file,
            rule,
            "exclusion",
            message=(
                f"Custom DRC rule {rule.name!r} explicitly declares `(severity exclusion)`; "
                "confirm that excluding its matching violations is intentional."
            ),
        )
        for rule in excluded_rules
    )


def text_variable_custom_drc_rule_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Request review when source contains a KiCad substitution not evaluated here."""
    if not is_supported_pcb_dru_kicad_version(config.kicad_version):
        return ()
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    source = source_file.local_path.read_text(encoding="utf-8")
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    if "${" not in source:
        return ()
    variable_names = tuple(sorted(set(_TEXT_VARIABLE.findall(source))))
    root = root.resolve()
    project_relative = str(config.project)
    board_relative = Path(project_relative).with_suffix(".kicad_pcb").as_posix()
    project_source = source_bound_project_input(root, project_relative, "project", source_hashes)
    board_source = source_bound_project_input(root, board_relative, "board", source_hashes)
    source_evidence = PcbDruTextVariableFindingEvidence(
        source_file=source_file,
        project_source=project_source,
        board_source=board_source,
        variable_names=variable_names,
    )
    return (
        PcbDruTextVariableCandidate.from_source_evidence(
            source_evidence,
            subject=f"{source_file.source_path}#text-variable-substitution",
            message=(
                "This custom DRC source contains text-variable substitution that this audit "
                "does not evaluate. Review the resolved rules and their severity, conditions, "
                "and limits against the project's intended policy."
            ),
        ),
    )


def _rule_without_constraint_candidate(
    source_file: SourceBoundPcbDruRuleFile,
    rule: NativeDrcRuleDeclaration,
) -> PcbDruRuleWithoutConstraintCandidate:
    source_evidence = PcbDruRuleWithoutConstraintFindingEvidence(
        source_file=source_file,
        rule=rule,
    )
    return PcbDruRuleWithoutConstraintCandidate.from_source_evidence(
        source_evidence,
        subject=f"{source_file.source_path}#rule[{rule.ordinal}] {rule.name}",
        message=(
            f"Custom DRC rule {rule.name!r} has no direct constraint clauses. "
            "It may be an inert declaration; confirm this is intentional or add a "
            "specific constraint."
        ),
    )


def custom_drc_rule_without_constraint_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review source-bound named custom rules that declare no constraints."""
    if not is_supported_pcb_dru_kicad_version(config.kicad_version):
        return ()
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    source = source_file.local_path.read_text(encoding="utf-8")
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    if "${" in source:
        return ()
    rules = native_rule_declarations(source)
    return tuple(
        _rule_without_constraint_candidate(source_file, rule)
        for rule in rules
        if rule.constraint_count == 0
    )


def custom_drc_duplicate_rule_name_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review exact duplicate names in source-bound KiCad 10 custom rules."""
    if not is_supported_pcb_dru_kicad_version(config.kicad_version):
        return ()
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    source = source_file.local_path.read_text(encoding="utf-8")
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    if "${" in source:
        return ()

    name_ordinals: dict[str, list[int]] = {}
    for rule in native_rule_declarations(source):
        name_ordinals.setdefault(rule.name, []).append(rule.ordinal)

    candidates: list[Candidate] = []
    for name, ordinals in name_ordinals.items():
        if len(ordinals) < 2:
            continue
        source_evidence = PcbDruDuplicateRuleNameFindingEvidence(
            source_file=source_file,
            rule_name=name,
            rule_ordinals=tuple(ordinals),
        )
        ordinal_text = ",".join(str(ordinal) for ordinal in ordinals)
        candidates.append(
            PcbDruDuplicateRuleNameCandidate.from_source_evidence(
                source_evidence,
                subject=f"{source_file.source_path}#rules[{ordinal_text}] {name}",
                message=(
                    f"Custom DRC rule name {name!r} appears in declarations {ordinal_text}. "
                    "KiCad treats a rule name as its unique identifier in DRC reports; give each "
                    "rule a distinct name or confirm this duplicate is intentional."
                ),
            )
        )
    return tuple(candidates)


def custom_drc_casefold_rule_name_collision_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Prompt when distinct custom DRC names share the same case-folded spelling."""
    if not is_supported_pcb_dru_kicad_version(config.kicad_version):
        return ()
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    source = source_file.local_path.read_text(encoding="utf-8")
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    if "${" in source:
        return ()

    groups: dict[str, list[NativeDrcRuleDeclaration]] = {}
    for rule in native_rule_declarations(source):
        if rule.name:
            groups.setdefault(rule.name.casefold(), []).append(rule)

    candidates: list[Candidate] = []
    ordered_groups = sorted(groups.items(), key=lambda item: item[1][0].ordinal)
    for casefold_key, rules in ordered_groups:
        if len({rule.name for rule in rules}) < 2:
            continue
        rule_names = tuple(rule.name for rule in rules)
        rule_ordinals = tuple(rule.ordinal for rule in rules)
        source_evidence = PcbDruCasefoldRuleNameFindingEvidence(
            source_file=source_file,
            casefold_key=casefold_key,
            rule_names=rule_names,
            rule_ordinals=rule_ordinals,
        )
        ordinal_text = ",".join(str(ordinal) for ordinal in rule_ordinals)
        names_text = ", ".join(repr(name) for name in rule_names)
        candidates.append(
            PcbDruCasefoldRuleNameCandidate.from_source_evidence(
                source_evidence,
                subject=f"{source_file.source_path}#casefold-rules[{ordinal_text}] {casefold_key}",
                message=(
                    f"Custom DRC rule names {names_text} share the case-folded spelling "
                    f"{casefold_key!r}. Confirm that the naming distinction is intentional; "
                    "this prompt does not assert that KiCad treats the rules as duplicates."
                ),
            )
        )
    return tuple(candidates)


def custom_drc_conflicting_severity_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review source-bound named rules with conflicting direct severities."""
    if not is_supported_pcb_dru_kicad_version(config.kicad_version):
        return ()
    source_file = source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    source = source_file.local_path.read_text(encoding="utf-8")
    if digest(source_file.local_path) != source_file.source_sha256:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    if "${" in source:
        return ()

    candidates: list[Candidate] = []
    for rule in native_rules_with_conflicting_severities(source):
        source_evidence = PcbDruConflictingSeveritiesFindingEvidence(
            source_file=source_file,
            rule=rule,
        )
        severity_text = ", ".join(rule.severities)
        candidates.append(
            PcbDruConflictingSeveritiesCandidate.from_source_evidence(
                source_evidence,
                subject=f"{source_file.source_path}#rule[{rule.ordinal}] {rule.name}",
                message=(
                    f"Custom DRC rule {rule.name!r} declares conflicting severities in order "
                    f"{severity_text}. Confirm the intended severity for this KiCad version."
                ),
            )
        )
    return tuple(candidates)
