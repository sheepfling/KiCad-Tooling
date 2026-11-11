"""Source-bound review of schematic ERC Error-to-Warning overrides."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_component_coverage import ComponentMapCoverageInputs
from kicad_tooling.hwrepo.design_lint_evaluation_types import DesignLintEvaluationRequest
from kicad_tooling.hwrepo.design_lint_evaluator import evaluate_request
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import NetlistContract, ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_project_settings import (
    ERC_DEFAULT_ERROR_RULE_KEYS,
    ERC_DEFAULT_IGNORED_RULE_KEYS,
    ERC_DEFAULT_WARNING_RULE_KEYS,
    SchematicErcRuleSeverity,
    configured_schematic_erc_rule_severities,
)
from kicad_tooling.hwrepo.schematic_erc_warning_downgrade import (
    SchematicErcWarningDowngradeCandidate,
    source_bound_schematic_erc_warning_downgrade_candidates,
)
from tests.design_lint_fixtures import coach

RULE_ID = "schematic.erc_error_downgraded"
PROJECT_RELATIVE = "projects/controller.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-warning-downgrade"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    document: str | None = None,
    *,
    kicad_version: str = "10.0.5",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True)
    if document is None:
        document = (FIXTURES / "fault.kicad_pro").read_text(encoding="utf-8")
    project.write_text(document, encoding="utf-8")
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=PROJECT_RELATIVE, kicad_version=kicad_version),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: Mapping[str, str]):
    return source_bound_schematic_erc_warning_downgrade_candidates(root, config, source_hashes)


def test_error_default_changed_to_warning_creates_source_bound_review(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)

    (candidate,) = _scan(root, config, source_hashes)

    assert isinstance(candidate, SchematicErcWarningDowngradeCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{PROJECT_RELATIVE}#erc/rule_severities/pin_not_connected"
    assert "changed from its KiCad Error default to Warning" in candidate.message
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.5",),
        "erc_rule_key": ("pin_not_connected",),
        "configured_severity": ("warning",),
        "default_severity": ("error",),
    }


@pytest.mark.parametrize("rule_key", sorted(ERC_DEFAULT_ERROR_RULE_KEYS))
def test_every_known_error_default_warning_override_is_reviewed(
    tmp_path: Path, rule_key: str
) -> None:
    document = f'{{"erc":{{"meta":{{"version":0}},"rule_severities":{{"{rule_key}":"warning"}}}}}}'
    root, _, config, source_hashes = _project(tmp_path, document)

    (candidate,) = _scan(root, config, source_hashes)

    assert candidate.evidence["erc_rule_key"] == (rule_key,)
    assert candidate.evidence["default_severity"] == ("error",)


@pytest.mark.parametrize("rule_key", sorted(ERC_DEFAULT_WARNING_RULE_KEYS))
def test_kicad_default_warning_is_a_valid_control(tmp_path: Path, rule_key: str) -> None:
    document = f'{{"erc":{{"meta":{{"version":0}},"rule_severities":{{"{rule_key}":"warning"}}}}}}'
    root, _, config, source_hashes = _project(tmp_path, document)

    assert _scan(root, config, source_hashes) == ()


def test_error_warning_and_ignore_baselines_are_disjoint() -> None:
    assert not ERC_DEFAULT_ERROR_RULE_KEYS & ERC_DEFAULT_WARNING_RULE_KEYS
    assert not ERC_DEFAULT_ERROR_RULE_KEYS & ERC_DEFAULT_IGNORED_RULE_KEYS
    assert not ERC_DEFAULT_WARNING_RULE_KEYS & ERC_DEFAULT_IGNORED_RULE_KEYS
    assert len(ERC_DEFAULT_ERROR_RULE_KEYS) == 20
    assert len(ERC_DEFAULT_WARNING_RULE_KEYS) == 22


def test_active_error_and_known_kicad_warning_controls_are_quiet(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, "{}")
    (root / PROJECT_RELATIVE).write_bytes((FIXTURES / "control.kicad_pro").read_bytes())
    source_hashes[PROJECT_RELATIVE] = digest(root / PROJECT_RELATIVE)

    assert _scan(root, config, source_hashes) == ()
    parsed = configured_schematic_erc_rule_severities(
        (FIXTURES / "control.kicad_pro").read_text(encoding="utf-8")
    )
    assert parsed == (
        SchematicErcRuleSeverity("endpoint_off_grid", "warning"),
        SchematicErcRuleSeverity("pin_not_connected", "error"),
    )


def test_unknown_warning_key_is_not_claimed_as_a_known_downgrade(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(
        tmp_path,
        '{"erc":{"meta":{"version":0},"rule_severities":{"future_rule":"warning"}}}',
    )

    assert _scan(root, config, source_hashes) == ()


def test_candidate_fields_cannot_diverge_from_source_evidence(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    (candidate,) = _scan(root, config, source_hashes)

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, subject=f"{candidate.subject}/stale")
    with pytest.raises(ValueError, match="known Error-default"):
        replace(
            candidate.source_evidence,
            configured_rule=SchematicErcRuleSeverity("future_rule", "warning"),
        )
    with pytest.raises(ValueError, match="must have Warning severity"):
        replace(
            candidate.source_evidence,
            configured_rule=SchematicErcRuleSeverity("pin_not_connected", "error"),
        )


@pytest.mark.parametrize(
    "document",
    (
        '{"erc":{"meta":{"version":1},"rule_severities":{"pin_not_connected":"warning"}}}',
        '{"erc":{"meta":null,"rule_severities":{"pin_not_connected":"warning"}}}',
        '{"erc":{"rule_severities":{"pin_not_connected":null}}}',
    ),
)
def test_unknown_schema_or_malformed_settings_fail_closed(document: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        configured_schematic_erc_rule_severities(document)


def test_source_hash_is_required_and_must_match(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)

    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})
    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, source_hashes)


def test_unsupported_kicad_versions_and_non_schematic_projects_are_out_of_scope(
    tmp_path: Path,
) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    pcb_only = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB_ONLY))
    assert _scan(root, pcb_only, source_hashes) == ()
    for version in ("9.0.0", "10.1.0", "11.0.0"):
        unsupported = cast(
            ProjectConfig,
            SimpleNamespace(kind=ProjectKind.PCB, project=config.project, kicad_version=version),
        )
        assert _scan(root, unsupported, source_hashes) == ()


def test_source_order_does_not_change_candidate_order_or_subjects(tmp_path: Path) -> None:
    first = '{"erc":{"rule_severities":{"pin_not_connected":"warning","label_dangling":"warning"}}}'
    second = (
        '{"erc":{"rule_severities":{"label_dangling":"warning","pin_not_connected":"warning"}}}'
    )
    first_root, _, first_config, first_hashes = _project(tmp_path / "first", first)
    second_root, _, second_config, second_hashes = _project(tmp_path / "second", second)

    first_candidates = _scan(first_root, first_config, first_hashes)
    second_candidates = _scan(second_root, second_config, second_hashes)

    assert tuple(item.subject for item in first_candidates) == tuple(
        item.subject for item in second_candidates
    )
    assert tuple(item.subject for item in first_candidates) == (
        f"{PROJECT_RELATIVE}#erc/rule_severities/label_dangling",
        f"{PROJECT_RELATIVE}#erc/rule_severities/pin_not_connected",
    )


def test_review_block_exact_ignore_and_off_policy_are_supported(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    (candidate,) = _scan(root, config, source_hashes)
    observed = coach(NetlistContract(components={}, nets={}))

    def inspect(policy: DesignLintPolicy):
        return evaluate_request(
            DesignLintEvaluationRequest(
                project_id="synthetic-erc-error-downgrade",
                coach=observed,
                policy=policy,
                component_map_coverage=ComponentMapCoverageInputs(),
                schematic_source_candidates=(candidate,),
            )
        )

    finding = next(item for item in inspect(DesignLintPolicy()).findings if item.rule_id == RULE_ID)
    assert (finding.mode, finding.disposition) == ("review", "OPEN")
    blocked = inspect(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="block",
                    reason="Synthetic policy requires downgraded ERC rules to be reviewed",
                ),
            )
        )
    )
    assert next(item for item in blocked.findings if item.rule_id == RULE_ID).mode == "block"
    ignored = inspect(
        DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=RULE_ID,
                    fingerprint=finding.fingerprint,
                    reason="Synthetic intentional ERC severity change",
                ),
            )
        )
    )
    assert (
        next(item for item in ignored.findings if item.rule_id == RULE_ID).disposition == "IGNORED"
    )
    off = inspect(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="off",
                    reason="Synthetic explicit disablement",
                ),
            )
        )
    )
    assert next(item for item in off.findings if item.rule_id == RULE_ID).disposition == "RULE_OFF"
