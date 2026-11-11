"""Typed source-bound evidence for pair-transition reference-via review."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeCount,
    RepositoryPath,
    StrictModel,
)


class PcbReferenceViaTransition(StrictModel):
    """One cross-layer transition and the nearest compatible reference-net via."""

    path_id: Identifier
    from_layer: NonEmptyText | None = None
    to_layer: NonEmptyText | None = None
    signal_via_id: Digest | None = None
    position_nm: tuple[int, int] | None = None
    nearest_reference_via_id: Digest | None = None
    nearest_distance_nm: NonNegativeCount | None = None
    nearest_distance_squared_nm2: NonNegativeCount | None = None
    status: Literal["WITHIN_LIMIT", "MISSING_REFERENCE_VIA", "INCOMPLETE"]
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def transition_state(self) -> PcbReferenceViaTransition:
        if self.status == "WITHIN_LIMIT":
            if (
                self.signal_via_id is None
                or self.position_nm is None
                or self.nearest_reference_via_id is None
                or self.nearest_distance_nm is None
                or self.nearest_distance_squared_nm2 is None
                or self.issue is not None
            ):
                raise ValueError("A supported reference-via transition needs exact via evidence")
        elif self.status == "MISSING_REFERENCE_VIA":
            if (
                self.signal_via_id is None
                or self.position_nm is None
                or self.issue is not None
                or len(
                    {
                        self.nearest_reference_via_id is None,
                        self.nearest_distance_nm is None,
                        self.nearest_distance_squared_nm2 is None,
                    }
                )
                != 1
            ):
                raise ValueError(
                    "A missing reference-via result needs a resolved signal transition"
                )
        elif self.issue is None:
            raise ValueError("An incomplete reference-via transition must explain its evidence gap")
        return self


class PcbDifferentialPairReferenceViaEntry(StrictModel):
    """Reference-via checks for every layer transition in one authored pair."""

    bundle_id: Identifier
    reference_net: NetName
    max_distance_nm: NonNegativeCount
    status: Literal["WITHIN_LIMIT", "MISSING_REFERENCE_VIA", "INCOMPLETE"]
    transitions: tuple[PcbReferenceViaTransition, ...]
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def entry_state(self) -> PcbDifferentialPairReferenceViaEntry:
        has_missing = any(item.status == "MISSING_REFERENCE_VIA" for item in self.transitions)
        has_incomplete = any(item.status == "INCOMPLETE" for item in self.transitions)
        if any(
            item.status == "WITHIN_LIMIT"
            and item.nearest_distance_squared_nm2 is not None
            and item.nearest_distance_squared_nm2 > self.max_distance_nm**2
            for item in self.transitions
        ):
            raise ValueError("A within-limit reference via must satisfy its authored maximum")
        if any(
            item.status == "MISSING_REFERENCE_VIA"
            and item.nearest_distance_squared_nm2 is not None
            and item.nearest_distance_squared_nm2 <= self.max_distance_nm**2
            for item in self.transitions
        ):
            raise ValueError("A missing reference via must exceed its authored maximum")
        if self.status == "WITHIN_LIMIT" and (
            has_missing or has_incomplete or self.issue is not None
        ):
            raise ValueError("A within-limit pair cannot contain unresolved transitions")
        if self.status == "MISSING_REFERENCE_VIA" and (not has_missing or has_incomplete):
            raise ValueError(
                "A missing-via pair must contain resolved transitions beyond the bound"
            )
        if self.status == "INCOMPLETE" and not has_incomplete and self.issue is None:
            raise ValueError("An incomplete pair must contain an unsupported transition")
        if self.issue is not None and self.status != "INCOMPLETE":
            raise ValueError("Only an incomplete pair can carry a coverage issue")
        return self


class PcbDifferentialPairReferenceViaReport(StrictModel):
    """Exact board/map-bound result for configured pair reference-via heuristics."""

    status: Literal["NOT_REQUESTED", "DISABLED", "COMPLETE", "INCOMPLETE", "BLOCKED"] = (
        "NOT_REQUESTED"
    )
    mode: Literal["review", "block", "off"] | None = None
    map_sha256: Digest | None = None
    source_inventory_sha256: Digest | None = None
    netlist_sha256: Digest | None = None
    board_path: RepositoryPath | None = None
    board_sha256: Digest | None = None
    snapshot_path: RepositoryPath | None = None
    snapshot_sha256: Digest | None = None
    command_path: RepositoryPath | None = None
    command_sha256: Digest | None = None
    probe_sha256: Digest | None = None
    kicad_version: NonEmptyText | None = None
    image: NonEmptyText | None = None
    configured_bundle_ids: tuple[Identifier, ...] = ()
    entries: tuple[PcbDifferentialPairReferenceViaEntry, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def report_matches_entries(self) -> PcbDifferentialPairReferenceViaReport:
        if len({item.bundle_id.casefold() for item in self.entries}) != len(self.entries):
            raise ValueError("Reference-via report cannot repeat pair bundle IDs")
        if len({item.casefold() for item in self.configured_bundle_ids}) != len(
            self.configured_bundle_ids
        ):
            raise ValueError("Reference-via report cannot repeat configured pair bundle IDs")
        if self.status in {"COMPLETE", "INCOMPLETE"}:
            if not self.entries or any(
                value is None
                for value in (
                    self.map_sha256,
                    self.source_inventory_sha256,
                    self.netlist_sha256,
                    self.board_path,
                    self.board_sha256,
                    self.snapshot_path,
                    self.snapshot_sha256,
                    self.command_path,
                    self.command_sha256,
                    self.probe_sha256,
                    self.kicad_version,
                    self.image,
                )
            ):
                raise ValueError("Measured reference-via evidence must bind its map and sources")
            if self.mode not in {"review", "block"}:
                raise ValueError("Measured reference-via evidence needs an active rule mode")
            has_incomplete = any(item.status != "WITHIN_LIMIT" for item in self.entries)
            if (self.status == "INCOMPLETE") != has_incomplete:
                raise ValueError("Reference-via report status must match its pair entries")
            if {item.casefold() for item in self.configured_bundle_ids} != {
                item.bundle_id.casefold() for item in self.entries
            }:
                raise ValueError("Measured reference-via entries must cover every configured pair")
            if self.issue is not None:
                raise ValueError("Measured reference-via reports cannot carry a blocking issue")
        elif self.status == "BLOCKED":
            if self.issue is None or not self.configured_bundle_ids or self.entries:
                raise ValueError("Blocked reference-via coverage needs its map scope and issue")
            if self.mode not in {"review", "block"}:
                raise ValueError("Blocked reference-via coverage needs an active rule mode")
        elif self.status == "DISABLED" and self.mode != "off":
            raise ValueError("Disabled reference-via evidence must use off mode")
        elif self.status == "NOT_REQUESTED" and self.entries:
            raise ValueError("Unrequested reference-via evidence cannot contain entries")
        elif self.status == "NOT_REQUESTED" and self.configured_bundle_ids:
            raise ValueError("Unrequested reference-via evidence cannot declare active bundles")
        return self
