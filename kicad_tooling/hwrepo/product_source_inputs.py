"""Stable, source-bound reads for product indexes and product records."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .contracts import parse_model_text, read_regular_bytes, repo_path
from .model_primitives import Digest, RepositoryPath
from .product_models import ProductIndex, ProductIndexEntry, ProductRecord

ProductRecordState = Literal["MISSING", "UNAVAILABLE", "EVALUATED"]


@dataclass(frozen=True, slots=True)
class ProductFileIdentity:
    """Repository path and digest for the exact bytes read from a product source."""

    path: RepositoryPath
    sha256: Digest


@dataclass(frozen=True, slots=True)
class ProductIndexDocument:
    """Validated product index bound to the bytes that defined its entries."""

    source: ProductFileIdentity
    value: ProductIndex


@dataclass(frozen=True, slots=True)
class ProductSourceIdentity:
    """Validated product record and its exact repository source identity."""

    record: ProductRecord
    path: RepositoryPath
    sha256: Digest


@dataclass(frozen=True, slots=True)
class ProductRecordInput:
    """Captured state for one selected product-index entry."""

    index_id: str
    path: RepositoryPath
    state: ProductRecordState
    file_identity: ProductFileIdentity | None
    record: ProductRecord | None
    issue: str | None

    def __post_init__(self) -> None:
        if self.state == "EVALUATED":
            if self.file_identity is None or self.record is None or self.issue is not None:
                raise ValueError("Evaluated product inputs require a source and validated record")
        elif self.record is not None:
            raise ValueError("Unevaluated product inputs cannot contain a product record")
        if self.state == "MISSING" and self.file_identity is not None:
            raise ValueError("Missing product inputs cannot have a file identity")

    @property
    def source(self) -> ProductSourceIdentity | None:
        if self.file_identity is None or self.record is None:
            return None
        return ProductSourceIdentity(
            record=self.record,
            path=self.file_identity.path,
            sha256=self.file_identity.sha256,
        )


def read_product_index_document(root: Path, value: RepositoryPath) -> ProductIndexDocument:
    """Read and validate the product index once, retaining its exact-byte identity."""
    root = root.resolve()
    try:
        path = repo_path(root, value)
        content, _ = read_regular_bytes(path, maximum=4 * 1024 * 1024)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{value}: invalid product index: {exc}") from exc
    return parse_product_index_document(root, value, content)


def parse_product_index_document(
    root: Path, value: RepositoryPath, content: bytes
) -> ProductIndexDocument:
    """Validate already-captured index bytes and retain their exact identity."""
    root = root.resolve()
    try:
        path = repo_path(root, value)
        index = parse_model_text(content.decode("utf-8"), ProductIndex)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{value}: invalid product index: {exc}") from exc
    return ProductIndexDocument(
        source=ProductFileIdentity(
            path=path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(content).hexdigest(),
        ),
        value=index,
    )


def resolve_product_index_document(
    root: Path,
    value: RepositoryPath,
    document: ProductIndexDocument | None = None,
) -> ProductIndexDocument:
    """Use a captured index or read it once, requiring the configured repository path."""
    if document is None:
        return read_product_index_document(root, value)
    if document.source.path != value:
        raise ValueError("Captured product index path differs from repository configuration")
    return document


def _read_product_record(
    path: Path, repository_path: RepositoryPath, index_id: str
) -> tuple[ProductRecordInput, bytes | None]:
    try:
        content, _ = read_regular_bytes(path, maximum=4 * 1024 * 1024)
    except FileNotFoundError:
        return (
            ProductRecordInput(
                index_id, repository_path, "MISSING", None, None, "product record is missing"
            ),
            None,
        )
    except (OSError, ValueError) as exc:
        return (
            ProductRecordInput(index_id, repository_path, "UNAVAILABLE", None, None, str(exc)),
            None,
        )

    identity = ProductFileIdentity(
        path=repository_path,
        sha256=hashlib.sha256(content).hexdigest(),
    )
    try:
        record = parse_model_text(content.decode("utf-8"), ProductRecord)
    except (UnicodeError, ValueError) as exc:
        return (
            ProductRecordInput(
                index_id,
                repository_path,
                "UNAVAILABLE",
                identity,
                None,
                f"invalid product record: {exc}",
            ),
            content,
        )
    return (
        ProductRecordInput(index_id, repository_path, "EVALUATED", identity, record, None),
        content,
    )


def capture_product_record(root: Path, entry: ProductIndexEntry) -> ProductRecordInput:
    """Capture a product record while preserving missing and unavailable states."""
    root = root.resolve()
    try:
        path = repo_path(root, entry.path)
    except ValueError as exc:
        return ProductRecordInput(entry.id, entry.path, "UNAVAILABLE", None, None, str(exc))
    result, _ = _read_product_record(path, entry.path, entry.id)
    return result


def read_product_source(
    path: Path, repository_path: RepositoryPath
) -> tuple[ProductSourceIdentity, bytes]:
    """Compatibility read for a required product source and its original bytes."""
    result, content = _read_product_record(path, repository_path, "product")
    if result.source is None or content is None:
        raise ValueError(f"{repository_path}: {result.issue or result.state.lower()}")
    return result.source, content


def require_product_file_current(root: Path, source: ProductFileIdentity) -> None:
    """Require a captured product source to remain readable and byte-identical."""
    root = root.resolve()
    try:
        content, _ = read_regular_bytes(repo_path(root, source.path), maximum=4 * 1024 * 1024)
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"Product source {source.path} is unavailable during operation: {exc}"
        ) from exc
    if hashlib.sha256(content).hexdigest() != source.sha256:
        raise ValueError(f"Product source {source.path} changed during operation")


def require_product_index_document_current(root: Path, document: ProductIndexDocument) -> None:
    """Require a captured product index to remain readable and byte-identical."""
    require_product_file_current(root, document.source)


def product_record_freshness_issues(
    root: Path, records: tuple[ProductRecordInput, ...]
) -> tuple[str, ...]:
    """Report selected product records whose source bytes or availability changed."""
    issues: list[str] = []
    for record in records:
        if record.file_identity is not None:
            try:
                require_product_file_current(root, record.file_identity)
            except ValueError as exc:
                issues.append(str(exc))
            continue
        current = capture_product_record(
            root,
            ProductIndexEntry(id=record.index_id, path=record.path, project_ids=()),
        )
        if current.state != record.state:
            issues.append(
                f"Product source {record.path} changed state during operation "
                f"({record.state} to {current.state})"
            )
    return tuple(issues)
