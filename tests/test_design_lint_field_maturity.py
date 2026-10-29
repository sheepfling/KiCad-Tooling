"""Require field-validation claims to point to reviewed evidence."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kicad_tooling.design_lint import catalog_text
from kicad_tooling.hwrepo.design_lint import rule_catalog
from kicad_tooling.hwrepo.design_lint_rule_models import (
    DesignLintRuleCatalog,
    DesignLintRuleMetadata,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint]


def test_field_validated_maturity_requires_independent_evidence_reference() -> None:
    entry = rule_catalog().rules[0].model_dump(mode="python")
    entry["maturity"] = "field_validated"

    with pytest.raises(ValidationError, match="source-hashed evidence"):
        DesignLintRuleMetadata.model_validate(entry)

    entry["field_validation_evidence"] = {
        "docs/reviews/public-unit-set.md": "a" * 64,
    }
    validated = DesignLintRuleMetadata.model_validate(entry)
    catalog = DesignLintRuleCatalog(
        schema_version="3",
        sha256="a" * 64,
        rules=(validated,),
    )

    rendered = catalog_text(catalog)
    assert "Maturity: field_validated" in rendered
    evidence_line = (
        f"Field validation evidence: docs/reviews/public-unit-set.md (SHA-256 {'a' * 64})"
    )
    assert evidence_line in rendered


def test_non_field_maturity_cannot_claim_field_validation_evidence() -> None:
    entry = rule_catalog().rules[0].model_dump(mode="python")
    entry["field_validation_evidence"] = {"docs/reviews/unreviewed.md": "b" * 64}

    with pytest.raises(ValidationError, match="requires field-validated maturity"):
        DesignLintRuleMetadata.model_validate(entry)


def test_field_validation_evidence_requires_sha256_digests() -> None:
    entry = rule_catalog().rules[0].model_dump(mode="python")
    entry["maturity"] = "field_validated"
    entry["field_validation_evidence"] = {"docs/reviews/public-unit-set.md": "not-a-digest"}

    with pytest.raises(ValidationError):
        DesignLintRuleMetadata.model_validate(entry)


@pytest.mark.parametrize(
    "path",
    [
        "/tmp/review.md",
        "../review.md",
        "docs/../review.md",
        r"docs\review.md",
        "C:/review.md",
        "C:review.md",
    ],
)
def test_field_validation_evidence_paths_must_stay_in_repository(path: str) -> None:
    entry = rule_catalog().rules[0].model_dump(mode="python")
    entry["maturity"] = "field_validated"
    entry["field_validation_evidence"] = {path: "a" * 64}

    with pytest.raises(ValidationError, match="repository-relative"):
        DesignLintRuleMetadata.model_validate(entry)
