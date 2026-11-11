"""Typed project requirements and reports for native PCB DRC coverage."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from . import pcb_signal_path_rule_models as _pcb_signal_path_rule_models
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
from .pcb_differential_pair_reference_via_models import (
    PcbDifferentialPairReferenceViaReport,
)
from .pcb_differential_pair_skew_models import PcbDifferentialPairRouteSkewReport
from .pcb_signal_path_rule_models import (
    PcbDrcMaximumRequirement,
    PcbDrcMinMaxRequirement,
    PcbDrcPadSelectorPattern,
)

PcbSignalPathBundleRequirement = _pcb_signal_path_rule_models.PcbSignalPathBundleRequirement
PcbSignalPathRequirement = _pcb_signal_path_rule_models.PcbSignalPathRequirement
PcbSignalPathRuleMap = _pcb_signal_path_rule_models.PcbSignalPathRuleMap


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
    edge_clearance: PcbDrcMinMaxRequirement | None = None

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
            for item in (
                self.track_width,
                self.diff_pair_gap,
                self.skew,
                self.uncoupled_length,
                self.edge_clearance,
            )
        ):
            raise ValueError("A differential-pair requirement needs at least one DRC constraint")
        if self.edge_clearance is not None and self.edge_clearance.max_nm is not None:
            raise ValueError("Differential-pair edge clearance supports only an authored minimum")
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
    "track_width",
    "diff_pair_gap",
    "skew",
    "diff_pair_uncoupled",
    "length",
    "physical_clearance",
    "edge_clearance",
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
            if not any(
                item.constraint in {"length", "edge_clearance"} for item in self.constraints
            ):
                raise ValueError("Signal-path coverage entries need a length or edge constraint")
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
    route_skew: PcbDifferentialPairRouteSkewReport | None = None
    reference_via_stitching: PcbDifferentialPairReferenceViaReport | None = None
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
        if self.route_skew is not None:
            if self.map_sha256 is not None and self.route_skew.map_sha256 != self.map_sha256:
                raise ValueError("Signal-path route skew must bind the same authored path map")
            if (
                self.status in {"COMPLETE", "INCOMPLETE"}
                and self.route_skew.status
                in {
                    "COMPLETE",
                    "INCOMPLETE",
                }
                and (
                    self.board_path != self.route_skew.board_path
                    or self.board_sha256 != self.route_skew.board_sha256
                    or self.pcb_snapshot_path != self.route_skew.snapshot_path
                    or self.pcb_snapshot_sha256 != self.route_skew.snapshot_sha256
                    or self.source_inventory_sha256 != self.route_skew.source_inventory_sha256
                )
            ):
                raise ValueError("Signal-path and measured route skew use different PCB evidence")
        if self.reference_via_stitching is not None:
            stitching = self.reference_via_stitching
            if self.map_sha256 is not None and stitching.map_sha256 != self.map_sha256:
                raise ValueError(
                    "Reference-via stitching must bind the same authored signal-path map"
                )
            if (
                self.status in {"COMPLETE", "INCOMPLETE"}
                and stitching.status in {"COMPLETE", "INCOMPLETE"}
                and (
                    self.board_path != stitching.board_path
                    or self.board_sha256 != stitching.board_sha256
                    or self.pcb_snapshot_path != stitching.snapshot_path
                    or self.pcb_snapshot_sha256 != stitching.snapshot_sha256
                    or self.source_inventory_sha256 != stitching.source_inventory_sha256
                )
            ):
                raise ValueError(
                    "Signal-path and reference-via checks use different PCB source evidence"
                )
        return self
