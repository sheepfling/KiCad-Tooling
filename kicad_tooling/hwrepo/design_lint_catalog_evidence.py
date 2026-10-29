"""Verify source hashes cited by field-validated lint catalog entries."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from .design_lint_rule_models import DesignLintRuleCatalog


def validate_field_validation_evidence_sources(
    catalog: DesignLintRuleCatalog, repository_root: Path
) -> None:
    """Require every field-validation evidence path to resolve and match its SHA-256."""
    root = repository_root.resolve()
    errors: list[str] = []
    for rule in catalog.rules:
        for relative_path, expected_digest in sorted(rule.field_validation_evidence.items()):
            path = PurePosixPath(relative_path)
            if path.is_absolute() or ".." in path.parts or str(path) != relative_path:
                errors.append(
                    f"{rule.rule_id}: evidence path is not repository-relative: {relative_path}"
                )
                continue
            try:
                source = (root / Path(*path.parts)).resolve(strict=True)
            except OSError:
                errors.append(f"{rule.rule_id}: evidence source does not exist: {relative_path}")
                continue
            if not source.is_relative_to(root):
                errors.append(
                    f"{rule.rule_id}: evidence source escapes repository: {relative_path}"
                )
                continue
            if not source.is_file():
                errors.append(f"{rule.rule_id}: evidence source is not a file: {relative_path}")
                continue
            actual_digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if actual_digest != expected_digest:
                errors.append(f"{rule.rule_id}: evidence digest mismatch: {relative_path}")
    if errors:
        raise ValueError("Invalid field-validation evidence sources: " + "; ".join(errors))
