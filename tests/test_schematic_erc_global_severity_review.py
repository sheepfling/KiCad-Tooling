"""Source-bound review of globally ignored schematic ERC rules."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
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
from kicad_tooling.hwrepo.schematic_erc_global_severity_review import (
    SchematicErcIgnoredRuleCandidate,
    source_bound_schematic_erc_ignored_rule_candidates,
)
from kicad_tooling.hwrepo.schematic_erc_project_settings import (
    ERC_DEFAULT_IGNORED_RULE_KEYS_BY_KICAD_VERSION,
    SchematicErcRuleSeverity,
    configured_schematic_erc_rule_severities,
)
from tests.design_lint_fixtures import coach

RULE_ID = "schematic.erc_rule_ignored"
PROJECT_RELATIVE = "projects/controller.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-global-severity"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str = "fault.kicad_pro",
    *,
    kicad_version: str = "10.0.5",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=PROJECT_RELATIVE, kicad_version=kicad_version),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: Mapping[str, str]):
    return source_bound_schematic_erc_ignored_rule_candidates(root, config, source_hashes)


@pytest.mark.parametrize("version", tuple(ERC_DEFAULT_IGNORED_RULE_KEYS_BY_KICAD_VERSION))
def test_ignored_pin_connectivity_rule_creates_source_bound_review_candidate(
    tmp_path: Path, version: str
) -> None:
    root, project, config, source_hashes = _project(tmp_path, kicad_version=version)

    candidates = _scan(root, config, source_hashes)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert isinstance(candidate, SchematicErcIgnoredRuleCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{PROJECT_RELATIVE}#erc/rule_severities/pin_not_connected"
    assert "configured as Ignore" in candidate.message
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": (version,),
        "erc_rule_key": ("pin_not_connected",),
        "configured_severity": ("ignore",),
    }


def test_candidate_fields_cannot_diverge_from_source_settings(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    (candidate,) = _scan(root, config, source_hashes)

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, subject=f"{candidate.subject}/stale")
    with pytest.raises(ValueError, match="must have Ignore severity"):
        replace(candidate.source_evidence, configured_rule=SchematicErcRuleSeverity("x", "warning"))


@pytest.mark.parametrize(
    ("version", "rule_key"),
    tuple(
        (version, rule_key)
        for version, rule_keys in ERC_DEFAULT_IGNORED_RULE_KEYS_BY_KICAD_VERSION.items()
        for rule_key in sorted(rule_keys)
    ),
)
def test_kicad_default_ignores_are_valid_controls_for_each_audited_patch(
    tmp_path: Path, version: str, rule_key: str
) -> None:
    document = f'{{"erc":{{"rule_severities":{{"{rule_key}":"ignore"}}}}}}'
    root, _, config, source_hashes = _project(tmp_path, kicad_version=version)
    project = root / PROJECT_RELATIVE
    project.write_text(document, encoding="utf-8")
    source_hashes[PROJECT_RELATIVE] = digest(project)

    assert _scan(root, config, source_hashes) == ()


def test_active_severity_settings_remain_valid_controls(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, "control.kicad_pro")

    assert _scan(root, config, source_hashes) == ()
    parsed = configured_schematic_erc_rule_severities(
        (FIXTURES / "control.kicad_pro").read_text(encoding="utf-8")
    )
    assert parsed == (
        SchematicErcRuleSeverity("footprint_filter", "ignore"),
        SchematicErcRuleSeverity("four_way_junction", "ignore"),
        SchematicErcRuleSeverity("label_dangling", "warning"),
        SchematicErcRuleSeverity("pin_not_connected", "error"),
        SchematicErcRuleSeverity("simulation_model_issue", "ignore"),
        SchematicErcRuleSeverity("single_global_label", "ignore"),
    )


def test_explicit_rule_severity_order_does_not_change_candidate_identity() -> None:
    first = '{"erc":{"rule_severities":{"pin_not_connected":"ignore","label_dangling":"ignore"}}}'
    second = '{"erc":{"rule_severities":{"label_dangling":"ignore","pin_not_connected":"ignore"}}}'

    parsed = configured_schematic_erc_rule_severities(first)
    reordered = configured_schematic_erc_rule_severities(second)
    assert parsed == reordered
    assert tuple(item.rule_key for item in parsed) == ("label_dangling", "pin_not_connected")


@pytest.mark.parametrize(
    "document",
    (
        '{"erc":{"meta":{"version":1},"rule_severities":{}}}',
        '{"erc":{"meta":null,"rule_severities":{}}}',
        '{"erc":{"rule_severities":null}}',
        '{"erc":{"rule_severities":{"pin_not_connected":1}}}',
        '{"erc":{"rule_severities":{"pin_not_connected":"disabled"}}}',
        '{"erc":{"rule_severities":{"":"ignore"}}}',
        ('{"erc":{"rule_severities":{"pin_not_connected":"ignore","pin_not_connected":"error"}}}'),
    ),
)
def test_unknown_or_malformed_severity_settings_fail_closed(document: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        configured_schematic_erc_rule_severities(document)


def test_source_hash_is_required_and_must_match(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)

    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})
    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, source_hashes)


def test_non_schematic_kinds_and_unsupported_patch_versions_are_out_of_scope(
    tmp_path: Path,
) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    pcb_only = cast(ProjectConfig, SimpleNamespace(kind=ProjectKind.PCB_ONLY))
    assert _scan(root, pcb_only, source_hashes) == ()
    for version in ("9.0.0", "10.0.3", "10.0.9", "10.1.0", "11.0.0"):
        unsupported = cast(
            ProjectConfig,
            SimpleNamespace(kind=ProjectKind.PCB, project=PROJECT_RELATIVE, kicad_version=version),
        )
        assert _scan(root, unsupported, source_hashes) == ()
    assert config.kind is ProjectKind.PCB


def test_default_ignore_catalog_is_exact_and_matches_rule_support() -> None:
    expected_versions = {
        "10.0.0",
        "10.0.1",
        "10.0.2",
        "10.0.4",
        "10.0.5",
        "10.0.6",
        "10.0.7",
        "10.0.8",
    }
    (entry,) = rule_catalog(rule_id=RULE_ID).rules
    catalog_versions = set(re.findall(r"\b10\.0\.\d+\b", entry.supported_kicad_versions[0]))

    assert set(ERC_DEFAULT_IGNORED_RULE_KEYS_BY_KICAD_VERSION) == expected_versions
    assert catalog_versions == expected_versions
    assert all(
        rule_keys == ERC_DEFAULT_IGNORED_RULE_KEYS_BY_KICAD_VERSION["10.0.0"]
        for rule_keys in ERC_DEFAULT_IGNORED_RULE_KEYS_BY_KICAD_VERSION.values()
    )


def test_review_block_exact_ignore_and_off_policy_are_supported(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    (candidate,) = _scan(root, config, source_hashes)
    observed = coach(NetlistContract(components={}, nets={}))

    def inspect(policy: DesignLintPolicy):
        return evaluate_request(
            DesignLintEvaluationRequest(
                project_id="synthetic-erc-global-severity",
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
                    reason="Synthetic policy requires global ERC severity review",
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
                    reason="Synthetic reviewed ERC policy",
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
                    reason="Synthetic policy disables this prompt",
                ),
            )
        )
    )
    assert next(item for item in off.findings if item.rule_id == RULE_ID).disposition == "RULE_OFF"
