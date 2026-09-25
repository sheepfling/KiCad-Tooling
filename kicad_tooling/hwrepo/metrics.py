"""Read-only current-state metrics for template policy and release exceptions."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path

from ..lint_registry import lint
from .documentation import check as documentation_check
from .generation import check_generation
from .models import (
    CheckMetric,
    DeviationMetrics,
    DeviationStatus,
    ReleaseDeviation,
    TemplateMetricsReport,
)
from .product import check as product_check
from .repository import check_repository


def deviation_metrics(
    deviations: Iterable[ReleaseDeviation], today: date | None = None
) -> DeviationMetrics:
    """Count declared release deviations without asserting their operational closure."""
    effective_today = today or datetime.now(UTC).date()
    values = tuple(deviations)
    return DeviationMetrics(
        total=len(values),
        approved=sum(item.status is DeviationStatus.APPROVED for item in values),
        open=sum(item.status is DeviationStatus.OPEN for item in values),
        closed=sum(item.status is DeviationStatus.CLOSED for item in values),
        expired=sum(item.expires < effective_today for item in values),
    )


def collect(
    root: Path,
    deviations: Iterable[ReleaseDeviation] = (),
    today: date | None = None,
) -> TemplateMetricsReport:
    """Report current policy outcomes; no source, release or external state is changed."""
    registry = lint(root)
    repository = check_repository(root)
    documentation = documentation_check(root)
    product = product_check(root)
    try:
        generation_findings = check_generation(root)
    except (OSError, ValueError) as exc:
        generation_findings = (str(exc),)
    checks = (
        CheckMetric(
            name="registry",
            status=registry.status,
            findings=len(registry.issues),
        ),
        CheckMetric(
            name="repository",
            status=repository.status,
            findings=len(repository.issues),
        ),
        CheckMetric(
            name="documentation",
            status=documentation.status,
            findings=len(documentation.issues),
        ),
        CheckMetric(
            name="product",
            status=product.status,
            findings=len(product.issues),
        ),
        CheckMetric(
            name="generation",
            status="FAIL" if generation_findings else "PASS",
            findings=len(generation_findings),
        ),
    )
    return TemplateMetricsReport(
        checks=checks,
        stale_evidence=sum(issue.code == "EVIDENCE_HASH" for issue in product.issues),
        deviations=deviation_metrics(deviations, today),
    )
