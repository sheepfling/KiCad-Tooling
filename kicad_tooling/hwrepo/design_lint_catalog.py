"""Packaged design-lint rule catalog loading and integrity."""

from __future__ import annotations

import hashlib
from importlib.resources import files

from .contracts import parse_model_text
from .design_lint_rule_models import DesignLintRuleCatalog, DesignLintRuleCatalogDocument


def rule_catalog() -> DesignLintRuleCatalog:
    """Load and hash the installed rule definition shipped with this package."""
    content = files("kicad_tooling.hwrepo").joinpath("design-lint-rules.json").read_bytes()
    document = parse_model_text(content.decode("utf-8"), DesignLintRuleCatalogDocument)
    return DesignLintRuleCatalog(
        schema_version=document.schema_version,
        sha256=hashlib.sha256(content).hexdigest(),
        rules=document.rules,
    )
