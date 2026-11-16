"""Derive scoped Pyright targets from lint catalog ownership."""

from __future__ import annotations

from pathlib import PurePosixPath

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.hwrepo.design_lint_rule_models import DesignLintRuleMetadata
from kicad_tooling.hwrepo.design_lint_rule_types import DesignLintTheme

RULE_GATE_TYPECHECK_PATHS = (
    "kicad_tooling/ci_module_size_preflight.py",
    "kicad_tooling/ci_template_playtest.py",
    "kicad_tooling/ci_typecheck.py",
    "kicad_tooling/lint_gate_typecheck.py",
    "scripts/ci.py",
    "scripts/lint_gate_scope.py",
)

_AREA_THEMES: dict[str, frozenset[DesignLintTheme]] = {
    "component_lint": frozenset({"components"}),
    "connector_lint": frozenset({"connectors"}),
    "interface_lint": frozenset({"interfaces"}),
    "power_lint": frozenset({"power"}),
    "return_path_lint": frozenset({"returns"}),
    "schematic_lint": frozenset({"schematic"}),
    "schematic_text_lint": frozenset({"schematic"}),
    "schematic_connectivity_lint": frozenset({"schematic"}),
    "schematic_hierarchy_lint": frozenset({"schematic"}),
    "pcb_lint": frozenset({"pcb"}),
    "pcb_reference_lint": frozenset({"pcb"}),
}
_FULL_CATALOG_AREAS = frozenset({"design_lint", "catalog_lint"})
_PACKAGE_WIDE_AREAS = frozenset({"architecture", "evidence_lint", "parity_lint"})


def _implementation_paths(rule: DesignLintRuleMetadata) -> tuple[str, ...]:
    references = (*rule.implementation_refs, rule.implementation_owner)
    paths: set[str] = set()
    owner_path: str | None = None
    for reference in references:
        module, separator, function = str(reference).partition("#")
        path = module.replace(".", "/") + ".py" if module.startswith("kicad_tooling.") else module
        parsed = PurePosixPath(path)
        if parsed.suffix != ".py" or not path.startswith("kicad_tooling/"):
            continue
        if (
            not separator
            or not function
            or parsed.is_absolute()
            or ".." in parsed.parts
            or path != parsed.as_posix()
        ):
            raise ValueError(
                f"Active rule {rule.rule_id!s} has an invalid implementation reference: "
                f"{reference!r}"
            )
        paths.add(path)
        if str(reference) == rule.implementation_owner:
            owner_path = path
    if not paths or owner_path not in paths:
        raise ValueError(f"Active rule {rule.rule_id!s} has no Python implementation owner")
    return tuple(sorted(paths))


def implementation_paths_by_rule() -> dict[str, tuple[str, ...]]:
    """Return deterministic Python targets from active rules' cataloged references."""
    return {
        str(rule.rule_id): _implementation_paths(rule)
        for rule in rule_catalog(status="active").rules
    }


def typecheck_paths_for_rule(rule_id: str) -> tuple[str, ...]:
    """Return a rule's cataloged implementation files and shared gate code."""
    paths = implementation_paths_by_rule().get(rule_id)
    if not paths:
        raise ValueError(f"Lint-Rule {rule_id!r} has no cataloged implementation paths")
    return tuple(sorted(set(paths) | set(RULE_GATE_TYPECHECK_PATHS)))


def typecheck_paths_for_area(area: str) -> tuple[str, ...]:
    """Return catalog-owned targets for a focused theme area, or full-scope fallback."""
    if area == "ci_lint":
        return RULE_GATE_TYPECHECK_PATHS
    if area in _PACKAGE_WIDE_AREAS:
        return ()

    catalog = rule_catalog(status="active")
    if area in _FULL_CATALOG_AREAS:
        rules = catalog.rules
    else:
        themes = _AREA_THEMES.get(area)
        if themes is None:
            return ()
        rules = tuple(rule for rule in catalog.rules if rule.theme in themes)

    paths: set[str] = set(RULE_GATE_TYPECHECK_PATHS)
    implementations = implementation_paths_by_rule()
    for rule in rules:
        paths.update(implementations[str(rule.rule_id)])
    return tuple(sorted(paths))
