"""Parse the supported native KiCad DRC rule and report formats."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from .model_inventory import _atoms, _children, _Span  # pyright: ignore[reportPrivateUsage]
from .pcb_drc_models import PcbDrcConstraintName

RULE_SEVERITY = {
    "track_width": "track_width",
    "diff_pair_gap": "diff_pair_gap_out_of_range",
    "skew": "skew_out_of_range",
    "diff_pair_uncoupled": "diff_pair_uncoupled_length_too_long",
    "length": "length_out_of_range",
}
_LENGTH = re.compile(r"^([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))(mm|mil)$")


class NativeRuleConstraint:
    def __init__(
        self,
        rule_name: str,
        condition: str,
        name: PcbDrcConstraintName,
        minimum_nm: int | None,
        maximum_nm: int | None,
        issue: str | None,
        severity: str | None,
        severity_issue: str | None,
    ) -> None:
        self.rule_name = rule_name
        self.condition = condition
        self.name = name
        self.minimum_nm = minimum_nm
        self.maximum_nm = maximum_nm
        self.issue = issue
        self.severity = severity
        self.severity_issue = severity_issue


@dataclass(frozen=True, slots=True)
class NativePcbDrcFixtureReport:
    """Typed native DRC fields consumed by deterministic fixture lanes."""

    kicad_version: str
    source: str
    violation_types: tuple[str, ...]
    violation_records_sha256: str


def _length_nm(value: str) -> int:
    match = _LENGTH.fullmatch(value)
    if match is None:
        raise ValueError(f"Unsupported native DRC length literal {value!r}; use mm or mil")
    try:
        amount = Decimal(match.group(1))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid native DRC length literal {value!r}") from exc
    scale = Decimal(1_000_000) if match.group(2) == "mm" else Decimal(25_400)
    result = amount * scale
    if result != result.to_integral_value():
        raise ValueError(f"Native DRC length {value!r} is not an integer nanometer value")
    if result <= 0:
        raise ValueError(f"Native DRC length {value!r} must be positive")
    return int(result)


def _parse_constraint(
    source: str,
    rule_name: str,
    condition: str,
    span: _Span,
    severity: str | None,
    severity_issue: str | None,
) -> NativeRuleConstraint | None:
    atoms = _atoms(source, span)
    if len(atoms) != 2 or atoms[1] not in RULE_SEVERITY:
        return None
    name = atoms[1]
    fields: dict[str, int] = {}
    issue: str | None = None
    for child in _children(source, span.start + 1, span.end - 1):
        values = _atoms(source, child)
        if not values or values[0] == "opt":
            continue
        if values[0] not in {"min", "max"} or len(values) != 2:
            issue = f"Unsupported bound expression in rule {rule_name!r}"
            continue
        if values[0] in fields:
            issue = f"Repeated {values[0]} bound in rule {rule_name!r}"
            continue
        try:
            fields[values[0]] = _length_nm(values[1])
        except ValueError as exc:
            issue = str(exc)
    if not fields and issue is None:
        issue = f"Rule {rule_name!r} has no explicit min/max bound"
    return NativeRuleConstraint(
        rule_name,
        condition,
        cast(PcbDrcConstraintName, name),
        fields.get("min"),
        fields.get("max"),
        issue,
        severity,
        severity_issue,
    )


def native_constraints(source: str) -> tuple[NativeRuleConstraint, ...]:
    if not source.strip():
        return ()
    nodes = _children(source, 0, len(source))
    versions = [_atoms(source, node) for node in nodes if _atoms(source, node)[:1] == ("version",)]
    if len(versions) != 1 or versions[0] != ("version", "1"):
        raise ValueError("Expected one version 1 root atom in the native DRC rules file")
    result: list[NativeRuleConstraint] = []
    for rule in nodes:
        header = _atoms(source, rule)
        if not header or header[0] != "rule":
            continue
        if len(header) != 2:
            raise ValueError("Malformed named rule in the native DRC rules file")
        children = _children(source, rule.start + 1, rule.end - 1)
        conditions = [node for node in children if _atoms(source, node)[:1] == ("condition",)]
        if len(conditions) != 1:
            continue
        condition_atoms = _atoms(source, conditions[0])
        if len(condition_atoms) != 2:
            continue
        severity_clauses = [node for node in children if _atoms(source, node)[:1] == ("severity",)]
        severity: str | None = None
        severity_issue: str | None = None
        if len(severity_clauses) > 1:
            severity_issue = "Native rule has multiple severity clauses."
        elif severity_clauses:
            severity_atoms = _atoms(source, severity_clauses[0])
            if len(severity_atoms) != 2 or severity_atoms[1] not in {
                "error",
                "warning",
                "ignore",
                "exclusion",
            }:
                severity_issue = (
                    "Unsupported native rule severity clause; expected error, warning, ignore, "
                    "or exclusion."
                )
            else:
                severity = severity_atoms[1]
        for node in children:
            if _atoms(source, node)[:1] != ("constraint",):
                continue
            parsed = _parse_constraint(
                source,
                header[1],
                condition_atoms[1],
                node,
                severity,
                severity_issue,
            )
            if parsed is not None:
                result.append(parsed)
    return tuple(result)


def drc_pad_selector(pad: str) -> str:
    reference, pad_number = pad.split(".", 1)
    return f"{reference}-{pad_number}"


def read_native_pcb_drc_fixture_report(path: Path) -> NativePcbDrcFixtureReport:
    """Validate the DRC report fields needed by native signal-path fixtures."""
    raw_payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_payload, dict):
        raise TypeError(f"{path}: native DRC report root must be an object")
    payload = cast(dict[str, object], raw_payload)
    version = payload.get("kicad_version")
    source = payload.get("source")
    violations = payload.get("violations")
    if not isinstance(version, str) or not version.strip():
        raise TypeError(f"{path}: native DRC report has no KiCad version")
    if not isinstance(source, str) or not source.strip():
        raise TypeError(f"{path}: native DRC report has no source board")
    if not isinstance(violations, list):
        raise TypeError(f"{path}: native DRC violations must be a list")
    violation_types: list[str] = []
    canonical_violations: list[str] = []
    for index, raw_item in enumerate(cast(list[object], violations)):
        if not isinstance(raw_item, dict):
            raise TypeError(f"{path}: native DRC violation {index} must be an object")
        item = cast(dict[str, object], raw_item)
        violation_type = item.get("type")
        if not isinstance(violation_type, str) or not violation_type.strip():
            raise TypeError(f"{path}: native DRC violation {index} has no type")
        violation_types.append(violation_type)
        canonical_violations.append(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
    violation_payload = json.dumps(
        sorted(canonical_violations), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return NativePcbDrcFixtureReport(
        kicad_version=version,
        source=source,
        violation_types=tuple(sorted(violation_types)),
        violation_records_sha256=hashlib.sha256(violation_payload).hexdigest(),
    )
