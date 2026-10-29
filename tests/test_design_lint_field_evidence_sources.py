"""Verify that field-validation claims cite exact repository source bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from kicad_tooling.hwrepo.design_lint_catalog_evidence import (
    validate_field_validation_evidence_sources,
)
from kicad_tooling.hwrepo.design_lint_rule_models import DesignLintRuleCatalog

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint]


def _catalog_with_evidence(path: str, digest: str) -> DesignLintRuleCatalog:
    catalog = rule_catalog()
    rule = catalog.rules[0].model_copy(
        update={"maturity": "field_validated", "field_validation_evidence": {path: digest}}
    )
    return DesignLintRuleCatalog(
        schema_version=catalog.schema_version,
        sha256=catalog.sha256,
        rules=(rule,),
    )


def test_packaged_catalog_field_evidence_matches_repository_sources() -> None:
    repository = Path(__file__).resolve().parents[1]

    validate_field_validation_evidence_sources(rule_catalog(), repository)


def test_field_evidence_accepts_exact_repository_file_hash(tmp_path: Path) -> None:
    content = b"Independent review record\n"
    (tmp_path / "review.md").write_bytes(content)
    catalog = _catalog_with_evidence("review.md", hashlib.sha256(content).hexdigest())

    validate_field_validation_evidence_sources(catalog, tmp_path)


def test_field_evidence_rejects_missing_source_and_digest_mismatch(tmp_path: Path) -> None:
    catalog = _catalog_with_evidence("missing.md", "a" * 64)

    with pytest.raises(ValueError, match="evidence source does not exist"):
        validate_field_validation_evidence_sources(catalog, tmp_path)

    (tmp_path / "review.md").write_text("changed review record\n", encoding="utf-8")
    mismatched = _catalog_with_evidence("review.md", "a" * 64)
    with pytest.raises(ValueError, match="evidence digest mismatch"):
        validate_field_validation_evidence_sources(mismatched, tmp_path)


def test_field_evidence_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-review.md"
    outside.write_text("outside\n", encoding="utf-8")
    (tmp_path / "review.md").symlink_to(outside)
    catalog = _catalog_with_evidence("review.md", hashlib.sha256(b"outside\n").hexdigest())

    with pytest.raises(ValueError, match="escapes repository"):
        validate_field_validation_evidence_sources(catalog, tmp_path)
