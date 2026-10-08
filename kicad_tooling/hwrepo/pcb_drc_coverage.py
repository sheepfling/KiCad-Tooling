"""Audit project-authored differential-pair requirements against native DRC rules."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, cast

from ..validate import hashes
from .contracts import read_model, repo_path
from .evidence import digest
from .model_inventory import _atoms, _children, _Span  # pyright: ignore[reportPrivateUsage]
from .models import (
    CommandEvidence,
    NetlistContract,
    PcbDifferentialPairRuleCoverageEntry,
    PcbDifferentialPairRuleCoverageReport,
    PcbDifferentialPairRuleMap,
    PcbDrcConstraintCoverage,
    PcbDrcConstraintName,
    PcbDrcMaximumRequirement,
    PcbDrcMinMaxRequirement,
    ProjectConfig,
    ValidationSummary,
)

_RULE_SEVERITY = {
    "track_width": "track_width",
    "diff_pair_gap": "diff_pair_gap_out_of_range",
    "skew": "skew_out_of_range",
    "diff_pair_uncoupled": "diff_pair_uncoupled_length_too_long",
}
_LENGTH = re.compile(r"^([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))(mm|mil)$")


class _NativeRuleConstraint:
    def __init__(
        self,
        rule_name: str,
        condition: str,
        name: PcbDrcConstraintName,
        minimum_nm: int | None,
        maximum_nm: int | None,
        issue: str | None,
    ) -> None:
        self.rule_name = rule_name
        self.condition = condition
        self.name = name
        self.minimum_nm = minimum_nm
        self.maximum_nm = maximum_nm
        self.issue = issue


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
) -> _NativeRuleConstraint | None:
    atoms = _atoms(source, span)
    if len(atoms) != 2 or atoms[1] not in _RULE_SEVERITY:
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
    return _NativeRuleConstraint(
        rule_name,
        condition,
        cast(PcbDrcConstraintName, name),
        fields.get("min"),
        fields.get("max"),
        issue,
    )


def _native_constraints(source: str) -> tuple[_NativeRuleConstraint, ...]:
    if not source.strip():
        return ()
    nodes = _children(source, 0, len(source))
    versions = [_atoms(source, node) for node in nodes if _atoms(source, node)[:1] == ("version",)]
    if len(versions) != 1 or versions[0] != ("version", "1"):
        raise ValueError("Expected one version 1 root atom in the native DRC rules file")
    result: list[_NativeRuleConstraint] = []
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
        for node in children:
            if _atoms(source, node)[:1] != ("constraint",):
                continue
            parsed = _parse_constraint(source, header[1], condition_atoms[1], node)
            if parsed is not None:
                result.append(parsed)
    return tuple(result)


def _expected(
    name: PcbDrcConstraintName,
    bounds: PcbDrcMinMaxRequirement | PcbDrcMaximumRequirement,
) -> tuple[int | None, int | None]:
    if isinstance(bounds, PcbDrcMaximumRequirement):
        return None, bounds.max_nm
    return bounds.min_nm, bounds.max_nm


def _recognized_pair_names(positive: str, negative: str, selector: str) -> bool:
    if positive.endswith("_P") and negative == positive[:-1] + "N":
        return selector == positive[:-1] and negative.startswith(selector)
    if positive.endswith("+") and negative == positive[:-1] + "-":
        return selector == positive[:-1] and negative.startswith(selector)
    return False


def compare_native_rules(
    requirements: PcbDifferentialPairRuleMap,
    rules_source: str,
    ignored_checks: frozenset[str],
) -> tuple[PcbDifferentialPairRuleCoverageEntry, ...]:
    """Compare exact supported `inDiffPair` rules; do not calculate PCB geometry."""
    native = _native_constraints(rules_source)
    entries: list[PcbDifferentialPairRuleCoverageEntry] = []
    for requirement in requirements.requirements:
        condition = f"A.inDiffPair('{requirement.pair_selector}')"
        constraints: list[PcbDrcConstraintCoverage] = []
        expected_fields: tuple[
            tuple[
                PcbDrcConstraintName,
                PcbDrcMinMaxRequirement | PcbDrcMaximumRequirement | None,
            ],
            ...,
        ] = (
            ("track_width", requirement.track_width),
            ("diff_pair_gap", requirement.diff_pair_gap),
            ("skew", requirement.skew),
            ("diff_pair_uncoupled", requirement.uncoupled_length),
        )
        entry_issues: list[str] = []
        if not _recognized_pair_names(
            requirement.positive_net, requirement.negative_net, requirement.pair_selector
        ):
            entry_issues.append(
                "The net names do not use a supported KiCad differential-pair suffix pattern."
            )
        for raw_name, bounds in expected_fields:
            if bounds is None:
                continue
            name = raw_name
            expected_minimum, expected_maximum = _expected(name, bounds)
            matches = tuple(
                item for item in native if item.condition == condition and item.name == name
            )
            severity = _RULE_SEVERITY[name]
            if severity in ignored_checks:
                constraints.append(
                    PcbDrcConstraintCoverage(
                        constraint=name,
                        status="IGNORED",
                        expected_min_nm=expected_minimum,
                        expected_max_nm=expected_maximum,
                        observed_min_nm=matches[0].minimum_nm if len(matches) == 1 else None,
                        observed_max_nm=matches[0].maximum_nm if len(matches) == 1 else None,
                        rule_names=tuple(sorted({item.rule_name for item in matches})),
                        issue=f"Native DRC severity {severity!r} is Ignore.",
                    )
                )
                continue
            if not matches:
                constraints.append(
                    PcbDrcConstraintCoverage(
                        constraint=name,
                        status="MISSING",
                        expected_min_nm=expected_minimum,
                        expected_max_nm=expected_maximum,
                        issue=f"No rule has exact condition {condition!r} and constraint {name!r}.",
                    )
                )
                continue
            if len(matches) != 1:
                constraints.append(
                    PcbDrcConstraintCoverage(
                        constraint=name,
                        status="AMBIGUOUS",
                        expected_min_nm=expected_minimum,
                        expected_max_nm=expected_maximum,
                        rule_names=tuple(sorted({item.rule_name for item in matches})),
                        issue="Multiple matching native rules make coverage ambiguous.",
                    )
                )
                continue
            match = matches[0]
            if match.issue is not None:
                constraints.append(
                    PcbDrcConstraintCoverage(
                        constraint=name,
                        status="UNSUPPORTED",
                        expected_min_nm=expected_minimum,
                        expected_max_nm=expected_maximum,
                        rule_names=(match.rule_name,),
                        issue=match.issue,
                    )
                )
                continue
            covered = match.minimum_nm == expected_minimum and match.maximum_nm == expected_maximum
            constraints.append(
                PcbDrcConstraintCoverage(
                    constraint=name,
                    status="COVERED" if covered else "MISMATCH",
                    expected_min_nm=expected_minimum,
                    expected_max_nm=expected_maximum,
                    observed_min_nm=match.minimum_nm,
                    observed_max_nm=match.maximum_nm,
                    rule_names=(match.rule_name,),
                    issue=None
                    if covered
                    else "Native rule bounds differ from the authored requirement.",
                )
            )
        complete = not entry_issues and all(item.status == "COVERED" for item in constraints)
        entries.append(
            PcbDifferentialPairRuleCoverageEntry(
                id=requirement.id,
                basis=requirement.basis,
                positive_net=requirement.positive_net,
                negative_net=requirement.negative_net,
                pair_selector=requirement.pair_selector,
                status="COMPLETE" if complete else "INCOMPLETE",
                constraints=tuple(constraints),
                issues=tuple(entry_issues),
            )
        )
    return tuple(entries)


def scan_source_bound_rule_map(
    root: Path,
    config: ProjectConfig,
    requirements: PcbDifferentialPairRuleMap,
    observed: NetlistContract,
    source_hashes: dict[str, str],
    native_summary: Path,
    mode: Literal["review", "block", "off"],
) -> PcbDifferentialPairRuleCoverageReport:
    """Read exact KiCad DRC inputs and bind coverage to the native receipt."""
    root = root.resolve()
    requirement_hash = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    if mode == "off":
        return PcbDifferentialPairRuleCoverageReport(
            status="DISABLED", mode="off", map_sha256=requirement_hash
        )
    base = repo_path(root, config.project)
    project_file = base
    board_file = base.with_suffix(".kicad_pcb")
    rules_file = base.with_suffix(".kicad_dru")
    project_relative = project_file.relative_to(root).as_posix()
    board_relative = board_file.relative_to(root).as_posix()
    rules_relative = rules_file.relative_to(root).as_posix()
    project_hash = source_hashes.get(project_relative)
    board_hash = source_hashes.get(board_relative)
    if project_hash is None or board_hash is None:
        raise ValueError("Project settings or authoritative PCB is outside source-bound inputs")
    if digest(project_file) != project_hash or digest(board_file) != board_hash:
        raise ValueError("Project settings or board differs from source-bound evidence")
    if rules_file.exists():
        rules_hash = source_hashes.get(rules_relative)
        if rules_hash is None or digest(rules_file) != rules_hash:
            raise ValueError("Native DRC rules are outside or differ from source-bound inputs")
        rules_source = rules_file.read_text(encoding="utf-8")
    else:
        rules_hash = None
        rules_source = ""

    summary_file = native_summary / "summary.json" if native_summary.is_dir() else native_summary
    summary_file = summary_file.resolve()
    try:
        summary_relative = summary_file.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Native summary is outside the current repository") from exc
    summary_hash_before = digest(summary_file)
    summary = read_model(summary_file, ValidationSummary)
    drc_relative = "drc.json"
    command_relative = "drc.command.json"
    if not {drc_relative, command_relative} <= summary.artifacts_sha256.keys():
        raise ValueError("Native summary does not bind both the DRC report and command")
    drc_file = summary_file.parent / drc_relative
    command_file = summary_file.parent / command_relative
    if digest(drc_file) != summary.artifacts_sha256[drc_relative]:
        raise ValueError("Native DRC report differs from its summary artifact hash")
    if digest(command_file) != summary.artifacts_sha256[command_relative]:
        raise ValueError("Native DRC command differs from its summary artifact hash")
    drc_command = read_model(command_file, CommandEvidence)
    if drc_command.error is not None or drc_command.returncode not in {0, 5}:
        raise ValueError("Native DRC command did not complete with a recognized result")
    argv = drc_command.argv
    if (
        not any(argv[index : index + 2] == ("pcb", "drc") for index in range(len(argv) - 1))
        or not any(
            argv[index : index + 2] == ("--format", "json") for index in range(len(argv) - 1)
        )
        or "--severity-all" not in argv
    ):
        raise ValueError("Native DRC command evidence does not record a JSON all-severity PCB DRC")
    try:
        output_index = argv.index("--output")
        output_argument = argv[output_index + 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("Native DRC command evidence has no report output path") from exc
    output_path = Path(output_argument)
    if not output_path.is_absolute():
        output_path = root / output_path
    board_argument = Path(argv[-1])
    if not board_argument.is_absolute():
        board_argument = root / board_argument
    if (
        output_path.resolve() != drc_file.resolve()
        or board_argument.resolve() != board_file.resolve()
    ):
        raise ValueError(
            "Native DRC command does not bind the current report and authoritative board"
        )
    check = summary.checks.get("drc")
    if check is None or check.status == "NOT_RUN" or check.returncode not in {0, 5}:
        raise ValueError("Native summary does not record a completed PCB DRC check")
    raw_drc_payload: object = json.loads(drc_file.read_text(encoding="utf-8"))
    if not isinstance(raw_drc_payload, dict):
        raise TypeError("Native DRC report root must be a JSON object")
    drc_payload = cast(dict[str, object], raw_drc_payload)
    if drc_payload.get("kicad_version") != config.kicad_version:
        raise ValueError("Native DRC report version differs from the selected project version")
    source = drc_payload.get("source")
    if (
        not isinstance(source, str)
        or source.replace("\\", "/").rsplit("/", 1)[-1] != board_file.name
    ):
        raise ValueError("Native DRC report does not name the authoritative PCB")
    raw_ignored_rows = drc_payload.get("ignored_checks")
    if not isinstance(raw_ignored_rows, list):
        raise TypeError("Native DRC report does not include ignored-check evidence")
    ignored_rows = cast(list[object], raw_ignored_rows)
    ignored: set[str] = set()
    for raw_row in ignored_rows:
        if not isinstance(raw_row, dict):
            raise TypeError("Native DRC report has malformed ignored-check evidence")
        row = cast(dict[str, object], raw_row)
        key = row.get("key")
        if not isinstance(key, str):
            raise TypeError("Native DRC report has malformed ignored-check evidence")
        ignored.add(key)

    entries = compare_native_rules(requirements, rules_source, frozenset(ignored))
    net_names = set(observed.nets)
    checked: list[PcbDifferentialPairRuleCoverageEntry] = []
    for entry in entries:
        missing = tuple(
            net for net in (entry.positive_net, entry.negative_net) if net not in net_names
        )
        if missing:
            issues = (
                *entry.issues,
                f"Mapped pair net(s) absent from the source-bound netlist: {', '.join(missing)}.",
            )
            entry = entry.model_copy(update={"status": "INCOMPLETE", "issues": issues})
        checked.append(entry)
    entries = tuple(checked)
    if hashes(root, config.source_roots) != source_hashes:
        raise ValueError("Declared source changed while checking native DRC rule coverage")
    if digest(summary_file) != summary_hash_before:
        raise ValueError("Native summary changed while checking DRC rule coverage")
    inventory = hashlib.sha256(
        "\n".join(f"{name}\0{value}" for name, value in sorted(source_hashes.items())).encode(
            "utf-8"
        )
    ).hexdigest()
    return PcbDifferentialPairRuleCoverageReport(
        status="COMPLETE" if all(item.status == "COMPLETE" for item in entries) else "INCOMPLETE",
        mode=mode,
        map_sha256=requirement_hash,
        source_inventory_sha256=inventory,
        project_path=project_relative,
        project_sha256=project_hash,
        rules_path=rules_relative,
        rules_sha256=rules_hash,
        board_path=board_relative,
        board_sha256=board_hash,
        native_summary_path=summary_relative,
        native_summary_sha256=digest(summary_file),
        native_drc_path=(summary_file.parent / drc_relative).relative_to(root).as_posix(),
        native_drc_sha256=digest(drc_file),
        kicad_version=config.kicad_version,
        image=config.image,
        entries=entries,
    )
