from __future__ import annotations

from .design_lint_finding_models import DesignLintFinding
from .design_lint_rule_models import DesignLintRuleCatalog


def validate_catalogued_findings(
    *,
    rule_catalog: DesignLintRuleCatalog | None,
    findings: tuple[DesignLintFinding, ...],
) -> None:
    if rule_catalog is None:
        return
    known = {item.rule_id for item in rule_catalog.rules if item.status == "active"}
    unknown = sorted({item.rule_id for item in findings} - known)
    if unknown:
        raise ValueError(
            f"Design-lint findings use rules absent from the active catalog: {unknown}"
        )
