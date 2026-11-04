"""Source-bound review candidates for custom PCB DRC rules."""

from __future__ import annotations

import re
from pathlib import Path

from .contracts import repo_path
from .design_lint_pcb_dru_rule_candidate_evidence import (
    PcbDruInputRole,
    PcbDruRuleCandidate,
    PcbDruRuleFindingEvidence,
    PcbDruRuleSeverity,
    PcbDruTextVariableCandidate,
    PcbDruTextVariableFindingEvidence,
    SourceBoundPcbDruInput,
    SourceBoundPcbDruRuleFile,
    is_supported_pcb_dru_kicad_version,
)
from .design_lint_types import Candidate
from .evidence import digest
from .pcb_drc_rule_parser import (
    NativeDrcRuleWithSeverity,
    NativeIgnoredDrcRule,
    native_ignored_rules,
    native_rules_with_severity,
)
from .project_models import ProjectConfig, ProjectKind
from .source_state_models import SourceHashInventory

_TEXT_VARIABLE = re.compile(r"\$\{([^{}]+)\}")


def _source_bound_rule_file(
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


def _source_bound_project_input(
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
    source_file = _source_bound_rule_file(root, config, source_hashes)
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
    source_file = _source_bound_rule_file(root, config, source_hashes)
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
    source_file = _source_bound_rule_file(root, config, source_hashes)
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
    project_source = _source_bound_project_input(root, project_relative, "project", source_hashes)
    board_source = _source_bound_project_input(root, board_relative, "board", source_hashes)
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
