"""Source structure for named KiCad PCB custom DRC rules."""

from __future__ import annotations

from dataclasses import dataclass

from .kicad_sexpr import SExprSpan as _Span
from .kicad_sexpr import sexpr_atoms as _atoms
from .kicad_sexpr import sexpr_children as _children


@dataclass(frozen=True, slots=True)
class NativeDrcRuleDeclaration:
    """Direct source structure for one named version-1 custom DRC rule."""

    name: str
    ordinal: int
    constraint_count: int
    condition: str | None
    layers: tuple[str, ...] = ()
    condition_issue: str | None = None
    constraint_types: tuple[str | None, ...] = ()
    constraint_disallow_object_types: tuple[tuple[str, ...] | None, ...] = ()


@dataclass(frozen=True, slots=True)
class _NativeNamedRule:
    name: str
    ordinal: int
    children: tuple[_Span, ...]


def _native_named_rules(source: str) -> tuple[_NativeNamedRule, ...]:
    """Parse the canonical named-rule inventory for version-1 custom rules."""
    if not source.strip():
        return ()
    nodes = _children(source, 0, len(source))
    versions = [_atoms(source, node) for node in nodes if _atoms(source, node)[:1] == ("version",)]
    if len(versions) != 1 or versions[0] != ("version", "1"):
        raise ValueError("Expected one version 1 root atom in the native DRC rules file")
    rules: list[_NativeNamedRule] = []
    ordinal = 0
    for node in nodes:
        header = _atoms(source, node)
        if not header or header[0] != "rule":
            continue
        ordinal += 1
        if len(header) != 2:
            raise ValueError("Malformed named rule in the native DRC rules file")
        children = _children(source, node.start + 1, node.end - 1)
        rules.append(_NativeNamedRule(header[1], ordinal, children))
    return tuple(rules)


def native_rule_declarations(source: str) -> tuple[NativeDrcRuleDeclaration, ...]:
    """Return direct rule clauses without expanding variables or conditions."""
    result: list[NativeDrcRuleDeclaration] = []
    for rule in _native_named_rules(source):
        conditions = [
            child for child in rule.children if _atoms(source, child)[:1] == ("condition",)
        ]
        condition: str | None = None
        condition_issue: str | None = None
        if len(conditions) == 1:
            atoms = _atoms(source, conditions[0])
            if len(atoms) == 2:
                condition = atoms[1]
            else:
                expression_count = max(0, len(atoms) - 1)
                condition_issue = (
                    "Direct condition clause has "
                    f"{expression_count} expression values; expected exactly one."
                )
        constraints = tuple(
            atoms
            for child in rule.children
            if (atoms := _atoms(source, child))[:1] == ("constraint",)
        )
        layers = tuple(
            atoms[1]
            for child in rule.children
            if (atoms := _atoms(source, child))[:1] == ("layer",) and len(atoms) == 2
        )
        result.append(
            NativeDrcRuleDeclaration(
                name=rule.name,
                ordinal=rule.ordinal,
                constraint_count=len(constraints),
                condition=condition,
                layers=layers,
                condition_issue=condition_issue,
                constraint_types=tuple(
                    atoms[1] if len(atoms) > 1 else None for atoms in constraints
                ),
                constraint_disallow_object_types=tuple(
                    atoms[2:] if len(atoms) > 1 and atoms[1] == "disallow" else None
                    for atoms in constraints
                ),
            )
        )
    return tuple(result)
