"""Project-authored path and pair-bundle requirements for PCB signal review."""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .model_primitives import (
    Identifier,
    NetName,
    NonEmptyText,
    NonNegativeCount,
    PositiveCount,
    Reference,
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

    max_nm: NonNegativeCount


PcbDrcPadSelectorPattern = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_.?*-]+$", min_length=3),
]


class PcbSignalPathRequirement(StrictModel):
    """One project-mapped PCB pad-to-pad path and its native DRC limits."""

    id: Identifier
    basis: NonEmptyText
    net: NetName
    from_pad: Reference
    to_pad: Reference
    length: PcbDrcMinMaxRequirement | None = None
    edge_clearance: PcbDrcMinMaxRequirement | None = None

    @model_validator(mode="after")
    def exact_path_endpoints(self) -> PcbSignalPathRequirement:
        if PurePosixPath(self.net).is_absolute():
            raise ValueError("Use the native net name without a leading slash")
        if self.from_pad.casefold() == self.to_pad.casefold():
            raise ValueError("A PCB signal path needs two distinct endpoint pads")
        if self.from_pad.count(".") != 1 or self.to_pad.count(".") != 1:
            raise ValueError("PCB signal-path endpoints must use exact reference.pad values")
        if self.edge_clearance is not None and self.edge_clearance.max_nm is not None:
            raise ValueError("Signal-path edge clearance supports only an authored minimum")
        if self.edge_clearance is not None and any(
            character in "'\\\"" or ord(character) < 32 for character in self.net
        ):
            raise ValueError(
                "Signal-path edge-clearance net cannot be represented exactly in a rule"
            )
        return self


class PcbSignalPathBundleRequirement(StrictModel):
    """Exact member paths and pad patterns for one project-reviewed skew group."""

    id: Identifier
    basis: NonEmptyText
    path_ids: Annotated[tuple[Identifier, ...], Field(min_length=2)]
    from_pad_pattern: PcbDrcPadSelectorPattern
    to_pad_pattern: PcbDrcPadSelectorPattern
    max_skew: PcbDrcMaximumRequirement | None = None
    reference_net: NetName | None = None
    max_reference_via_distance_nm: PositiveCount | None = None

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
        if (self.reference_net is None) != (self.max_reference_via_distance_nm is None):
            raise ValueError(
                "Reference-via stitching needs both an exact reference net and a distance bound"
            )
        if self.max_skew is None and self.reference_net is None:
            raise ValueError("A signal-path bundle needs a skew limit or reference-via contract")
        return self


class PcbSignalPathRuleMap(StrictModel):
    """Project-authored pad paths and skew groups for native PCB rule coverage."""

    schema_version: Literal["1"] = "1"
    basis: NonEmptyText
    paths: Annotated[tuple[PcbSignalPathRequirement, ...], Field(min_length=1)]
    bundles: tuple[PcbSignalPathBundleRequirement, ...] = ()

    def has_native_drc_requirements(self) -> bool:
        """Return whether the map contains any length, edge-clearance, or skew bound."""
        return any(
            item.length is not None or item.edge_clearance is not None for item in self.paths
        ) or any(item.max_skew is not None for item in self.bundles)

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
            if bundle.reference_net is not None:
                if len(members) != 2:
                    raise ValueError(
                        "Reference-via stitching currently supports exactly two mapped pair paths"
                    )
                if bundle.reference_net.casefold() in {item.net.casefold() for item in members}:
                    raise ValueError(
                        "A reference-via net must be distinct from both signal-path nets"
                    )
            member_keys = {item.id.casefold() for item in members}
            if bundle_members & member_keys:
                raise ValueError("A signal path can belong to only one skew bundle")
            bundle_members.update(member_keys)
        if any(
            item.length is None
            and item.edge_clearance is None
            and item.id.casefold() not in bundle_members
            for item in self.paths
        ):
            raise ValueError("Every signal path needs a DRC bound or a skew-bundle membership")
        return self


def _pcb_drc_pad_selector(pad: str) -> str:
    reference, pad_number = pad.split(".", 1)
    return f"{reference}-{pad_number}"
