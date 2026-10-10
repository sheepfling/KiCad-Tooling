"""Typed project requirements and reports for native PCB DRC coverage."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    PositiveCount,
    Reference,
    RepositoryPath,
    StrictModel,
)


class PcbDrcMinMaxRequirement(StrictModel):
    """Explicit lower and/or upper geometry bounds in integer nanometers."""

    min_nm: PositiveCount | None = None
    max_nm: PositiveCount | None = None

    @model_validator(mode="after")
    def ordered_bounds(self) -> PcbDrcMinMaxRequirement:
        if self.min_nm is None and self.max_nm is None:
            raise ValueError("A native DRC min/max requirement needs at least one bound")
        if self.min_nm is not None and self.max_nm is not None and self.min_nm > self.max_nm:
            raise ValueError("A native DRC minimum cannot exceed its maximum")
        return self


class PcbDrcMaximumRequirement(StrictModel):
    """Explicit upper bound for a native DRC geometry constraint."""

    max_nm: PositiveCount


PcbDrcPadSelectorPattern = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_.?*-]+$", min_length=3),
]


class PcbSignalPathRequirement(StrictModel):
    """One project-mapped PCB pad-to-pad path and its optional native length limit."""

    id: Identifier
    basis: NonEmptyText
    net: NetName
    from_pad: Reference
    to_pad: Reference
    length: PcbDrcMinMaxRequirement | None = None

    @model_validator(mode="after")
    def exact_path_endpoints(self) -> PcbSignalPathRequirement:
        if self.net.startswith("/"):
            raise ValueError("Use the native net name without a leading slash")
        if self.from_pad.casefold() == self.to_pad.casefold():
            raise ValueError("A PCB signal path needs two distinct endpoint pads")
        if self.from_pad.count(".") != 1 or self.to_pad.count(".") != 1:
            raise ValueError("PCB signal-path endpoints must use exact reference.pad values")
        return self


class PcbSignalPathBundleRequirement(StrictModel):
    """Exact member paths and pad patterns for one project-reviewed skew group."""

    id: Identifier
    basis: NonEmptyText
    path_ids: Annotated[tuple[Identifier, ...], Field(min_length=2)]
    from_pad_pattern: PcbDrcPadSelectorPattern
    to_pad_pattern: PcbDrcPadSelectorPattern
    max_skew: PcbDrcMaximumRequirement

    @model_validator(mode="after")
    def wildcard_pad_patterns(self) -> PcbSignalPathBundleRequirement:
        if not any(character in self.from_pad_pattern for character in "*?"):
            raise ValueError("A signal-path bundle from-pad pattern must use a wildcard")
        if not any(character in self.to_pad_pattern for character in "*?"):
            raise ValueError("A signal-path bundle to-pad pattern must use a wildcard")
        if "-" not in self.from_pad_pattern or "-" not in self.to_pad_pattern:
            raise ValueError("Native fromTo pad patterns must use reference-pad syntax")
        if len({item.casefold() for item in self.path_ids}) != len(self.path_ids):
            raise ValueError("A signal-path bundle cannot repeat a member path")
        return self


class PcbSignalPathRuleMap(StrictModel):
    """Project-authored pad paths and skew groups for auditing native DRC rule coverage."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    paths: Annotated[tuple[PcbSignalPathRequirement, ...], Field(min_length=1)]
    bundles: tuple[PcbSignalPathBundleRequirement, ...] = ()

    @model_validator(mode="after")
    def unique_paths_and_valid_bundles(self) -> PcbSignalPathRuleMap:
        path_ids = {item.id.casefold() for item in self.paths}
        all_ids = [item.id.casefold() for item in self.paths] + [
            item.id.casefold() for item in self.bundles
        ]
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("PCB signal-path and bundle IDs must be unique")
        endpoints = [
            tuple(sorted((item.from_pad.casefold(), item.to_pad.casefold()))) for item in self.paths
        ]
        if len(set(endpoints)) != len(endpoints):
            raise ValueError("A PCB pad-to-pad signal path can only be mapped once")
        bundle_members: set[str] = set()
        for bundle in self.bundles:
            missing = {item.casefold() for item in bundle.path_ids} - path_ids
            if missing:
                raise ValueError(
                    f"Signal-path bundle {bundle.id!r} refers to unknown path IDs: "
                    f"{', '.join(sorted(missing))}"
                )
            members = tuple(
                item
                for item in self.paths
                if item.id.casefold() in {path_id.casefold() for path_id in bundle.path_ids}
            )
            if len({item.net.casefold() for item in members}) != len(members):
                raise ValueError("Signal-path bundle members must use distinct nets")
            if len({item.from_pad.casefold() for item in members}) != len(members) or len(
                {item.to_pad.casefold() for item in members}
            ) != len(members):
                raise ValueError("Signal-path bundle members must have unique endpoint pads")
            if not all(
                fnmatchcase(
                    _pcb_drc_pad_selector(item.from_pad).casefold(),
                    bundle.from_pad_pattern.casefold(),
                )
                and fnmatchcase(
                    _pcb_drc_pad_selector(item.to_pad).casefold(),
                    bundle.to_pad_pattern.casefold(),
                )
                for item in members
            ):
                raise ValueError("Signal-path bundle pad patterns must match every member path")
            member_keys = {item.id.casefold() for item in members}
            if bundle_members & member_keys:
                raise ValueError("A signal path can belong to only one skew bundle")
            bundle_members.update(member_keys)
        if any(
            item.length is None and item.id.casefold() not in bundle_members for item in self.paths
        ):
            raise ValueError("Every signal path needs a length bound or a skew-bundle membership")
        return self


def _pcb_drc_pad_selector(pad: str) -> str:
    reference, pad_number = pad.split(".", 1)
    return f"{reference}-{pad_number}"


class PcbDifferentialPairRuleRequirement(StrictModel):
    """Project-reviewed pair identity and the exact native DRC bounds it requires."""

    id: Identifier
    basis: NonEmptyText
    positive_net: NetName
    negative_net: NetName
    pair_selector: NonEmptyText
    track_width: PcbDrcMinMaxRequirement | None = None
    diff_pair_gap: PcbDrcMinMaxRequirement | None = None
    skew: PcbDrcMaximumRequirement | None = None
    uncoupled_length: PcbDrcMaximumRequirement | None = None

    @model_validator(mode="after")
    def complete_pair_requirement(self) -> PcbDifferentialPairRuleRequirement:
        if self.positive_net.casefold() == self.negative_net.casefold():
            raise ValueError("A differential pair must name two distinct nets")
        if not (
            self.positive_net.startswith(self.pair_selector)
            and self.negative_net.startswith(self.pair_selector)
        ):
            raise ValueError("The pair selector must be a prefix of both explicitly named nets")
        if not any(
            item is not None
            for item in (self.track_width, self.diff_pair_gap, self.skew, self.uncoupled_length)
        ):
            raise ValueError("A differential-pair requirement needs at least one DRC constraint")
        return self


class PcbDifferentialPairRuleMap(StrictModel):
    """Project-authored inventory for auditing native DRC rule coverage only."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    requirements: Annotated[tuple[PcbDifferentialPairRuleRequirement, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_pairs(self) -> PcbDifferentialPairRuleMap:
        if len({item.id.casefold() for item in self.requirements}) != len(self.requirements):
            raise ValueError("Differential-pair rule requirement IDs must be unique")
        pairs = {
            (item.positive_net.casefold(), item.negative_net.casefold())
            for item in self.requirements
        }
        if len(pairs) != len(self.requirements):
            raise ValueError("A differential net pair can only be mapped once")
        return self


PcbDrcConstraintName = Literal[
    "track_width", "diff_pair_gap", "skew", "diff_pair_uncoupled", "length"
]

PcbDrcConstraintCoverageStatus = Literal[
    "COVERED", "MISSING", "MISMATCH", "AMBIGUOUS", "IGNORED", "UNSUPPORTED"
]


class PcbDrcConstraintCoverage(StrictModel):
    """Exact native-rule match for one project-authored DRC constraint."""

    constraint: PcbDrcConstraintName
    status: PcbDrcConstraintCoverageStatus
    expected_min_nm: PositiveCount | None = None
    expected_max_nm: PositiveCount | None = None
    observed_min_nm: PositiveCount | None = None
    observed_max_nm: PositiveCount | None = None
    rule_names: tuple[NonEmptyText, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def evidence_matches_status(self) -> PcbDrcConstraintCoverage:
        if self.status == "COVERED" and (
            not self.rule_names
            or self.expected_min_nm != self.observed_min_nm
            or self.expected_max_nm != self.observed_max_nm
        ):
            raise ValueError("Covered native DRC constraints must match exact rule bounds")
        if self.status != "COVERED" and self.issue is None:
            raise ValueError("Uncovered native DRC constraints must explain their status")
        return self


class PcbDifferentialPairRuleCoverageEntry(StrictModel):
    id: Identifier
    basis: NonEmptyText
    positive_net: NetName
    negative_net: NetName
    pair_selector: NonEmptyText
    status: Literal["COMPLETE", "INCOMPLETE"]
    constraints: tuple[PcbDrcConstraintCoverage, ...]
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def match_constraint_status(self) -> PcbDifferentialPairRuleCoverageEntry:
        complete = not self.issues and all(item.status == "COVERED" for item in self.constraints)
        if (self.status == "COMPLETE") != complete:
            raise ValueError("Pair coverage status must agree with its exact constraints")
        if not self.constraints:
            raise ValueError("Pair coverage entries need at least one required constraint")
        return self


class PcbDifferentialPairRuleCoverageReport(StrictModel):
    """Source-bound audit of explicit pair requirements against native DRC rules."""

    status: Literal["NOT_REQUESTED", "DISABLED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    mode: Literal["review", "block", "off"] | None = None
    map_sha256: Digest | None = None
    source_inventory_sha256: Digest | None = None
    project_path: RepositoryPath | None = None
    project_sha256: Digest | None = None
    rules_path: RepositoryPath | None = None
    rules_sha256: Digest | None = None
    board_path: RepositoryPath | None = None
    board_sha256: Digest | None = None
    native_summary_path: RepositoryPath | None = None
    native_summary_sha256: Digest | None = None
    native_drc_path: RepositoryPath | None = None
    native_drc_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    entries: tuple[PcbDifferentialPairRuleCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def scanned_report_is_bound(self) -> PcbDifferentialPairRuleCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and any(
            item is None
            for item in (
                self.map_sha256,
                self.source_inventory_sha256,
                self.project_path,
                self.project_sha256,
                self.rules_path,
                self.board_path,
                self.board_sha256,
                self.native_summary_path,
                self.native_summary_sha256,
                self.native_drc_path,
                self.native_drc_sha256,
                self.kicad_version,
                self.image,
            )
        ):
            raise ValueError("Scanned differential-pair rule coverage must bind all inputs")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            if not self.entries:
                raise ValueError("Scanned differential-pair coverage must include each mapped pair")
            any_incomplete = any(item.status == "INCOMPLETE" for item in self.entries)
            if (self.status == "COMPLETE" and any_incomplete) or (
                self.status == "INCOMPLETE" and not any_incomplete
            ):
                raise ValueError("Differential-pair report status must match its mapped entries")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked differential-pair rule coverage must explain the gap")
        return self


class PcbSignalPathRuleCoverageEntry(StrictModel):
    """Native DRC coverage for one exact pad path or mapped skew bundle."""

    id: Identifier
    kind: Literal["path", "bundle"]
    basis: NonEmptyText
    net: NetName | None = None
    from_pad: Reference | None = None
    to_pad: Reference | None = None
    from_pad_pattern: PcbDrcPadSelectorPattern | None = None
    to_pad_pattern: PcbDrcPadSelectorPattern | None = None
    path_ids: tuple[Identifier, ...] = ()
    status: Literal["COMPLETE", "INCOMPLETE"]
    constraints: tuple[PcbDrcConstraintCoverage, ...]
    issues: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def entry_matches_kind_and_status(self) -> PcbSignalPathRuleCoverageEntry:
        if self.kind == "path":
            if (
                self.net is None
                or self.from_pad is None
                or self.to_pad is None
                or self.from_pad_pattern is not None
                or self.to_pad_pattern is not None
                or self.path_ids
            ):
                raise ValueError("Signal-path coverage entries need exact path endpoints")
            if not any(item.constraint == "length" for item in self.constraints):
                raise ValueError("Signal-path coverage entries need a length constraint")
        elif (
            self.from_pad_pattern is None
            or self.to_pad_pattern is None
            or len(self.path_ids) < 2
            or self.net is not None
            or self.from_pad is not None
            or self.to_pad is not None
            or not any(item.constraint == "skew" for item in self.constraints)
        ):
            raise ValueError("Signal-path bundle coverage entries need mapped paths and skew")
        complete = not self.issues and all(item.status == "COVERED" for item in self.constraints)
        if (self.status == "COMPLETE") != complete:
            raise ValueError("Signal-path coverage status must match its exact constraints")
        return self


class PcbSignalPathRuleCoverageReport(StrictModel):
    """Source-bound audit of mapped signal paths against native KiCad DRC rules."""

    status: Literal["NOT_REQUESTED", "DISABLED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    mode: Literal["review", "block", "off"] | None = None
    map_sha256: Digest | None = None
    source_inventory_sha256: Digest | None = None
    project_path: RepositoryPath | None = None
    project_sha256: Digest | None = None
    rules_path: RepositoryPath | None = None
    rules_sha256: Digest | None = None
    board_path: RepositoryPath | None = None
    board_sha256: Digest | None = None
    native_summary_path: RepositoryPath | None = None
    native_summary_sha256: Digest | None = None
    native_drc_path: RepositoryPath | None = None
    native_drc_sha256: Digest | None = None
    pcb_snapshot_path: RepositoryPath | None = None
    pcb_snapshot_sha256: Digest | None = None
    pcb_command_path: RepositoryPath | None = None
    pcb_command_sha256: Digest | None = None
    pcb_probe_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    entries: tuple[PcbSignalPathRuleCoverageEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def scanned_report_is_bound(self) -> PcbSignalPathRuleCoverageReport:
        if self.status in {"COMPLETE", "INCOMPLETE"} and any(
            item is None
            for item in (
                self.map_sha256,
                self.source_inventory_sha256,
                self.project_path,
                self.project_sha256,
                self.rules_path,
                self.board_path,
                self.board_sha256,
                self.native_summary_path,
                self.native_summary_sha256,
                self.native_drc_path,
                self.native_drc_sha256,
                self.pcb_snapshot_path,
                self.pcb_snapshot_sha256,
                self.pcb_command_path,
                self.pcb_command_sha256,
                self.pcb_probe_sha256,
                self.kicad_version,
                self.image,
            )
        ):
            raise ValueError("Scanned signal-path rule coverage must bind all inputs")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            if not self.entries:
                raise ValueError("Scanned signal-path coverage must include every mapped path")
            any_incomplete = any(item.status == "INCOMPLETE" for item in self.entries)
            if (self.status == "COMPLETE" and any_incomplete) or (
                self.status == "INCOMPLETE" and not any_incomplete
            ):
                raise ValueError("Signal-path report status must match its mapped entries")
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked signal-path rule coverage must explain the evidence gap")
        return self
