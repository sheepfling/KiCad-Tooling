"""Guard source identity and static pipeline report model ownership."""

from __future__ import annotations

import ast
from operator import setitem
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo import models, source_state_models, static_pipeline_models
from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.documentation_models import DocumentationPolicyReport
from kicad_tooling.hwrepo.governance_lint_models import GovernanceLintReport
from kicad_tooling.hwrepo.product_models import ProductPolicyReport
from kicad_tooling.hwrepo.project_static_pipeline_models import GenerationReport, ProjectTestsReport
from kicad_tooling.hwrepo.repository_policy_models import RepositoryPolicyReport

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]
_MODEL_NAMES = frozenset({"SourceState", "StaticPipelineReport"})


def _imports(path: Path) -> set[str]:
    return {
        node.module
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }


def test_source_and_static_pipeline_owners_have_closed_dependencies() -> None:
    source_owner = _ROOT / "kicad_tooling/hwrepo/source_state_models.py"
    report_owner = _ROOT / "kicad_tooling/hwrepo/static_pipeline_models.py"

    assert len(source_owner.read_text(encoding="utf-8").splitlines()) < 500
    assert len(report_owner.read_text(encoding="utf-8").splitlines()) < 500
    assert _imports(source_owner) == {
        "collections.abc",
        "types",
        "typing",
        "pydantic",
        "model_primitives",
    }
    assert _imports(report_owner) == {
        "typing",
        "pydantic",
        "command_evidence_models",
        "documentation_models",
        "governance_lint_models",
        "model_primitives",
        "product_models",
        "project_static_pipeline_models",
        "repository_policy_models",
        "source_state_models",
    }


def test_production_consumers_import_source_and_static_reports_from_owners() -> None:
    tooling = _ROOT / "kicad_tooling"
    registry = tooling / "hwrepo/models.py"
    violations: list[str] = []

    for path in tooling.rglob("*.py"):
        if path == registry:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or node.module not in {
                "models",
                "hwrepo.models",
                "kicad_tooling.hwrepo.models",
            }:
                continue
            misplaced = _MODEL_NAMES.intersection(alias.name for alias in node.names)
            if misplaced:
                violations.append(f"{path.relative_to(_ROOT)}:{node.lineno}: {sorted(misplaced)}")

    assert not violations, "Import static evidence models from their owners: " + "; ".join(
        violations
    )


def _repository_static_report() -> static_pipeline_models.StaticPipelineReport:
    command = CommandEvidence(
        argv=("quality-tool",), started_utc="2026-11-03T18:00:00Z", returncode=0
    )
    return static_pipeline_models.StaticPipelineReport(
        status="PASS",
        source=source_state_models.SourceState(
            commit="a" * 40,
            clean=True,
            files_sha256={"README.md": "b" * 64},
        ),
        scope="repository_static",
        tooling_version="1.2.3",
        registry=GovernanceLintReport(projects=("board",), issues=(), status="PASS"),
        repository=RepositoryPolicyReport(status="PASS", issues=()),
        documentation=DocumentationPolicyReport(
            roots=("README.md",), documents=1, issues=(), status="PASS"
        ),
        rumdl=command,
        mdrepo=command,
        product=ProductPolicyReport(status="PASS", products=(), open_items={}, issues=()),
        generation=GenerationReport(status="PASS", issues=()),
        project_tests=ProjectTestsReport(status="PASS", commands={}),
    )


def test_registry_exports_preserve_identity_and_report_json_contract() -> None:
    assert models.SourceState is source_state_models.SourceState
    assert models.StaticPipelineReport is static_pipeline_models.StaticPipelineReport

    report = _repository_static_report()
    source = report.source
    assert source is not None
    assert report.model_dump(mode="json")["source"]["files_sha256"] == {"README.md": "b" * 64}
    with pytest.raises(TypeError):
        setitem(cast(Any, source.files_sha256), "README.md", "c" * 64)
    assert (
        static_pipeline_models.StaticPipelineReport.model_validate_json(report.model_dump_json())
        == report
    )
    with pytest.raises(ValidationError, match="Legacy full reports require"):
        static_pipeline_models.StaticPipelineReport.model_validate(
            {**report.model_dump(), "scope": "static_only", "tooling_version": None}
        )
