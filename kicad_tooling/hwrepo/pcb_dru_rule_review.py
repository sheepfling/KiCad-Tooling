"""Source-bound review candidates for explicitly ignored custom PCB rules."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from .contracts import repo_path
from .design_lint_types import Candidate
from .evidence import digest
from .models import ProjectConfig, ProjectKind
from .pcb_drc_rule_parser import native_ignored_rules, native_rules_with_severity

_SUPPORTED_KICAD_VERSION = re.compile(r"10\.\d+\.\d+\Z")


def _source_bound_rule_file(
    root: Path,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[str, Path, str] | None:
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
    return relative, rules_file, expected_hash


def ignored_custom_drc_rule_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[Candidate, ...]:
    """Prompt for review of each source-bound rule declaring `(severity ignore)`.

    An explicit Ignore may be intentional. Findings therefore describe the
    authored declaration and ask for review without asserting it is a defect.
    """
    source_file = _source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    relative, rules_file, expected_hash = source_file
    source = rules_file.read_text(encoding="utf-8")
    ignored_rules = native_ignored_rules(source)
    if digest(rules_file) != expected_hash:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    return tuple(
        Candidate(
            rule_id="pcb.custom_drc_rule_ignored",
            subject=f"{relative}#rule[{rule.ordinal}] {rule.name}",
            message=(
                f"Custom DRC rule {rule.name!r} explicitly declares `(severity ignore)`; "
                "confirm that suppressing this rule is intentional."
            ),
            evidence={
                "source_path": (relative,),
                "source_sha256": (expected_hash,),
                "kicad_version": (config.kicad_version,),
                "rule_name": (rule.name,),
                "rule_ordinal": (str(rule.ordinal),),
            },
        )
        for rule in ignored_rules
    )


def excluded_custom_drc_rule_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[Candidate, ...]:
    """Prompt for review of each source-bound rule declaring `(severity exclusion)`."""
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return ()
    if _SUPPORTED_KICAD_VERSION.fullmatch(config.kicad_version) is None:
        return ()
    source_file = _source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    relative, rules_file, expected_hash = source_file
    source = rules_file.read_text(encoding="utf-8")
    excluded_rules = native_rules_with_severity(source, "exclusion")
    if digest(rules_file) != expected_hash:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    return tuple(
        Candidate(
            rule_id="pcb.custom_drc_rule_excluded",
            subject=f"{relative}#rule[{rule.ordinal}] {rule.name}",
            message=(
                f"Custom DRC rule {rule.name!r} explicitly declares `(severity exclusion)`; "
                "confirm that excluding its matching violations is intentional."
            ),
            evidence={
                "source_path": (relative,),
                "source_sha256": (expected_hash,),
                "kicad_version": (config.kicad_version,),
                "rule_name": (rule.name,),
                "rule_ordinal": (str(rule.ordinal),),
                "severity": (rule.severity,),
            },
        )
        for rule in excluded_rules
    )


def text_variable_custom_drc_rule_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[Candidate, ...]:
    """Request review when source contains a KiCad substitution not evaluated here."""
    if _SUPPORTED_KICAD_VERSION.fullmatch(config.kicad_version) is None:
        return ()
    source_file = _source_bound_rule_file(root, config, source_hashes)
    if source_file is None:
        return ()
    relative, rules_file, expected_hash = source_file
    source = rules_file.read_text(encoding="utf-8")
    if digest(rules_file) != expected_hash:
        raise ValueError("Custom DRC rules changed during design-lint inspection")
    if "${" not in source:
        return ()
    return (
        Candidate(
            rule_id="pcb.custom_drc_text_variable_review",
            subject=f"{relative}#text-variable-substitution",
            message=(
                "This custom DRC source contains text-variable substitution that this audit "
                "does not evaluate. Review the resolved rules and their severity, conditions, "
                "and limits against the project's intended policy."
            ),
            evidence={
                "source_path": (relative,),
                "source_sha256": (expected_hash,),
                "kicad_version": (config.kicad_version,),
            },
        ),
    )
