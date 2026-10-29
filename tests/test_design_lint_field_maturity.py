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

    with pytest.raises(ValidationError, match="independently reviewed evidence"):
        DesignLintRuleMetadata.model_validate(entry)

    entry["field_validation_evidence"] = ("measurement:reviewed-unit-set-2026-01",)
    validated = DesignLintRuleMetadata.model_validate(entry)
    catalog = DesignLintRuleCatalog(
        schema_version="3",
        sha256="a" * 64,
        rules=(validated,),
    )

    rendered = catalog_text(catalog)
    assert "Maturity: field_validated" in rendered
    assert "Field validation: measurement:reviewed-unit-set-2026-01" in rendered


def test_non_field_maturity_cannot_claim_field_validation_evidence() -> None:
    entry = rule_catalog().rules[0].model_dump(mode="python")
    entry["field_validation_evidence"] = ("measurement:unreviewed",)

    with pytest.raises(ValidationError, match="requires field-validated maturity"):
        DesignLintRuleMetadata.model_validate(entry)
