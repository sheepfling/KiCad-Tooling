"""Source-bound review candidates for PCB DRC severity changes."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .design_lint_pcb_drc_global_severity_candidate_evidence import (
    WARNING_DEFAULT_DRC_SUPPORTED_VERSIONS,
    PcbDrcSeverityCandidate,
    PcbDrcSeverityCategory,
    PcbDrcSeverityFindingEvidence,
    PcbDrcSeverityRuleId,
    SourceBoundPcbDrcSettings,
)
from .design_lint_types import Candidate
from .pcb_drc_project_settings import (
    PcbDrcCheckSeverity,
    configured_core_drc_check_severities,
    configured_dfm_drc_check_severities,
    configured_electrical_drc_check_severities,
    configured_miscellaneous_drc_check_severities,
    configured_signal_integrity_drc_check_severities,
    configured_warning_default_drc_check_severities,
)
from .pcb_drc_project_settings_evidence import read_source_bound_pcb_project_settings
from .project_models import (
    ProjectConfig,
    ProjectKind,
)
from .source_state_models import SourceHashInventory


def _source_bound_drc_settings(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
    *,
    supported_version_prefix: str = "10.",
    parse_severities: Callable[[str], tuple[PcbDrcCheckSeverity, ...]] = (
        configured_core_drc_check_severities
    ),
) -> SourceBoundPcbDrcSettings | None:
    if config.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        return None
    if not config.kicad_version.startswith(supported_version_prefix):
        return None

    relative = str(config.project)
    source = read_source_bound_pcb_project_settings(root, relative, source_hashes)
    if source is None:
        return None
    try:
        severities = parse_severities(source.document)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{relative}: could not read supported PCB DRC severity settings: {exc}"
        ) from exc
    return SourceBoundPcbDrcSettings(
        project_path=source.source_path,
        source_sha256=source.source_sha256,
        project_kind=config.kind,
        kicad_version=config.kicad_version,
        configured_severities=severities,
    )


def _severity_candidate(
    settings: SourceBoundPcbDrcSettings,
    configured_check: PcbDrcCheckSeverity,
    *,
    category: PcbDrcSeverityCategory,
    rule_id: PcbDrcSeverityRuleId,
    subject: str,
    message: str,
) -> PcbDrcSeverityCandidate:
    source = PcbDrcSeverityFindingEvidence(
        settings=settings,
        configured_check=configured_check,
        category=category,
        rule_id=rule_id,
    )
    return PcbDrcSeverityCandidate.from_source_evidence(
        source,
        subject=subject,
        message=message,
    )


def ignored_core_native_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Prompt when source-bound KiCad 10 settings suppress a core PCB DRC check."""
    settings = _source_bound_drc_settings(root, config, source_hashes)
    if settings is None:
        return ()

    return tuple(
        _severity_candidate(
            settings,
            check,
            category="core",
            rule_id="pcb.core_drc_check_ignored",
            subject=(
                f"{settings.project_path}#board/design_settings/rule_severities/{check.check_id}"
            ),
            message=(
                f"Core native DRC check {check.check_id!r} is configured as Ignore; "
                "confirm that suppressing this check is intentional."
            ),
        )
        for check in settings.configured_severities
        if check.configured_severity == "ignore"
    )


def ignored_dfm_native_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review KiCad 10.0 DFM checks documented with Error defaults but set to Ignore."""
    settings = _source_bound_drc_settings(
        root,
        config,
        source_hashes,
        supported_version_prefix="10.0.",
        parse_severities=configured_dfm_drc_check_severities,
    )
    if settings is None:
        return ()
    return tuple(
        _severity_candidate(
            settings,
            check,
            category="dfm",
            rule_id="pcb.dfm_drc_check_ignored",
            subject=(
                f"{settings.project_path}#board/design_settings/rule_severities/{check.check_id}"
            ),
            message=(
                f"Documented Error-default DFM DRC check {check.check_id!r} is configured "
                "as Ignore; "
                "confirm that suppressing this check is intentional."
            ),
        )
        for check in settings.configured_severities
        if check.configured_severity == "ignore"
    )


def warning_core_native_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review Error-default core PCB checks explicitly downgraded to Warning."""
    settings = _source_bound_drc_settings(root, config, source_hashes)
    if settings is None:
        return ()
    return tuple(
        _severity_candidate(
            settings,
            check,
            category="core",
            rule_id="pcb.core_drc_check_warning",
            subject=(
                f"{settings.project_path}#board/design_settings/rule_severities/{check.check_id}"
            ),
            message=(
                f"Error-default core DRC check {check.check_id!r} is configured as Warning; "
                "confirm that lowering its severity is intentional."
            ),
        )
        for check in settings.configured_severities
        if check.configured_severity == "warning"
    )


def warning_dfm_native_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review KiCad 10.0 DFM checks documented with Error defaults but set to Warning."""
    settings = _source_bound_drc_settings(
        root,
        config,
        source_hashes,
        supported_version_prefix="10.0.",
        parse_severities=configured_dfm_drc_check_severities,
    )
    if settings is None:
        return ()
    return tuple(
        _severity_candidate(
            settings,
            check,
            category="dfm",
            rule_id="pcb.dfm_drc_check_warning",
            subject=(
                f"{settings.project_path}#board/design_settings/rule_severities/{check.check_id}"
            ),
            message=(
                f"Documented Error-default DFM DRC check {check.check_id!r} is configured "
                "as Warning; "
                "confirm that lowering its severity is intentional."
            ),
        )
        for check in settings.configured_severities
        if check.configured_severity == "warning"
    )


def downgraded_signal_integrity_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review Error-default KiCad 10.0 signal-integrity checks set below Error."""
    return _downgraded_native_drc_check_candidates(
        root,
        config,
        source_hashes,
        rule_id="pcb.signal_integrity_drc_check_downgraded",
        category="signal_integrity",
        parse_severities=configured_signal_integrity_drc_check_severities,
    )


def downgraded_electrical_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review Error-default KiCad 10.0 electrical checks set below Error."""
    return _downgraded_native_drc_check_candidates(
        root,
        config,
        source_hashes,
        rule_id="pcb.electrical_drc_check_downgraded",
        category="electrical",
        parse_severities=configured_electrical_drc_check_severities,
    )


def downgraded_miscellaneous_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review Error-default KiCad 10.0 miscellaneous checks set below Error."""
    return _downgraded_native_drc_check_candidates(
        root,
        config,
        source_hashes,
        rule_id="pcb.miscellaneous_drc_check_downgraded",
        category="miscellaneous",
        parse_severities=configured_miscellaneous_drc_check_severities,
    )


def ignored_warning_default_native_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review Warning-default KiCad DRC checks explicitly disabled as Ignore."""
    if config.kicad_version not in WARNING_DEFAULT_DRC_SUPPORTED_VERSIONS:
        return ()
    settings = _source_bound_drc_settings(
        root,
        config,
        source_hashes,
        supported_version_prefix="10.0.",
        parse_severities=configured_warning_default_drc_check_severities,
    )
    if settings is None:
        return ()
    return tuple(
        _severity_candidate(
            settings,
            check,
            category="warning_default",
            rule_id="pcb.warning_default_drc_check_ignored",
            subject=(
                f"{settings.project_path}#board/design_settings/rule_severities/{check.check_id}"
            ),
            message=(
                f"Warning-default native DRC check {check.check_id!r} is configured as Ignore; "
                "confirm that disabling this check is intentional."
            ),
        )
        for check in settings.configured_severities
        if check.configured_severity == "ignore"
    )


def _downgraded_native_drc_check_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
    *,
    rule_id: PcbDrcSeverityRuleId,
    category: PcbDrcSeverityCategory,
    parse_severities: Callable[[str], tuple[PcbDrcCheckSeverity, ...]],
) -> tuple[Candidate, ...]:
    settings = _source_bound_drc_settings(
        root,
        config,
        source_hashes,
        supported_version_prefix="10.0.",
        parse_severities=parse_severities,
    )
    if settings is None:
        return ()
    return tuple(
        _severity_candidate(
            settings,
            check,
            category=category,
            rule_id=rule_id,
            subject=(
                f"{settings.project_path}#board/design_settings/rule_severities/{check.check_id}"
            ),
            message=(
                f"Error-default {category.replace('_', '-')} DRC check {check.check_id!r} "
                f"is configured as {check.configured_severity.title()}; confirm lowering its "
                "severity is intentional."
            ),
        )
        for check in settings.configured_severities
        if check.configured_severity in {"ignore", "warning"}
    )
