"""Read-only MCP adapter for design-lint rule catalog discovery."""

from __future__ import annotations

from typing import Literal

from . import design_lint
from .design_lint_rule_models import DesignLintRuleCatalog
from .design_lint_rule_types import DesignLintTheme


def list_design_lint_rules(
    theme: DesignLintTheme | None = None,
    status: Literal["active", "prototype", "retired"] | None = None,
    maturity: Literal["synthetic_validated", "cohort_candidate", "field_validated"] | None = None,
    default_mode: Literal["review", "block", "off"] | None = None,
    rule_id: str | None = None,
    rule_id_prefix: str | None = None,
) -> DesignLintRuleCatalog:
    """Return the packaged rule catalog without reading project evidence."""
    return design_lint.rule_catalog(
        theme=theme,
        status=status,
        maturity=maturity,
        default_mode=default_mode,
        rule_id=rule_id,
        rule_id_prefix=rule_id_prefix,
    )
