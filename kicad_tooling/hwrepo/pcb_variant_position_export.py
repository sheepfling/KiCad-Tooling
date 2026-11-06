"""Read stable, source-bound KiCad PCB position exports."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from .contracts import read_regular_bytes
from .evidence import digest_bytes
from .model_primitives import Digest


@dataclass(frozen=True, slots=True)
class PcbVariantPositionExport:
    """Parsed references and optional value column from one exact CSV byte set."""

    source_sha256: Digest
    references: tuple[str, ...]
    value_column_status: Literal["PRESENT", "ABSENT"]
    values_by_reference: Mapping[str, str] | None

    def __post_init__(self) -> None:
        references = tuple(self.references)
        values = (
            None
            if self.values_by_reference is None
            else MappingProxyType(dict(self.values_by_reference))
        )
        if self.value_column_status == "PRESENT":
            if values is None or tuple(values) != references:
                raise ValueError("PCB position values must match their parsed references")
        elif values is not None:
            raise ValueError("PCB position values require a present value column")
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "values_by_reference", values)


def read_pcb_variant_position_export(path: Path) -> PcbVariantPositionExport:
    """Parse one stable regular-file read and hash the exact parsed bytes."""
    content, _ = read_regular_bytes(path)
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise ValueError(f"KiCad position export has no CSV header: {path.name}")
    reference_column = next(
        (name for name in reader.fieldnames if name.strip().casefold() in {"ref", "reference"}),
        None,
    )
    if reference_column is None:
        raise ValueError(f"KiCad position export has no reference column: {path.name}")
    value_column = next(
        (name for name in reader.fieldnames if name.strip().casefold() in {"val", "value"}),
        None,
    )
    rows = tuple(row for row in reader if any(value and value.strip() for value in row.values()))
    references = tuple((row.get(reference_column) or "").strip() for row in rows)
    keys = [reference.casefold() for reference in references]
    if any(not reference for reference in references) or len(keys) != len(set(keys)):
        raise ValueError(
            f"KiCad position export contains blank or duplicate references: {path.name}"
        )
    values = (
        None
        if value_column is None
        else {
            reference: (row.get(value_column) or "").strip()
            for reference, row in zip(references, rows, strict=True)
        }
    )
    return PcbVariantPositionExport(
        source_sha256=digest_bytes(content),
        references=references,
        value_column_status="ABSENT" if values is None else "PRESENT",
        values_by_reference=values,
    )


def read_verified_pcb_variant_position_export(
    path: Path,
    *,
    expected_sha256: Digest,
) -> PcbVariantPositionExport:
    """Read one stable export and require its parsed bytes to match the receipt."""
    export = read_pcb_variant_position_export(path)
    if export.source_sha256 != expected_sha256:
        raise ValueError("KiCad position export differs from source-bound evidence")
    return export
