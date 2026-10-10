"""Compare authored PCB DRC requirements with parsed native rule definitions."""

from __future__ import annotations

from fnmatch import fnmatchcase

from .models import (
    NetlistContract,
    PcbConnectivitySnapshot,
)
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageEntry,
    PcbDifferentialPairRuleMap,
    PcbDrcConstraintCoverage,
    PcbDrcConstraintName,
    PcbDrcMaximumRequirement,
    PcbDrcMinMaxRequirement,
    PcbSignalPathRequirement,
    PcbSignalPathRuleCoverageEntry,
    PcbSignalPathRuleMap,
)
from .pcb_drc_rule_parser import (
    RULE_SEVERITY,
    NativeRuleConstraint,
    drc_pad_selector,
    native_constraints,
)


def _expected(
    name: PcbDrcConstraintName,
    bounds: PcbDrcMinMaxRequirement | PcbDrcMaximumRequirement,
) -> tuple[int | None, int | None]:
    if isinstance(bounds, PcbDrcMaximumRequirement):
        return None, bounds.max_nm
    return bounds.min_nm, bounds.max_nm


def _compare_constraint(
    condition: str,
    name: PcbDrcConstraintName,
    bounds: PcbDrcMinMaxRequirement | PcbDrcMaximumRequirement,
    native: tuple[NativeRuleConstraint, ...],
    ignored_checks: frozenset[str],
) -> PcbDrcConstraintCoverage:
    expected_minimum, expected_maximum = _expected(name, bounds)
    matches = tuple(item for item in native if item.condition == condition and item.name == name)
    severity = RULE_SEVERITY[name]
    if severity in ignored_checks:
        return PcbDrcConstraintCoverage(
            constraint=name,
            status="IGNORED",
            expected_min_nm=expected_minimum,
            expected_max_nm=expected_maximum,
            observed_min_nm=matches[0].minimum_nm if len(matches) == 1 else None,
            observed_max_nm=matches[0].maximum_nm if len(matches) == 1 else None,
            rule_names=tuple(sorted({item.rule_name for item in matches})),
            issue=f"Native DRC severity {severity!r} is Ignore.",
        )
    if not matches:
        return PcbDrcConstraintCoverage(
            constraint=name,
            status="MISSING",
            expected_min_nm=expected_minimum,
            expected_max_nm=expected_maximum,
            issue=f"No rule has exact condition {condition!r} and constraint {name!r}.",
        )
    if len(matches) != 1:
        return PcbDrcConstraintCoverage(
            constraint=name,
            status="AMBIGUOUS",
            expected_min_nm=expected_minimum,
            expected_max_nm=expected_maximum,
            rule_names=tuple(sorted({item.rule_name for item in matches})),
            issue="Multiple matching native rules make coverage ambiguous.",
        )
    match = matches[0]
    if match.severity_issue is not None:
        return PcbDrcConstraintCoverage(
            constraint=name,
            status="UNSUPPORTED",
            expected_min_nm=expected_minimum,
            expected_max_nm=expected_maximum,
            rule_names=(match.rule_name,),
            issue=match.severity_issue,
        )
    if match.severity == "ignore":
        return PcbDrcConstraintCoverage(
            constraint=name,
            status="IGNORED",
            expected_min_nm=expected_minimum,
            expected_max_nm=expected_maximum,
            observed_min_nm=match.minimum_nm,
            observed_max_nm=match.maximum_nm,
            rule_names=(match.rule_name,),
            issue=f"Native custom-rule severity is 'ignore' for rule {match.rule_name!r}.",
        )
    if match.issue is not None:
        return PcbDrcConstraintCoverage(
            constraint=name,
            status="UNSUPPORTED",
            expected_min_nm=expected_minimum,
            expected_max_nm=expected_maximum,
            rule_names=(match.rule_name,),
            issue=match.issue,
        )
    covered = match.minimum_nm == expected_minimum and match.maximum_nm == expected_maximum
    return PcbDrcConstraintCoverage(
        constraint=name,
        status="COVERED" if covered else "MISMATCH",
        expected_min_nm=expected_minimum,
        expected_max_nm=expected_maximum,
        observed_min_nm=match.minimum_nm,
        observed_max_nm=match.maximum_nm,
        rule_names=(match.rule_name,),
        issue=None if covered else "Native rule bounds differ from the authored requirement.",
    )


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
    native = native_constraints(rules_source)
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
            constraints.append(_compare_constraint(condition, name, bounds, native, ignored_checks))
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


def compare_native_signal_path_rules(
    requirements: PcbSignalPathRuleMap,
    rules_source: str,
    ignored_checks: frozenset[str],
    observed: NetlistContract,
    snapshot: PcbConnectivitySnapshot,
) -> tuple[PcbSignalPathRuleCoverageEntry, ...]:
    """Audit exact native `fromTo` rules and verify their pads against source evidence."""
    native = native_constraints(rules_source)
    source_nets = {name.casefold(): pins for name, pins in observed.nets.items()}
    pads = {item.pad.casefold(): item for item in snapshot.pads}
    paths = {item.id.casefold(): item for item in requirements.paths}

    def endpoint_issues(path: PcbSignalPathRequirement) -> tuple[str, ...]:
        issues: list[str] = []
        source = pads.get(path.from_pad.casefold())
        destination = pads.get(path.to_pad.casefold())
        net_pins = {pin.casefold() for pin in source_nets.get(path.net.casefold(), ())}
        if path.net.casefold() not in source_nets:
            issues.append(f"Mapped net {path.net!r} is absent from the source-bound netlist.")
        for pad_ref in (path.from_pad, path.to_pad):
            if pad_ref.casefold() not in net_pins:
                issues.append(
                    f"Mapped pad {pad_ref!r} is absent from source-bound net {path.net!r}."
                )
        for label, endpoint in (("from", source), ("to", destination)):
            pad_ref = path.from_pad if label == "from" else path.to_pad
            if endpoint is None:
                issues.append(f"Mapped {label}-pad {pad_ref!r} is absent from the native PCB.")
                continue
            if endpoint.dnp:
                issues.append(f"Mapped {label}-pad {pad_ref!r} belongs to a DNP footprint.")
            if endpoint.net is None or endpoint.net.casefold() != path.net.casefold():
                issues.append(
                    f"Mapped {label}-pad {pad_ref!r} is not assigned to net {path.net!r} on the PCB."
                )
        if source is not None and destination is not None:
            source_component = {item.casefold() for item in source.connected_pads}
            destination_component = {item.casefold() for item in destination.connected_pads}
            if (
                path.to_pad.casefold() not in source_component
                or path.from_pad.casefold() not in destination_component
            ):
                issues.append("Mapped endpoint pads are not in the same native copper component.")
        return tuple(issues)

    entries: list[PcbSignalPathRuleCoverageEntry] = []
    for path in sorted(requirements.paths, key=lambda item: item.id.casefold()):
        if path.length is None:
            continue
        path_issues = endpoint_issues(path)
        condition = (
            f"A.fromTo('{drc_pad_selector(path.from_pad)}', '{drc_pad_selector(path.to_pad)}')"
        )
        constraints = (
            _compare_constraint(condition, "length", path.length, native, ignored_checks),
        )
        entries.append(
            PcbSignalPathRuleCoverageEntry(
                id=path.id,
                kind="path",
                basis=path.basis,
                net=path.net,
                from_pad=path.from_pad,
                to_pad=path.to_pad,
                status="COMPLETE"
                if not path_issues and all(item.status == "COVERED" for item in constraints)
                else "INCOMPLETE",
                constraints=constraints,
                issues=path_issues,
            )
        )

    for bundle in sorted(requirements.bundles, key=lambda item: item.id.casefold()):
        members = tuple(paths[item.casefold()] for item in bundle.path_ids)
        bundle_issues: list[str] = []
        expected_from = {drc_pad_selector(item.from_pad).casefold() for item in members}
        expected_to = {drc_pad_selector(item.to_pad).casefold() for item in members}
        observed_from = {
            drc_pad_selector(item.pad).casefold()
            for item in snapshot.pads
            if fnmatchcase(
                drc_pad_selector(item.pad).casefold(), bundle.from_pad_pattern.casefold()
            )
        }
        observed_to = {
            drc_pad_selector(item.pad).casefold()
            for item in snapshot.pads
            if fnmatchcase(drc_pad_selector(item.pad).casefold(), bundle.to_pad_pattern.casefold())
        }
        if observed_from != expected_from:
            bundle_issues.append(
                "The native from-pad pattern does not resolve to exactly the mapped bundle endpoints."
            )
        if observed_to != expected_to:
            bundle_issues.append(
                "The native to-pad pattern does not resolve to exactly the mapped bundle endpoints."
            )
        for path in members:
            bundle_issues.extend(endpoint_issues(path))
        condition = f"A.fromTo('{bundle.from_pad_pattern}', '{bundle.to_pad_pattern}')"
        constraint = _compare_constraint(condition, "skew", bundle.max_skew, native, ignored_checks)
        entries.append(
            PcbSignalPathRuleCoverageEntry(
                id=bundle.id,
                kind="bundle",
                basis=bundle.basis,
                from_pad_pattern=bundle.from_pad_pattern,
                to_pad_pattern=bundle.to_pad_pattern,
                path_ids=tuple(sorted(bundle.path_ids, key=str.casefold)),
                status="COMPLETE"
                if not bundle_issues and constraint.status == "COVERED"
                else "INCOMPLETE",
                constraints=(constraint,),
                issues=tuple(dict.fromkeys(bundle_issues)),
            )
        )
    return tuple(sorted(entries, key=lambda item: item.id.casefold()))
