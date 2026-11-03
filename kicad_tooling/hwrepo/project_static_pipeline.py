"""Selected-project portable checks and their typed report assembly."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .command_evidence_models import CommandEvidence
from .generation import check_generation
from .governance_lint import lint
from .pipeline_journal import PipelineJournal
from .product import check as product_check
from .project_static_pipeline_models import (
    GenerationReport,
    ProjectStaticPipelineReport,
    ProjectStaticPipelineRequest,
    ProjectTestsReport,
)
from .project_tests import run_tests
from .repository import check_repository

_Result = TypeVar("_Result", bound=BaseModel)


def generation_report(root: Path, selected: tuple[str, ...] | None = None) -> GenerationReport:
    try:
        issues = check_generation(root, selected)
        return GenerationReport(status="FAIL" if issues else "PASS", issues=issues)
    except (OSError, ValueError) as exc:
        return GenerationReport(status="FAIL", issues=(str(exc),))


def checked_project_tests(
    root: Path, selected: tuple[str, ...] | None = None, workers: int = 1
) -> ProjectTestsReport:
    """Keep malformed discovery records as a typed failure in the portable report."""
    try:
        return run_tests(root, selected, max_workers=workers)
    except (OSError, ValueError) as exc:
        return ProjectTestsReport(
            status="FAIL",
            commands={
                "discovery": CommandEvidence(
                    argv=("project-test-discovery",),
                    started_utc=datetime.now(UTC).isoformat(),
                    returncode=1,
                    error=str(exc),
                ),
            },
        )


def _phase(journal: PipelineJournal | None, name: str, action: Callable[[], _Result]) -> _Result:
    return action() if journal is None else journal.stage(name, action)


def run_project_static_pipeline(
    root: Path,
    request: ProjectStaticPipelineRequest,
    journal: PipelineJournal | None = None,
) -> ProjectStaticPipelineReport:
    """Run the portable policy lane for its typed project scope."""
    selected = request.project_ids
    workers = request.workers
    registry = _phase(journal, "registry", lambda: lint(root, list(selected)))
    repository = _phase(journal, "repository", lambda: check_repository(root, selected))
    product = _phase(journal, "product", lambda: product_check(root, selected_project_ids=selected))
    generation = _phase(journal, "generation", lambda: generation_report(root, selected))
    project_tests = _phase(
        journal, "project-tests", lambda: checked_project_tests(root, selected, workers)
    )
    passed = (
        registry.status == "PASS"
        and repository.status == "PASS"
        and product.status == "PASS"
        and generation.status == "PASS"
        and project_tests.status == "PASS"
    )
    return ProjectStaticPipelineReport(
        status="PASS" if passed else "FAIL",
        projects=selected,
        registry=registry,
        repository=repository,
        product=product,
        generation=generation,
        project_tests=project_tests,
    )
