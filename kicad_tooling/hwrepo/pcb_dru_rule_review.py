"""Source-bound review candidates for explicitly ignored custom PCB rules."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .contracts import repo_path
from .design_lint_types import Candidate
from .evidence import digest
from .models import ProjectConfig, ProjectKind
from .pcb_drc_rule_parser import native_ignored_rules


def ignored_custom_drc_rule_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: Mapping[str, str],
) -> tuple[Candidate, ...]:
    """Prompt for review of each source-bound rule declaring `(severity ignore)`.

    An explicit Ignore may be intentional. Findings therefore describe the
    authored declaration and ask for review without asserting it is a defect.
    """
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return ()
    root = root.resolve()
    project_file = repo_path(root, config.project)
    relative = project_file.with_suffix(".kicad_dru").relative_to(root).as_posix()
    rules_file = repo_path(root, relative)
    expected_hash = source_hashes.get(relative)
    if not rules_file.exists():
        if expected_hash is not None:
            raise ValueError("Source-bound custom DRC rules disappeared during inspection")
        return ()
    if not rules_file.is_file():
        raise ValueError("Custom DRC rules path is not a regular file")
    if expected_hash is None:
        raise ValueError("Custom DRC rules are outside source-bound project inputs")
    if digest(rules_file) != expected_hash:
        raise ValueError("Custom DRC rules differ from source-bound project inputs")
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
