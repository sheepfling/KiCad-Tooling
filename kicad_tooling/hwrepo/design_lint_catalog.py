"""Packaged design-lint rule catalog loading and integrity."""

from __future__ import annotations

import hashlib
from importlib.resources import files
from typing import Literal

from .contracts import parse_model_text
from .design_lint_rule_models import DesignLintRuleCatalog, DesignLintRuleCatalogDocument
from .design_lint_rule_types import DesignLintTheme


def rule_catalog(
    *,
    theme: DesignLintTheme | None = None,
    status: Literal["active", "prototype", "retired"] | None = None,
    maturity: Literal["synthetic_validated", "cohort_candidate", "field_validated"] | None = None,
    default_mode: Literal["review", "block", "off"] | None = None,
    rule_id: str | None = None,
    rule_id_prefix: str | None = None,
) -> DesignLintRuleCatalog:
    """Load the packaged catalog, optionally selecting exact metadata dimensions.

    The digest always identifies the complete installed catalog, even for a subset.
    """
    content = files("kicad_tooling.hwrepo").joinpath("design-lint-rules.json").read_bytes()
    document = parse_model_text(content.decode("utf-8"), DesignLintRuleCatalogDocument)
    return DesignLintRuleCatalog(
        schema_version=document.schema_version,
        sha256=hashlib.sha256(content).hexdigest(),
        rules=tuple(
            item
            for item in document.rules
            if (theme is None or item.theme == theme)
            and (status is None or item.status == status)
            and (maturity is None or item.maturity == maturity)
            and (default_mode is None or item.default_mode == default_mode)
            and (rule_id is None or item.rule_id == rule_id)
            and (rule_id_prefix is None or item.rule_id.startswith(rule_id_prefix))
        ),
    )
